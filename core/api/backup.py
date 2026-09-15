# -*- coding: utf-8 -*-
"""备份 API"""
import asyncio
import json as _json
import os
import time
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response

from .web_utils import _err, get_req_query, get_req_json, no_cache_response

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST


def _backup_base(plugin_base=""):
    if ST.BACKUP_DIR:
        return ST.BACKUP_DIR
    if hasattr(ST, "get_persistent_data_dir"):
        return os.path.join(ST.get_persistent_data_dir(plugin_base), "backups")
    if plugin_base:
        return os.path.join(plugin_base, "data", "backups")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "backups")


def _safe_backup(rel, base=""):
    b = base or _backup_base()
    p = os.path.abspath(os.path.join(b, str(rel or "").strip()))
    if p != b and not p.startswith(b + os.sep):
        return None
    return p


async def handle_backups_list(request, plugin_base=""):
    # 备份列表不再触发自动备份检查（自动备份只由 xb-auto-backup 守护线程执行，防WebUI每次点开雪崩）
    rel = get_req_query(request, "dir", "") or get_req_query(request, "path", "")
    root = _safe_backup(rel, _backup_base(plugin_base))
    if not root:
        return _err("bad dir", 400)
    if not os.path.isdir(root):
        return json_response({"dir": str(rel or ""), "dirs": [], "files": []})

    def _scan_backups():
        dirs, files = [], []
        base = _backup_base(plugin_base)
        try:
            with os.scandir(root) as it:
                for entry in it:
                    try:
                        name = entry.name
                        r = os.path.relpath(entry.path, base).replace(os.sep, "/")
                        if entry.is_dir(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)
                            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                            dirs.append({"name": name, "path": r, "mtime": mtime})
                        elif entry.is_file(follow_symlinks=False) and (name.endswith(".db") or name.endswith(".json")):
                            st = entry.stat(follow_symlinks=False)
                            sz = f"{st.st_size // 1024}KB"
                            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                            files.append({"name": name, "path": r, "size": sz, "mtime": mtime})
                    except Exception:
                        pass
        except Exception:
            pass
        dirs.sort(key=lambda x: x["name"], reverse=True)
        files.sort(key=lambda x: x["name"], reverse=True)
        return dirs, files

    dirs, files = await asyncio.to_thread(_scan_backups)
    # sidecar 可读性标记：前端在备份时间后提示文件锁防重保护
    sidecar = {"ok": False, "time": ""}
    try:
        _sp = ST._backup_sidecar_path() if hasattr(ST, "_backup_sidecar_path") else ""
        if _sp and os.path.isfile(_sp):
            sidecar["ok"] = True
            try:
                with open(_sp, "r", encoding="utf-8") as _f:
                    _d = _json.load(_f)
                _ts = float((_d or {}).get("ts", 0) or 0)
                if _ts:
                    sidecar["time"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(_ts))
            except Exception:
                pass
    except Exception:
        pass
    return no_cache_response(json_response({"dir": str(rel or ""), "dirs": dirs, "files": files, "sidecar": sidecar}))


async def handle_backups_restore(request, plugin_base=""):
    p = await get_req_json(request, default={})
    rel = str((p.get("path") or p.get("file") or "") if isinstance(p, dict) else "").strip()
    if not rel:
        rel = get_req_query(request, "path", "") or get_req_query(request, "file", "")
    rel = str(rel).strip()
    if rel == "__backup_now__":
        dst = await asyncio.to_thread(lambda: ST.backup_user_data(force=True))
        if dst:
            return json_response({"ok": True, "path": os.path.relpath(dst, _backup_base(plugin_base)).replace(os.sep, "/")})
        return _err("backup failed", 500)
    if not rel:
        return _err("path required", 400)
    src = _safe_backup(rel, _backup_base(plugin_base))
    if not src or not os.path.isfile(src) or not src.endswith(".db"):
        return _err("backup not found (need .db)", 404)

    def _work():
        import sqlite3
        cur_db = ST._DB
        with ST._LOCK:
            if hasattr(ST, "flush_all") and ST.flush_all() is False:
                raise RuntimeError("flush before restore failed")
            try:
                cur_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            cur_db.commit()
            if hasattr(ST, "close_read_conn"):
                ST.close_read_conn()
            src_conn = sqlite3.connect(src)
            try:
                src_conn.backup(cur_db)
            finally:
                src_conn.close()
            cur_db.commit()
            ST._ACC_CACHE.clear()
            ST._GROUP_CACHE.clear()
            try:
                ST._KV_CACHE.clear()
            except Exception:
                pass
            try:
                ST.reload_config_from_db()
            except Exception:
                pass
    try:
        await asyncio.to_thread(_work)
        return json_response({"ok": True, "path": rel, "msg": "备份恢复成功！数据已实时加载生效。"})
    except Exception as e:
        return _err(f"restore failed: {e}", 500)


async def handle_backups_delete(request, plugin_base=""):
    p = await get_req_json(request, default={})
    rel = str((p.get("path") or p.get("file") or p.get("dir") or "") if isinstance(p, dict) else "").strip()
    if not rel:
        rel = get_req_query(request, "path", "") or get_req_query(request, "file", "") or get_req_query(request, "dir", "")
    rel = str(rel).strip()
    if not rel:
        return _err("path required", 400)
    fp = _safe_backup(rel, _backup_base(plugin_base))
    if not fp or not os.path.exists(fp):
        return _err("path not found", 404)
    base = _backup_base(plugin_base)
    if os.path.abspath(fp) == os.path.abspath(base):
        return _err("cannot delete root", 400)
    try:
        import shutil
        if os.path.isfile(fp):
            os.remove(fp)
            if fp.endswith(".db") and os.path.isfile(fp + ".json"):
                try:
                    os.remove(fp + ".json")
                except Exception:
                    pass
        elif os.path.isdir(fp):
            shutil.rmtree(fp)
        return json_response({"ok": True, "path": rel})
    except Exception as e:
        return _err(f"delete failed: {e}", 500)


async def handle_backups_export(request, plugin_base=""):
    rel = get_req_query(request, "path", "") or get_req_query(request, "file", "")
    if not rel:
        try:
            p = await get_req_json(request, default={})
            if isinstance(p, dict):
                rel = str(p.get("path") or p.get("file") or "").strip()
        except Exception:
            pass
    fp = None
    base = _backup_base(plugin_base)
    if not rel:
        if os.path.isdir(base):
            for root, _, files in os.walk(base):
                for fn in sorted(files, reverse=True):
                    if fn.endswith(".db"):
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, base).replace(os.sep, "/")
                        break
                if fp:
                    break
    else:
        fp = _safe_backup(rel, base)
    if not fp or not os.path.exists(fp):
        return _err("backup file not found", 404)
    if os.path.isdir(fp):
        cands = [os.path.join(fp, x) for x in sorted(os.listdir(fp), reverse=True) if x.endswith(".db") and os.path.isfile(os.path.join(fp, x))]
        if cands:
            fp = cands[0]
            rel = os.path.relpath(fp, base).replace(os.sep, "/")
        else:
            return _err("file not found in directory", 404)
    def _work():
        if os.path.getsize(fp) > 50 * 1024 * 1024:
            raise ValueError("file too large")
        with open(fp, "rb") as f:
            data = f.read()
        import base64 as _b64
        return _b64.b64encode(data).decode(), len(data)
    try:
        is_raw = get_req_query(request, "raw", "") in ("1", "true", "yes") or get_req_query(request, "download", "") in ("1", "true", "yes")
        if not is_raw:
            try:
                p2 = await get_req_json(request, default={})
                if isinstance(p2, dict) and str(p2.get("raw", "")).strip() in ("1", "true", "yes"):
                    is_raw = True
            except Exception:
                pass
        b64, size = await asyncio.to_thread(_work)
        return json_response({"ok": True, "path": rel, "data": b64, "size": size, "filename": os.path.basename(fp)})
    except ValueError as e:
        return _err(str(e), 400)
    except Exception as e:
        return _err(f"export failed: {e}", 500)


async def handle_clear_all(request, plugin_base=""):
    try:
        p = await get_req_json(request, default={})
        if not isinstance(p, dict) or p.get("confirm") != "确认删除":
            return _err("need confirm=确认删除", 400)
        if p.get("confirm2") != "确认":
            return _err("need confirm2=确认", 400)

        def _work():
            with ST._LOCK:
                if ST._DB:
                    ST._DB.execute("DELETE FROM wallet")
                    ST._DB.execute("DELETE FROM accounts")
                    ST._DB.execute("DELETE FROM groups")
                    ST._DB.execute("DELETE FROM redpacks")
                    ST._DB.execute("DELETE FROM kv")
                    ST._DB.commit()
                    ST._ACC_CACHE.clear()
                    ST._GROUP_CACHE.clear()
                    # kv 内存缓存必须同步清空，否则开关/游戏锁/签到顺序等残留内存快照，清空后仍幽灵生效
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
            if hasattr(ST, "set_last_backup"):
                ST.set_last_backup(0)
            try:
                base = _backup_base(plugin_base)
                if os.path.isdir(base):
                    for root, _, files in os.walk(base):
                        for fn in files:
                            try:
                                os.remove(os.path.join(root, fn))
                            except Exception:
                                pass
            except Exception:
                pass
        await asyncio.to_thread(_work)
        return json_response({"cleared": True})
    except Exception as e:
        return _err(f"clear failed: {e}", 500)

async def handle_db_doctor(request, plugin_base=""):
    """执行数据库健康体检与碎片整理 (VACUUM + PRAGMA integrity_check + wal_checkpoint)"""
    try:
        if ST._DB is None:
            return _err("database not initialized", 500)

        # 1. 强制落盘脏数据
        try:
            ST.flush_all()
        except Exception:
            pass

        db_path = getattr(ST, "_DB_PATH", None) or os.path.join(plugin_base or _backup_base(plugin_base), "..", "xb.db")
        if not os.path.isfile(db_path):
            # 兼容默认 data/xb.db 或 data/nuli_slave.db / xbbot.db
            cands = [
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "xb.db"),
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "nuli_slave.db"),
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "xbbot.db"),
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "data.db")
            ]
            for c in cands:
                if os.path.isfile(c):
                    db_path = c
                    break

        wal_path = (db_path + "-wal") if (db_path and os.path.isfile(db_path + "-wal")) else ""
        
        size_before = 0
        if db_path and os.path.isfile(db_path):
            size_before += os.path.getsize(db_path)
        if wal_path and os.path.isfile(wal_path):
            size_before += os.path.getsize(wal_path)

        # 只读体检移入后台线程；VACUUM/TRUNCATE 等重型整理同样后台并 60s 熔断，
        # 避免 WebUI 一次体检卡死全群读写数秒
        def _check_work():
            with ST._LOCK:
                cur = ST._DB.cursor()

                # 3. 运行完整性检查
                cur.execute("PRAGMA integrity_check(10)")
                integrity_rows = cur.fetchall()
                integrity_status = "正常 (OK)" if (integrity_rows and integrity_rows[0][0] == "ok") else str(integrity_rows)

                # 4. 统计各表数据行数
                counts = {}
                for tbl in ("wallet", "accounts", "groups", "redpacks", "kv"):
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                        counts[tbl] = cur.fetchone()[0]
                    except Exception:
                        counts[tbl] = 0
            return integrity_status, counts

        integrity_status, counts = await asyncio.to_thread(_check_work)

        # 5. WAL 截断与 VACUUM 碎片整理（锁外独立连接，后台线程，超时 60s 熔断）
        import asyncio as _aio

        def _vacuum_work(path):
            import sqlite3 as _sql
            try:
                try:
                    from .. import storage as _ST
                except ImportError:
                    from core import storage as _ST  # type: ignore
                c = _sql.connect(path, timeout=getattr(_ST, "DB_TIMEOUT", 30.0))
                try:
                    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass
                try:
                    c.execute("PRAGMA optimize")
                except Exception:
                    pass
                try:
                    c.execute("VACUUM")
                except Exception:
                    pass
                try:
                    c.close()
                except Exception:
                    pass
                return True
            except Exception:
                return False

        try:
            if db_path and os.path.isfile(db_path):
                await _aio.wait_for(_aio.to_thread(_vacuum_work, db_path), timeout=60)
        except Exception:
            pass

        # 6. 统计整理后大小
        size_after = 0
        if db_path and os.path.isfile(db_path):
            size_after += os.path.getsize(db_path)
        if wal_path and os.path.isfile(wal_path):
            size_after += os.path.getsize(wal_path)

        def fmt_sz(s):
            if s <= 0: return "0 KB"
            if s < 1024 * 1024: return f"{s / 1024:.1f} KB"
            return f"{s / (1024 * 1024):.2f} MB"

        saved = max(0, size_before - size_after)

        return json_response({
            "ok": True,
            "integrity": integrity_status,
            "size_before": fmt_sz(size_before),
            "size_after": fmt_sz(size_after),
            "saved": fmt_sz(saved),
            "tables": counts,
            "msg": f"数据库健康体检完成！完整性状态：{integrity_status}，成功释放碎片空间：{fmt_sz(saved)}。"
        })
    except Exception as e:
        return _err(f"db doctor failed: {e}", 500)


# ---------- 全量配置快照已独立至 snapshots.py（本文件仅保留本地备份/体检/修剪/清库） ----------


async def handle_backups_prune(request, plugin_base=""):
    """按保留数量一键修剪本地 + WebDAV 远端旧备份（保存保留配置后即时生效）"""
    import asyncio
    try:
        keep = ST.cfgi("备份配置", "保留备份数量", 30)
    except Exception:
        keep = 30
    if keep <= 0:
        keep = 30
    local_deleted = 0
    try:
        local_deleted = int(ST.clean_old_backups(max_keep=keep) or 0)
    except Exception:
        local_deleted = 0
    remote_deleted = 0
    remote_msg = "未配置 WebDAV，跳过云端修剪"
    try:
        from .. import webdav as _wd
    except ImportError:
        try:
            from core import webdav as _wd
        except ImportError:
            _wd = None
    if _wd is not None:
        try:
            if _wd.is_enabled():
                ok, res = await asyncio.to_thread(_wd.prune_remote_backups, keep)
                remote_msg = str(res or "")
                if ok:
                    import re as _re
                    m = _re.search(r"清理\s*(\d+)", remote_msg)
                    if m:
                        remote_deleted = int(m.group(1))
            else:
                remote_msg = "WebDAV 未启用，仅修剪本地"
        except Exception as e:
            remote_msg = f"云端修剪异常: {e}"
    return json_response({
        "ok": True,
        "keep": keep,
        "local_deleted": local_deleted,
        "remote_deleted": remote_deleted,
        "remote_msg": remote_msg,
        "msg": f"保留最新 {keep} 份：本地清理 {local_deleted} 份，云端清理 {remote_deleted} 份",
    })
