"""version_check API - 在线版本检测与通道（原 stats.py updater 段独立，端点不变）"""
# -*- coding: utf-8 -*-
import asyncio
import json
import re
import time
import urllib.request
import urllib.error
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response
from .web_utils import _err, get_req_query, get_req_json, no_cache_response
try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST  # type: ignore


# ==================== 在线版本检测（原 updater.py 并入） ====================
GITHUB_REPO = "imsuperone/xb"
GITHUB_REPO_XBTEST = "imsuperone/xbtest"  # BETA 通道：快照版跟踪仓
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UPDATE_CHANNELS = ("正式", "BETA")

_LAST_CHECK_RES = {}
_LAST_CHECK_TIME = {}
_CHECK_CACHE_TTL = 300.0  # 成功结果缓存 5 分钟：版本不变时不再打 GitHub，防 RateLimit
_CHECK_FAIL_TTL = 60.0  # 失败结果缓存 1 分钟：网络故障时不再每点每试
_CHECK_RUNNING_SINCE = {}  # channel -> 在途检测开始时间戳（分槽：双通道并查互不阻塞，防惊群）
_CHECK_RUNNING_TTL = 30.0  # 在途超时：拥有者超过此时长未回即视为死亡，等候者自行接管


def _get_local_version(plugin_base=""):
    """本地版本：委托 version.py 单源（读 metadata.yaml），失败回 _FALLBACK。"""
    try:
        try:
            from ..version import get_version as _gv
        except ImportError:
            from core.version import get_version as _gv  # type: ignore
        return _gv(plugin_base)
    except Exception:
        pass
    return "unknown"


def _parse_version_tuple(v_str):
    """纪元比较：委托 version.parse_version_tuple（单源，含快照制），失败走本地同逻辑兜底。"""
    try:
        try:
            from ..version import parse_version_tuple as _pvt
        except ImportError:
            from core.version import parse_version_tuple as _pvt  # type: ignore
        return _pvt(v_str)
    except Exception:
        pass
    s = str(v_str or "").strip()
    m0 = re.match(r"^(\d{4})[wW](\d{2})(\d{2})([a-zA-Z]+)$", s)
    if m0:
        try:
            _seq = 0
            for _ch in m0.group(4).lower():
                _seq = _seq * 26 + (ord(_ch) - 96)
            return (2, int(m0.group(1) + m0.group(2) + m0.group(3)), _seq)
        except Exception:
            pass
    m = re.findall(r"\d+", s)
    nums = [int(x) for x in m] if m else [0, 0, 0]
    while len(nums) < 3:
        nums.append(0)
    major, minor, patch = nums[0], nums[1], nums[2]
    epoch = 0 if (major == 0 and 10 <= minor <= 68) else 1
    return (epoch, major, minor, patch)





def _update_channel():
    """更新通道：recall 记忆，缺省 BETA（beta 插件；正式版树可另行默认正式）。"""
    try:
        c = str(ST.recall_get("update_channel", "BETA") or "BETA").strip()
        if c in UPDATE_CHANNELS:
            return c
    except Exception:
        pass
    return "BETA"


def _channel_repo(channel):
    return GITHUB_REPO_XBTEST if channel == "BETA" else GITHUB_REPO


def check_latest_version(plugin_base="", repo=""):
    """
    双通道检测最新版本：
    1. GitHub Releases 接口 (官方标准发版，带版本日志与元数据)
    2. GitHub main 分支 metadata.yaml (实时 Git 提交版本，支持多镜像加速容灾)
    择优选取版本号最高者，并与本地版本进行纪元元组比较。
    repo 为空则用官方仓；BETA 通道传 xbtest 仓。
    """
    local_ver = _get_local_version(plugin_base)
    repo = (repo or "").strip() or GITHUB_REPO
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "User-Agent": "XbBot-AutoUpdater/1.0",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. 优先尝试检测 main 分支 metadata.yaml（多镜像加速容灾；3 镜像×2 秒=最坏 6 秒，
    # 加 Releases 4 秒共 10 秒，低于前端 20 秒熔断；慢代理镜像已剔除）
    main_ver = ""
    ts = int(time.time())
    raw_meta_urls = [
        f"https://raw.githubusercontent.com/{repo}/main/metadata.yaml",
        f"https://cdn.jsdelivr.net/gh/{repo}@main/metadata.yaml?_t={ts}",
        f"https://fastly.jsdelivr.net/gh/{repo}@main/metadata.yaml?_t={ts}"
    ]
    for url in raw_meta_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    txt = resp.read().decode("utf-8")
                    for line in txt.splitlines():
                        if line.strip().startswith("version:"):
                            main_ver = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                    if main_ver:
                        break
        except Exception:
            continue

    # 2. 检测 GitHub Releases 接口
    rel_ver = ""
    rel_name = ""
    rel_date = ""
    rel_body = ""
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                rel_ver = (data.get("tag_name") or data.get("name") or "").replace("v", "").strip()
                rel_name = data.get("name") or rel_ver
                rel_date = (data.get("published_at") or "")[:10]
                rel_body = data.get("body") or ""
    except Exception:
        pass

    # 3. 双通道择优：取版本号更高者
    # 若 main 分支最新提交版本严格高于 Release 版本，则提示 main 分支源码更新
    # 否则若存在 Release 发版，优先使用官方规范发版与更新日志
    if main_ver and _parse_version_tuple(main_ver) > _parse_version_tuple(rel_ver):
        best_ver = main_ver
        best_name = f"小白 v{main_ver} (Git main 源码更新)"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "已检测到 GitHub 仓库 main 分支最新提交版本，可前往 AstrBot 插件管理面板一键更新或拉取代码。"
    elif rel_ver:
        best_ver = rel_ver
        best_name = rel_name or f"小白 v{rel_ver} 正式版"
        best_date = rel_date or time.strftime("%Y-%m-%d")
        best_body = rel_body or "请查看 GitHub Releases 更新说明。"
    elif main_ver:
        best_ver = main_ver
        best_name = f"小白 v{main_ver}"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "已检测到 GitHub 仓库最新代码。"
    else:
        best_ver = local_ver
        best_name = f"小白 {local_ver}"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "当前已是最新版本。"

    has_update = _parse_version_tuple(best_ver) > _parse_version_tuple(local_ver)
    detect_error = None
    if not main_ver and not rel_ver:
        detect_error = "无法连接 GitHub（raw/Api 双通道均失败，多为服务器网络或代理问题），请检查网络后重试"
    return {
        "ok": True,
        "current_version": local_ver,
        "latest_version": best_ver,
        "has_update": has_update,
        "release_name": best_name,
        "release_date": best_date,
        "changelog": best_body,
        "detect_error": detect_error
    }


async def handle_version_check(request=None, plugin_base=""):
    """从云端检测是否有最新 Release 或 main 分支版本（完全异步化，绝不阻塞主事件循环）。
    通道：显式 channel 参数 > 存储记忆 > 默认 BETA；BETA 查 xbtest 快照仓，正式查官方仓。"""
    global _LAST_CHECK_RES, _LAST_CHECK_TIME, _CHECK_RUNNING_SINCE
    import asyncio
    channel = ""
    try:
        if isinstance(request, dict):
            channel = str(request.get("channel") or "")
        elif request is not None:
            channel = get_req_query(request, "channel", "")
    except Exception:
        pass
    if (not channel or channel.strip() not in UPDATE_CHANNELS):
        # 官方 proxy 直读（真机唯一真相，request=None 时唯一有效路）
        try:
            from astrbot.api.web import request as _proxy
            try:
                channel = str(_proxy.query.get("channel", "") or "")
            except Exception:
                pass
        except Exception:
            pass
    channel = (channel or "").strip()
    if channel not in UPDATE_CHANNELS:
        channel = _update_channel()
    # 旧单槽缓存（无 channel 键）直接丢弃重检
    if not isinstance(_LAST_CHECK_RES, dict):
        _LAST_CHECK_RES = {}
    if not isinstance(_LAST_CHECK_TIME, dict):
        _LAST_CHECK_TIME = {}
    if not isinstance(_CHECK_RUNNING_SINCE, dict):
        _CHECK_RUNNING_SINCE = {}
    repo = _channel_repo(channel)
    now = time.time()
    # 成功/失败分级缓存（按通道分槽隔离：双通道并查互不覆盖）
    _cached = _LAST_CHECK_RES.get(channel)
    if _cached is not None:
        _failed = bool(_cached.get("detect_error") or _cached.get("error"))
        _ttl = _CHECK_FAIL_TTL if _failed else _CHECK_CACHE_TTL
        if (now - _LAST_CHECK_TIME.get(channel, 0)) < _ttl:
            return no_cache_response(json_response(_cached))
    # 在途共享（同通道）：已有检测在跑则等候结果（8 秒），防并发惊群打 GitHub
    _t0 = now
    if _CHECK_RUNNING_SINCE.get(channel, 0) > 0 and (now - _CHECK_RUNNING_SINCE.get(channel, 0)) < _CHECK_RUNNING_TTL:
        try:
            for _ in range(16):
                await asyncio.sleep(0.5)
                if (_LAST_CHECK_TIME.get(channel, 0) > _t0 and _LAST_CHECK_RES.get(channel) is not None):
                    return no_cache_response(json_response(_LAST_CHECK_RES.get(channel)))
                if _CHECK_RUNNING_SINCE.get(channel, 0) <= 0:
                    break
        except Exception:
            pass
        now = time.time()
        _cached = _LAST_CHECK_RES.get(channel)
        if (_cached is not None
                and (now - _LAST_CHECK_TIME.get(channel, 0)) < _CHECK_CACHE_TTL):
            return no_cache_response(json_response(_cached))
    # 成为拥有者执行检测
    _CHECK_RUNNING_SINCE[channel] = time.time()
    try:
        try:
            res = await asyncio.to_thread(check_latest_version, plugin_base, repo)
        except Exception as e:
            res = {
                "current_version": _get_local_version(plugin_base),
                "latest_version": _get_local_version(plugin_base),
                "has_update": False,
                "error": str(e)
            }
        res["channel"] = channel
        res["repo"] = repo
        _LAST_CHECK_RES[channel] = res
        _LAST_CHECK_TIME[channel] = time.time()
    finally:
        _CHECK_RUNNING_SINCE[channel] = 0.0
    return no_cache_response(json_response(res))


async def handle_version_channel(request=None):
    """更新通道读写：GET 查当前；POST {channel: 正式/BETA} 切换（记忆进 recall，检测即时跟随）。
    取参全收：dict/body/query/官方 proxy（request=None 真机路），防桥转发形态差异致切换无效。"""
    try:
        data = None
        if isinstance(request, dict):
            data = request
        elif request is not None:
            try:
                data = await get_req_json(request, default={})
            except Exception:
                data = {}
        _c = ""
        try:
            if isinstance(data, dict) and str(data.get("channel") or "").strip() in UPDATE_CHANNELS:
                _c = str(data.get("channel")).strip()
        except Exception:
            pass
        if not _c:
            try:
                _q = get_req_query(request, "channel", "")
                if str(_q or "").strip() in UPDATE_CHANNELS:
                    _c = str(_q).strip()
            except Exception:
                pass
        if not _c:
            # 官方 proxy 直读（request=None 真机路；body/query 双收）
            try:
                from astrbot.api.web import request as _proxy
                try:
                    _jb = _proxy.json
                    if callable(_jb):
                        import inspect as _ins
                        _r = _jb(default={})
                        if _ins.isawaitable(_r):
                            _r = await _r
                        if isinstance(_r, dict) and str(_r.get("channel") or "").strip() in UPDATE_CHANNELS:
                            _c = str(_r.get("channel")).strip()
                except Exception:
                    pass
                if not _c:
                    try:
                        _pq = str(_proxy.query.get("channel", "") or "").strip()
                        if _pq in UPDATE_CHANNELS:
                            _c = _pq
                    except Exception:
                        pass
            except Exception:
                pass
        if _c in UPDATE_CHANNELS:
            try:
                ST.recall_set("update_channel", _c)
            except Exception:
                pass
    except Exception:
        pass
    return json_response({"ok": True, "channel": _update_channel(), "channels": list(UPDATE_CHANNELS)})
