# -*- coding: utf-8 -*-
"""
小白机器人 WebDAV 自动云备份模块 (零依赖纯标准库实现)
支持坚果云、Alist、InfiniCloud、Nextcloud、群晖/QNAP 等任意标准 WebDAV 服务
"""
import os
import ssl
import time
import base64
import threading
import urllib.request
import urllib.error
import urllib.parse
import email.utils
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

SHANGHAI_TZ = timezone(timedelta(hours=8))


def format_shanghai_time(dt_str, filename=""):
    """
    将 WebDAV 返回的 GMT/UTC 时间字符串 (如 RFC 1123 HTTP-date 或 ISO 8601)
    准确换算为中国标准时间（UTC+8 / 上海时区）并格式化为中文日期时间。
    若时间缺失或格式未知，尝试从备份文件名 (xbbot_YYYYMMDD_HHMMSS) 解析兜底。
    """
    s = str(dt_str or "").strip()
    if s:
        # 1. 尝试 RFC 1123 / RFC 822 (如 "Sun, 06 Sep 2026 05:25:30 GMT")
        try:
            dt = email.utils.parsedate_to_datetime(s)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(SHANGHAI_TZ).strftime("%Y年%m月%d日 %H:%M:%S")
        except Exception:
            pass

        # 2. 尝试 ISO 8601 (如 "2026-09-06T05:25:30Z")
        try:
            clean = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(SHANGHAI_TZ).strftime("%Y年%m月%d日 %H:%M:%S")
        except Exception:
            pass

    # 3. 兜底从文件名推导时间 (xbbot_20260906_132530.db)
    if filename:
        import re
        m = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", filename)
        if m:
            return f"{m.group(1)}年{m.group(2)}月{m.group(3)}日 {m.group(4)}:{m.group(5)}:{m.group(6)}"

    return s or "-"

try:
    from .. import storage as ST
    from . import logger as _logger
except ImportError:
    import storage as ST
    try:
        from core import logger as _logger
    except ImportError:
        _logger = None


def is_enabled():
    """检查 WebDAV 自动备份是否启用且配置完整"""
    sw = ST.cfg("备份配置", "WebDAV备份开关", "假").strip().lower()
    if sw not in ("真", "true", "1", "on", "yes"):
        return False
    url = ST.cfg("备份配置", "WebDAV服务器地址", "").strip()
    return bool(url)


def _clean_url(url):
    u = str(url or "").strip()
    if not u:
        return ""
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return u.rstrip("/")


def _get_auth_header(user, pwd):
    raw = f"{user}:{pwd}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _make_ssl_context():
    ctx = ssl.create_default_context()
    # 兼容私有 NAS 或自签名证书
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


_VERIFIED_REMOTE_DIRS = set()


def _ensure_remote_dir(base_url, remote_dir, auth, timeout=6):
    """递归检查并创建 WebDAV 远端多级目录 (MKCOL)，带内存去重防触发服务商 429 频控"""
    cache_key = f"{base_url}|{remote_dir}|{auth}"
    if cache_key in _VERIFIED_REMOTE_DIRS:
        return True
    parts = [p for p in remote_dir.strip("/").split("/") if p]
    cur_url = base_url.rstrip("/")
    for part in parts:
        cur_url = f"{cur_url}/{part}"
        try:
            # WebDAV 集合标准规定集合 URL 须以斜杠结尾，避免 301 重定向将 MKCOL 变更为 GET 导致目录未创建
            req = urllib.request.Request(f"{cur_url}/", method="MKCOL")
            req.add_header("Authorization", auth)
            req.add_header("User-Agent", "XBBot-WebDAV-Backup/1.0")
            with urllib.request.urlopen(req, timeout=timeout, context=_make_ssl_context()):
                pass
        except urllib.error.HTTPError as e:
            # 405 Method Not Allowed / 301 / 409 通常表示目录已存在，属于正常情况
            if e.code in (405, 301, 409, 200, 201):
                pass
            elif e.code == 429:
                # 触发服务商频控，通常目录已就绪，跳过后续以保护配额
                break
        except Exception:
            pass
    _VERIFIED_REMOTE_DIRS.add(cache_key)
    return True


def upload_backup(local_path):
    """
    同步上传单个本地备份文件到 WebDAV 远端
    :param local_path: 本地 .db 备份文件路径
    :return: (bool, str) 是否成功及详情信息
    """
    if not os.path.isfile(local_path):
        return False, f"本地文件不存在: {local_path}"

    raw_url = ST.cfg("备份配置", "WebDAV服务器地址", "").strip()
    if not raw_url:
        return False, "未配置 WebDAV 服务器地址"
    base_url = _clean_url(raw_url)
    user = ST.cfg("备份配置", "WebDAV用户名", "").strip()
    pwd = ST.cfg("备份配置", "WebDAV应用密码", "").strip()
    rdir = ST.cfg("备份配置", "WebDAV远端目录", "/xbbot_backup/").strip() or "/xbbot_backup/"

    auth = _get_auth_header(user, pwd)

    try:
        _ensure_remote_dir(base_url, rdir, auth, timeout=6)
    except Exception:
        pass

    fname = os.path.basename(local_path)
    clean_rdir = rdir.strip("/")
    target_url = f"{base_url}/{clean_rdir}/{fname}" if clean_rdir else f"{base_url}/{fname}"

    try:
        with open(local_path, "rb") as f:
            data = f.read()

        req = urllib.request.Request(target_url, data=data, method="PUT")
        req.add_header("Authorization", auth)
        req.add_header("Content-Type", "application/x-sqlite3")
        req.add_header("User-Agent", "XBBot-WebDAV-Backup/1.0")
        req.add_header("Content-Length", str(len(data)))

        with urllib.request.urlopen(req, timeout=25, context=_make_ssl_context()) as resp:
            status = getattr(resp, "status", getattr(resp, "code", 200))
            if status in (200, 201, 204):
                sz_kb = len(data) // 1024
                msg = f"WebDAV 备份成功上传: {fname} ({sz_kb} KB) -> {target_url}"
                if _logger:
                    _logger.info(msg)
                # 上传成功后按保留数量后台修剪远端旧归档（云端保留数与本地同配置）
                try:
                    async_prune_remote_backups()
                except Exception:
                    pass
                return True, msg
            return False, f"WebDAV 服务器返回非预期状态码: {status}"
    except urllib.error.HTTPError as e:
        if e.code == 429:
            msg = "WebDAV 上传触发服务商频控 (HTTP 429 Too Many Requests: 坚果云等限制频次，凭证正常，请稍候再试)"
        else:
            msg = f"WebDAV 上传 HTTP 错误 {e.code}: {e.reason}"
        if _logger:
            _logger.error(msg)
        return False, msg
    except (urllib.error.URLError, TimeoutError) as e:
        msg = f"WebDAV 上传网络超时或连接失败: {getattr(e, 'reason', e)}"
        if _logger:
            _logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"WebDAV 上传异常: {e}"
        if _logger:
            _logger.error(msg)
        return False, msg


def test_connection(url=None, user=None, pwd=None, rdir=None):
    """测试 WebDAV 连接与鉴权有效性 (支持直接传参或回退读取当前配置)"""
    raw_url = str(url if url is not None else ST.cfg("备份配置", "WebDAV服务器地址", "")).strip()
    if not raw_url:
        return False, "请先填写 WebDAV 服务器地址"
    base_url = _clean_url(raw_url)
    user = str(user if user is not None else ST.cfg("备份配置", "WebDAV用户名", "")).strip()
    pwd = str(pwd if pwd is not None else ST.cfg("备份配置", "WebDAV应用密码", "")).strip()
    rdir = str(rdir if rdir is not None else (ST.cfg("备份配置", "WebDAV远端目录", "/xbbot_backup/").strip() or "/xbbot_backup/")).strip()

    auth = _get_auth_header(user, pwd)

    # 1. 优先采用 RFC 4918 标准 OPTIONS 轻量探测（几乎所有 WebDAV 均支持，且不消耗目录列表配额，防坚果云 429 频控）
    try:
        req = urllib.request.Request(f"{base_url}/", method="OPTIONS")
        req.add_header("Authorization", auth)
        req.add_header("User-Agent", "XBBot-WebDAV-Backup/1.0")
        with urllib.request.urlopen(req, timeout=8, context=_make_ssl_context()) as resp:
            status = getattr(resp, "status", getattr(resp, "code", 200))
            if status in (200, 204):
                _ensure_remote_dir(base_url, rdir, auth, timeout=6)
                return True, f"WebDAV 连接与鉴权成功！(服务器状态: {status}, 远端目录: {rdir})"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "WebDAV 用户名或应用密码错误 (HTTP 401 Unauthorized)"
        if e.code == 403:
            return False, "WebDAV 拒绝访问 (HTTP 403 Forbidden)"
        if e.code == 404:
            return False, "WebDAV 服务器路径不存在 (HTTP 404 Not Found)"
        if e.code == 429:
            return False, "WebDAV 连接与鉴权正常，但触发服务商频控限制 (HTTP 429 Too Many Requests: 坚果云等限制频次，请等待 1-2 分钟后再试)"
        # 405 Method Not Allowed 或 501，继续回退 PROPFIND
    except (urllib.error.URLError, TimeoutError) as e:
        reason = getattr(e, 'reason', e)
        return False, f"WebDAV 连接超时或目标主机无法连接（8秒超时）: {reason}"
    except Exception:
        pass

    # 2. 回退 PROPFIND 探测
    try:
        req = urllib.request.Request(f"{base_url}/", method="PROPFIND")
        req.add_header("Authorization", auth)
        req.add_header("Depth", "0")
        req.add_header("User-Agent", "XBBot-WebDAV-Backup/1.0")
        with urllib.request.urlopen(req, timeout=8, context=_make_ssl_context()) as resp:
            status = getattr(resp, "status", getattr(resp, "code", 200))
            if status in (200, 207):
                _ensure_remote_dir(base_url, rdir, auth, timeout=6)
                return True, f"WebDAV 连接与鉴权成功！(PROPFIND 响应: {status}, 远端目录: {rdir})"
            return False, f"WebDAV 响应非预期状态码: {status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "WebDAV 用户名或应用密码错误 (HTTP 401 Unauthorized)"
        if e.code == 403:
            return False, "WebDAV 拒绝访问 (HTTP 403 Forbidden)"
        if e.code == 404:
            return False, "WebDAV 服务器路径不存在 (HTTP 404 Not Found)"
        if e.code == 429:
            return False, "WebDAV 连接与鉴权正常，但触发服务商频控限制 (HTTP 429 Too Many Requests: 坚果云等限制频次，请等待 1-2 分钟后再试)"
        return False, f"WebDAV HTTP 错误 {e.code}: {e.reason}"
    except (urllib.error.URLError, TimeoutError) as e:
        reason = getattr(e, 'reason', e)
        return False, f"WebDAV 连接超时或目标主机无法连接（8秒超时）: {reason}"
    except Exception as e:
        return False, f"WebDAV 连接异常: {e}"


def async_upload_backup(local_path):
    """异步后台上传备份文件，绝不阻塞主消息链路"""
    if not is_enabled():
        return
    def _worker():
        try:
            upload_backup(local_path)
        except Exception:
            pass
    t = threading.Thread(target=_worker, name="WebDAV-Upload", daemon=True)
    t.start()


def list_remote_files(url=None, user=None, pwd=None, rdir=None, timeout=12):
    """
    列出 WebDAV 远端备份目录中的所有备份文件 (PROPFIND Depth: 1)
    :return: (bool, list[dict] 或 str 错误提示)
    """
    raw_url = str(url if url is not None else ST.cfg("备份配置", "WebDAV服务器地址", "")).strip()
    if not raw_url:
        return False, "请先填写 WebDAV 服务器地址"
    base_url = _clean_url(raw_url)
    user = str(user if user is not None else ST.cfg("备份配置", "WebDAV用户名", "")).strip()
    pwd = str(pwd if pwd is not None else ST.cfg("备份配置", "WebDAV应用密码", "")).strip()
    rdir = str(rdir if rdir is not None else (ST.cfg("备份配置", "WebDAV远端目录", "/xbbot_backup/").strip() or "/xbbot_backup/")).strip()
    auth = _get_auth_header(user, pwd)

    clean_rdir = rdir.strip("/")
    target_url = f"{base_url}/{clean_rdir}/" if clean_rdir else f"{base_url}/"

    body = (
        '<?xml version="1.0" encoding="utf-8" ?>\n'
        '<D:propfind xmlns:D="DAV:">\n'
        '  <D:prop>\n'
        '    <D:displayname/>\n'
        '    <D:getcontentlength/>\n'
        '    <D:getlastmodified/>\n'
        '    <D:resourcetype/>\n'
        '  </D:prop>\n'
        '</D:propfind>'
    ).encode("utf-8")

    try:
        req = urllib.request.Request(target_url, data=body, method="PROPFIND")
        req.add_header("Authorization", auth)
        req.add_header("Depth", "1")
        req.add_header("Content-Type", "application/xml; charset=utf-8")
        req.add_header("User-Agent", "XBBot-WebDAV-Backup/1.0")

        with urllib.request.urlopen(req, timeout=timeout, context=_make_ssl_context()) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return True, []  # 远端目录尚不存在或为空
        if e.code == 401:
            return False, "WebDAV 用户名或应用密码错误 (HTTP 401 Unauthorized)"
        if e.code == 403:
            return False, "WebDAV 拒绝访问 (HTTP 403 Forbidden)"
        if e.code == 429:
            return False, "WebDAV 触发服务商频控限制 (HTTP 429: 坚果云等限制并发频次，请稍候重试)"
        return False, f"WebDAV HTTP 错误 {e.code}: {e.reason}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"WebDAV 列表连接超时或网络失败: {getattr(e, 'reason', e)}"
    except Exception as e:
        return False, f"WebDAV 列表读取异常: {e}"

    try:
        root = ET.fromstring(data)
    except Exception as e:
        return False, f"WebDAV XML 解析失败: {e}"

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    files = []
    # 提取所有 response 节点
    for resp_el in root.iter():
        if _strip_ns(resp_el.tag).lower() != "response":
            continue

        href = ""
        is_collection = False
        display_name = ""
        content_length = 0
        last_modified = ""

        for child in resp_el.iter():
            ntag = _strip_ns(child.tag).lower()
            if ntag == "href":
                href = (child.text or "").strip()
            elif ntag == "collection":
                is_collection = True
            elif ntag == "displayname":
                display_name = (child.text or "").strip()
            elif ntag == "getcontentlength":
                try:
                    content_length = int((child.text or "0").strip())
                except Exception:
                    content_length = 0
            elif ntag == "getlastmodified":
                last_modified = (child.text or "").strip()

        if is_collection:
            continue  # 忽略目录本身及子目录

        raw_name = urllib.parse.unquote(display_name or os.path.basename(href.rstrip("/")))
        if not raw_name or raw_name.startswith("."):
            continue

        # 格式化文件大小
        if content_length < 1024:
            sz_str = f"{content_length} B"
        elif content_length < 1024 * 1024:
            sz_str = f"{content_length // 1024} KB"
        else:
            sz_str = f"{content_length / (1024 * 1024):.1f} MB"

        files.append({
            "name": raw_name,
            "href": href,
            "size": sz_str,
            "raw_size": content_length,
            "mtime": format_shanghai_time(last_modified, raw_name),
            "raw_mtime": last_modified
        })

    # 优先按备份文件名字序降序排列（xbbot_YYYYMMDD_HHMMSS 格式天然有序）
    files.sort(key=lambda x: x["name"], reverse=True)
    return True, files


def download_remote_file(remote_name, local_dest=None, url=None, user=None, pwd=None, rdir=None, timeout=30):
    """
    从 WebDAV 远端下载指定备份文件
    :param remote_name: 远端文件名 (例如 xbbot_20260906_120000.db)
    :param local_dest: 本地目标保存绝对路径 (None 则保存至 data/backups/downloads/)
    :return: (bool, 本地文件路径或错误信息)
    """
    raw_url = str(url if url is not None else ST.cfg("备份配置", "WebDAV服务器地址", "")).strip()
    if not raw_url:
        return False, "未配置 WebDAV 服务器地址"
    base_url = _clean_url(raw_url)
    user = str(user if user is not None else ST.cfg("备份配置", "WebDAV用户名", "")).strip()
    pwd = str(pwd if pwd is not None else ST.cfg("备份配置", "WebDAV应用密码", "")).strip()
    rdir = str(rdir if rdir is not None else (ST.cfg("备份配置", "WebDAV远端目录", "/xbbot_backup/").strip() or "/xbbot_backup/")).strip()
    auth = _get_auth_header(user, pwd)

    clean_rdir = rdir.strip("/")
    clean_name = str(remote_name or "").strip().lstrip("/")
    if "/" in clean_name:
        clean_name = os.path.basename(clean_name)
    if not clean_name:
        return False, "未指定远端文件名"

    target_url = f"{base_url}/{clean_rdir}/{clean_name}" if clean_rdir else f"{base_url}/{clean_name}"

    if not local_dest:
        bdir = ST.BACKUP_DIR or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "backups")
        dl_dir = os.path.join(bdir, "downloads")
        os.makedirs(dl_dir, exist_ok=True)
        local_dest = os.path.join(dl_dir, clean_name)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(local_dest)), exist_ok=True)

    tmp_dest = local_dest + f".part_{int(time.time())}"
    try:
        req = urllib.request.Request(target_url, method="GET")
        req.add_header("Authorization", auth)
        req.add_header("User-Agent", "XBBot-WebDAV-Backup/1.0")

        with urllib.request.urlopen(req, timeout=timeout, context=_make_ssl_context()) as resp:
            status = getattr(resp, "status", getattr(resp, "code", 200))
            if status != 200:
                return False, f"WebDAV 服务器返回状态码: {status}"
            with open(tmp_dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)

        if not os.path.isfile(tmp_dest) or os.path.getsize(tmp_dest) == 0:
            if os.path.exists(tmp_dest):
                os.remove(tmp_dest)
            return False, "下载文件为空"

        if os.path.exists(local_dest):
            try:
                os.remove(local_dest)
            except Exception:
                pass
        os.replace(tmp_dest, local_dest)
        return True, local_dest
    except urllib.error.HTTPError as e:
        if os.path.exists(tmp_dest):
            try:
                os.remove(tmp_dest)
            except Exception:
                pass
        if e.code == 404:
            return False, f"WebDAV 远端文件不存在 (HTTP 404): {clean_name}"
        if e.code == 429:
            return False, "WebDAV 下载触发服务商频控 (HTTP 429: 坚果云等限制频次，请稍候重试)"
        return False, f"WebDAV 下载 HTTP 错误 {e.code}: {e.reason}"
    except Exception as e:
        if os.path.exists(tmp_dest):
            try:
                os.remove(tmp_dest)
            except Exception:
                pass
        return False, f"WebDAV 下载异常: {e}"


def delete_remote_file(remote_name, url=None, user=None, pwd=None, rdir=None, timeout=15):
    """
    从 WebDAV 远端删除指定备份文件 (HTTP DELETE)
    :param remote_name: 远端文件名 (例如 xbbot_20260906_120000.db)
    :return: (bool, str) 是否成功及提示信息
    """
    raw_url = str(url if url is not None else ST.cfg("备份配置", "WebDAV服务器地址", "")).strip()
    if not raw_url:
        return False, "未配置 WebDAV 服务器地址"
    base_url = _clean_url(raw_url)
    user = str(user if user is not None else ST.cfg("备份配置", "WebDAV用户名", "")).strip()
    pwd = str(pwd if pwd is not None else ST.cfg("备份配置", "WebDAV应用密码", "")).strip()
    rdir = str(rdir if rdir is not None else (ST.cfg("备份配置", "WebDAV远端目录", "/xbbot_backup/").strip() or "/xbbot_backup/")).strip()
    auth = _get_auth_header(user, pwd)

    clean_rdir = rdir.strip("/")
    clean_name = str(remote_name or "").strip().lstrip("/")
    if "/" in clean_name:
        clean_name = os.path.basename(clean_name)
    if not clean_name:
        return False, "未指定待删除远端文件名"

    target_url = f"{base_url}/{clean_rdir}/{clean_name}" if clean_rdir else f"{base_url}/{clean_name}"

    try:
        req = urllib.request.Request(target_url, method="DELETE")
        req.add_header("Authorization", auth)
        req.add_header("User-Agent", "XBBot-WebDAV-Backup/1.0")

        with urllib.request.urlopen(req, timeout=timeout, context=_make_ssl_context()) as resp:
            status = getattr(resp, "status", getattr(resp, "code", 200))
            if status in (200, 204, 202):
                msg = f"已成功从 WebDAV 远端删除备份文件: {clean_name}"
                if _logger:
                    _logger.info(msg)
                return True, msg
            return False, f"WebDAV 服务器返回状态码: {status}"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return True, f"远端文件已不存在或已被删除: {clean_name}"
        if e.code == 429:
            return False, "WebDAV 删除触发服务商频控 (HTTP 429: 坚果云等限制频次，请稍候重试)"
        return False, f"WebDAV 删除 HTTP 错误 {e.code}: {e.reason}"
    except Exception as e:
        return False, f"WebDAV 删除异常: {e}"


def prune_remote_backups(keep=None):
    """
    按保留数量修剪 WebDAV 远端备份（只处理 xbbot_*.db，留新删旧）。
    :param keep: 保留份数（None 则读 备份配置/保留备份数量，默认 30）
    :return: (bool, str) 是否成功及详情
    """
    try:
        keep = int(float(keep)) if keep not in (None, "") else int(float(ST.cfg("备份配置", "保留备份数量", "30")))
    except Exception:
        keep = 30
    if keep <= 0:
        keep = 30
    ok, res = list_remote_files()
    if not ok:
        return False, str(res or "获取远端列表失败")
    if not isinstance(res, list):
        return False, "远端列表格式异常"
    cands = [f for f in res
             if isinstance(f, dict)
             and str(f.get("name", "")).endswith(".db")
             and os.path.basename(str(f.get("name", ""))).startswith("xbbot_")]
    if len(cands) <= keep:
        return True, f"远端共 {len(cands)} 份归档，未超保留数 {keep}，无需清理"
    # 列表已按文件名降序（新→旧），超出的尾部即最旧
    excess = cands[keep:]
    deleted = 0
    for f in excess:
        try:
            okd, _ = delete_remote_file(str(f.get("name", "")))
            if okd:
                deleted += 1
        except Exception:
            pass
    return True, f"远端保留最新 {keep} 份，清理 {deleted}/{len(excess)} 份旧归档"


def async_prune_remote_backups(keep=None):
    """后台线程修剪远端，绝不阻塞调用方（上传成功后自动跟进）"""
    def _worker():
        try:
            prune_remote_backups(keep)
        except Exception:
            pass
    try:
        t = threading.Thread(target=_worker, name="WebDAV-Prune", daemon=True)
        t.start()
    except Exception:
        pass


