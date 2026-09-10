# -*- coding: utf-8 -*-
"""小白机器人 - 在线版本检测引擎 (标准 GitHub Release / 国内加速镜像适配)"""
import re
import json
import time
import urllib.request
import urllib.error
try:
    from astrbot.api.web import json_response
except ImportError:
    def json_response(data, status=200):
        return data
from .web_utils import _err, no_cache_response

GITHUB_REPO = "imsuperone/xb"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_LAST_CHECK_RES = None
_LAST_CHECK_TIME = 0.0
_CHECK_CACHE_TTL = 300.0  # 成功结果缓存 5 分钟：版本不变时不再打 GitHub，防 RateLimit
_CHECK_FAIL_TTL = 60.0  # 失败结果缓存 1 分钟：网络故障时不再每点每试
_CHECK_RUNNING_SINCE = 0.0  # 在途检测开始时间戳（>0 表示有检测正在跑，并发请求共享结果，防惊群）
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
    return "0.7.44"


def _parse_version_tuple(v_str):
    """纪元比较：委托 version.parse_version_tuple（单源），失败走本地同逻辑兜底。"""
    try:
        try:
            from ..version import parse_version_tuple as _pvt
        except ImportError:
            from core.version import parse_version_tuple as _pvt  # type: ignore
        return _pvt(v_str)
    except Exception:
        pass
    m = re.findall(r"\d+", str(v_str or ""))
    nums = [int(x) for x in m] if m else [0, 0, 0]
    while len(nums) < 3:
        nums.append(0)
    major, minor, patch = nums[0], nums[1], nums[2]
    epoch = 0 if (major == 0 and 10 <= minor <= 68) else 1
    return (epoch, major, minor, patch)





def check_latest_version(plugin_base=""):
    """
    双通道检测最新版本：
    1. GitHub Releases 接口 (官方标准发版，带版本日志与元数据)
    2. GitHub main 分支 metadata.yaml (实时 Git 提交版本，支持多镜像加速容灾)
    择优选取版本号最高者，并与本地版本进行纪元元组比较。
    """
    local_ver = _get_local_version(plugin_base)
    headers = {
        "User-Agent": "XbBot-AutoUpdater/1.0",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. 优先尝试检测 main 分支 metadata.yaml（多镜像加速容灾；3 镜像×2 秒=最坏 6 秒，
    # 加 Releases 4 秒共 10 秒，低于前端 20 秒熔断；慢代理镜像已剔除）
    main_ver = ""
    ts = int(time.time())
    raw_meta_urls = [
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/metadata.yaml",
        f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO}@main/metadata.yaml?_t={ts}",
        f"https://fastly.jsdelivr.net/gh/{GITHUB_REPO}@main/metadata.yaml?_t={ts}"
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
        req = urllib.request.Request(API_URL, headers=headers)
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
    """从云端检测是否有最新 Release 或 main 分支版本（完全异步化，绝不阻塞主事件循环）"""
    global _LAST_CHECK_RES, _LAST_CHECK_TIME, _CHECK_RUNNING_SINCE
    import asyncio
    now = time.time()
    # 成功/失败分级缓存
    if _LAST_CHECK_RES is not None:
        _failed = bool(_LAST_CHECK_RES.get("detect_error") or _LAST_CHECK_RES.get("error"))
        _ttl = _CHECK_FAIL_TTL if _failed else _CHECK_CACHE_TTL
        if (now - _LAST_CHECK_TIME) < _ttl:
            return no_cache_response(json_response(_LAST_CHECK_RES))
    # 在途共享：已有检测在跑则等候结果（8 秒），防并发惊群打 GitHub
    _t0 = now
    if _CHECK_RUNNING_SINCE > 0 and (now - _CHECK_RUNNING_SINCE) < _CHECK_RUNNING_TTL:
        try:
            for _ in range(16):
                await asyncio.sleep(0.5)
                if _LAST_CHECK_TIME > _t0 and _LAST_CHECK_RES is not None:
                    return no_cache_response(json_response(_LAST_CHECK_RES))
                if _CHECK_RUNNING_SINCE <= 0:
                    break
        except Exception:
            pass
        now = time.time()
        if _LAST_CHECK_RES is not None and (now - _LAST_CHECK_TIME) < _CHECK_CACHE_TTL:
            return no_cache_response(json_response(_LAST_CHECK_RES))
    # 成为拥有者执行检测
    _CHECK_RUNNING_SINCE = time.time()
    try:
        try:
            res = await asyncio.to_thread(check_latest_version, plugin_base)
        except Exception as e:
            res = {
                "current_version": _get_local_version(plugin_base),
                "latest_version": _get_local_version(plugin_base),
                "has_update": False,
                "error": str(e)
            }
        _LAST_CHECK_RES = res
        _LAST_CHECK_TIME = time.time()
    finally:
        _CHECK_RUNNING_SINCE = 0.0
    return no_cache_response(json_response(res))
