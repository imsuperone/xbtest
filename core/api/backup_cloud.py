# -*- coding: utf-8 -*-
"""云备份 API — WebDAV 测试/备份/文件/恢复/删除（由 backup.py 独立拆出，端点不变）。"""
import asyncio
import os
import time
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response

from .web_utils import _err, get_req_query, get_req_json

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST


from .backup import _backup_base, _safe_backup


async def handle_webdav_test(request):
    """测试 WebDAV 连接（完全异步化，绝不阻塞主事件循环，支持动态参数与回退读取配置）"""
    import asyncio
    try:
        from .. import webdav as _wd
    except ImportError:
        try:
            from core import webdav as _wd
        except ImportError:
            return _err("WebDAV 模块未加载", 500)
    try:
        p = await get_req_json(request, default={})
        url = (p.get("url") if isinstance(p, dict) else None) or get_req_query(request, "url", None)
        user = (p.get("user") if isinstance(p, dict) else None) or get_req_query(request, "user", None)
        # 密码只走 POST body：禁 query 明文进日志/代理留痕（前端已是 apiPost）
        pwd = (p.get("pwd") if isinstance(p, dict) else None)
        rdir = (p.get("dir") if isinstance(p, dict) else None) or get_req_query(request, "dir", None)
        ok, msg = await asyncio.to_thread(_wd.test_connection, url, user, pwd, rdir)
        return json_response({"ok": ok, "msg": msg})
    except Exception as e:
        return _err(f"WebDAV 测试异常: {e}", 500)


async def handle_webdav_backup_now(request, plugin_base=""):
    """立即备份并上传至 WebDAV（完全异步化，绝不阻塞主事件循环；支持指定选中文件）"""
    import asyncio
    p = await get_req_json(request, default={})
    target_path = str((p.get("path") if isinstance(p, dict) else "") or get_req_query(request, "path", "")).strip()

    def _worker():
        dst = None
        base = _backup_base(plugin_base)
        if target_path and target_path != "__backup_now__":
            real_p = _safe_backup(target_path, base)
            if real_p and os.path.isfile(real_p) and (real_p.endswith(".db") or real_p.endswith(".json")):
                dst = real_p
        if not dst:
            # 传 auto_upload=False 避免内部后台线程重复触发上传
            dst = ST.backup_user_data(force=True, auto_upload=False)
        if not dst or not os.path.isfile(dst):
            return False, "本地备份生成或定位失败", None
        try:
            from .. import webdav as _wd
        except ImportError:
            from core import webdav as _wd
        ok, msg = _wd.upload_backup(dst)
        return ok, msg, os.path.basename(dst)
    try:
        ok, msg, fname = await asyncio.to_thread(_worker)
        if not fname:
            return _err(msg or "本地备份生成失败", 500)
        return json_response({"ok": ok, "msg": msg, "file": fname})
    except Exception as e:
        return _err(f"WebDAV 备份异常: {e}", 500)


async def handle_webdav_files(request):
    """获取 WebDAV 远端目录中的备份文件列表（完全异步化，绝不阻塞主事件循环）"""
    import asyncio
    try:
        from .. import webdav as _wd
    except ImportError:
        try:
            from core import webdav as _wd
        except ImportError:
            return _err("WebDAV 模块未加载", 500)
    try:
        p = await get_req_json(request, default={})
        url = (p.get("url") if isinstance(p, dict) else None) or get_req_query(request, "url", None)
        user = (p.get("user") if isinstance(p, dict) else None) or get_req_query(request, "user", None)
        # 密码只走 POST body：禁 query 明文进日志/代理留痕
        pwd = (p.get("pwd") if isinstance(p, dict) else None)
        rdir = (p.get("dir") if isinstance(p, dict) else None) or get_req_query(request, "dir", None)
        ok, res = await asyncio.to_thread(_wd.list_remote_files, url, user, pwd, rdir)
        if not ok:
            return _err(str(res or "获取远端列表失败"), 500)
        return json_response({"ok": True, "files": res if isinstance(res, list) else [], "count": len(res) if isinstance(res, list) else 0})
    except Exception as e:
        return _err(f"WebDAV 列表查询异常: {e}", 500)


async def handle_webdav_restore(request, plugin_base=""):
    """从 WebDAV 远端备份快捷热恢复（完全异步下载，主锁内原子无损热加载）"""
    import asyncio
    import sqlite3
    try:
        from .. import webdav as _wd
    except ImportError:
        try:
            from core import webdav as _wd
        except ImportError:
            return _err("WebDAV 模块未加载", 500)

    p = await get_req_json(request, default={})
    file_name = str((p.get("file") if isinstance(p, dict) else "") or (p.get("name") if isinstance(p, dict) else "") or get_req_query(request, "file", "")).strip()
    if not file_name:
        return _err("缺少待恢复文件名 (file)", 400)
    clean_name = os.path.basename(file_name)
    if not clean_name.lower().endswith(".db"):
        return _err("仅支持从 .db 格式的数据库备份恢复", 400)

    # 1. 异步下载远端备份文件至本地 downloads 目录
    ok, dl_res = await asyncio.to_thread(_wd.download_remote_file, clean_name)
    if not ok or not dl_res or not os.path.isfile(dl_res):
        return _err(f"从 WebDAV 下载备份失败: {dl_res}", 500)

    # 2. 验证 SQLite 数据库完整性与有效性
    try:
        with open(dl_res, "rb") as f:
            header = f.read(16)
        if header != b"SQLite format 3\x00":
            return _err("下载的文件不是有效的 SQLite 数据库文件", 400)
    except Exception as e:
        return _err(f"校验下载文件失败: {e}", 400)

    # 3. 恢复入库（原子事务持锁备份与缓存清空）
    def _do_restore():
        cur_db = ST._DB
        with ST._LOCK:
            if hasattr(ST, "flush_all") and ST.flush_all() is False:
                raise RuntimeError("flush before restore failed")
            try:
                cur_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            cur_db.commit()
            src_conn = sqlite3.connect(dl_res)
            try:
                if hasattr(ST, "close_read_conn"):
                    ST.close_read_conn()
                src_conn.backup(cur_db)
            finally:
                src_conn.close()
            cur_db.commit()
            ST._ACC_CACHE.clear()
            ST._GROUP_CACHE.clear()
            try:
                if hasattr(ST, "_KV_CACHE_LOCK"):
                    with ST._KV_CACHE_LOCK:
                        ST._KV_CACHE.clear()
                else:
                    ST._KV_CACHE.clear()
            except Exception:
                pass
            try:
                ST.reload_config_from_db()
            except Exception:
                pass
        # 恢复后尝试将刚下载的云端备份放入今日备份目录，方便本地留痕
        try:
            today_dir = os.path.join(_backup_base(plugin_base), time.strftime("%Y-%m-%d"))
            os.makedirs(today_dir, exist_ok=True)
            import shutil
            local_arch = os.path.join(today_dir, f"cloud_{clean_name}")
            if not os.path.exists(local_arch):
                shutil.copy2(dl_res, local_arch)
        except Exception:
            pass
        return True

    try:
        await asyncio.to_thread(_do_restore)
        return json_response({"ok": True, "file": clean_name, "msg": f"WebDAV 远端备份 [{clean_name}] 恢复成功！数据与配置已全量生效。"})
    except Exception as e:
        return _err(f"恢复远端备份失败: {e}", 500)


async def handle_webdav_delete(request, plugin_base=""):
    """删除 WebDAV 远端指定备份文件（完全异步化，绝不阻塞主事件循环）"""
    import asyncio
    try:
        from .. import webdav as _wd
    except ImportError:
        try:
            from core import webdav as _wd
        except ImportError:
            return _err("WebDAV 模块未加载", 500)

    p = await get_req_json(request, default={})
    file_name = str((p.get("file") if isinstance(p, dict) else "") or (p.get("name") if isinstance(p, dict) else "") or get_req_query(request, "file", "")).strip()
    if not file_name:
        return _err("缺少待删除文件名 (file)", 400)
    clean_name = os.path.basename(file_name)
    try:
        ok, msg = await asyncio.to_thread(_wd.delete_remote_file, clean_name)
        if not ok:
            return _err(msg or "删除远端备份失败", 500)
        return json_response({"ok": True, "file": clean_name, "msg": msg or f"已成功从云端删除备份文件 [{clean_name}]"})
    except Exception as e:
        return _err(f"删除云端备份异常: {e}", 500)
