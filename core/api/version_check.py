"""version_check API - 在线版本检测（原 stats.py updater 段独立，端点不变）"""
# -*- coding: utf-8 -*-
import json
import time
import urllib.request
from ..adapters import json_response
from .web_utils import no_cache_response
from ..version import parse_version_tuple as _parse_version_tuple


# ==================== 在线版本检测（原 updater.py 并入） ====================
GITHUB_REPO = "imsuperone/xb"
GITHUB_REPO_XBTEST = "imsuperone/xbtest"  # BETA 通道：快照版跟踪仓


def _get_local_version(plugin_base=""):
    """本地版本：委托 version.py 单源（读 metadata.yaml）。"""
    from ..version import get_version as _gv
    return _gv(plugin_base)


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


def handle_version_get(req=None):
    """返回当前插件版本号，单源于 metadata.yaml"""
    v = _get_local_version()
    return no_cache_response(json_response({
        "ok": True,
        "status": "ok",
        "version": v,
        "plugin": "astrbot_plugin_xbbot_beta",
    }))

