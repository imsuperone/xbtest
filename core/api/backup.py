# -*- coding: utf-8 -*-
"""备份 API"""
import asyncio
import json as _json
import os
import time
try:
    from astrbot.api.web import json_response
except ImportError:
    def json_response(data, status=200):
        return data

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
    dirs, files = [], []
    base = _backup_base(plugin_base)
    for name in sorted(os.listdir(root)):
        f = os.path.join(root, name)
        r = os.path.relpath(f, base).replace(os.sep, "/")
        if os.path.isdir(f):
            try:
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
            except Exception:
                mtime = ""
            dirs.append({"name": name, "path": r, "mtime": mtime})
        elif os.path.isfile(f) and (name.endswith(".db") or name.endswith(".json")):
            try:
                sz = f"{os.path.getsize(f)//1024}KB"
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
            except Exception:
                sz = ""; mtime = ""
            files.append({"name": name, "path": r, "size": sz, "mtime": mtime})
    dirs.sort(key=lambda x: x["name"], reverse=True)
    files.sort(key=lambda x: x["name"], reverse=True)
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
            try:
                ST.flush_all()
            except Exception:
                pass
            try:
                cur_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            cur_db.commit()
            src_conn = sqlite3.connect(src)
            src_conn.backup(cur_db)
            src_conn.close()
            cur_db.commit()
            ST._ACC_CACHE.clear()
            ST._GROUP_CACHE.clear()
            try:
                ST._KV_CACHE.clear()
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
                    ST._last_backup = 0
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


# ---------- 全量配置快照（一键恢复）：存 kv/DB，独立于 AstrBot 配置体系 ----------
_CFG_SNAP_MAX = 5


def _snap_index():
    try:
        raw = ST.recall_get("cfgsnap__index", "[]")
        idx = _json.loads(raw or "[]")
        return [str(x) for x in idx] if isinstance(idx, list) else []
    except Exception:
        return []


def _snap_name(prefix=""):
    """毫秒精度快照名，同毫秒连存自动加 -1/-2 后缀，防同名覆盖"""
    base = time.strftime("%Y%m%d_%H%M%S", time.localtime()) + "_%03d" % (int(time.time() * 1000) % 1000)
    name = (prefix + base) if prefix else base
    try:
        idx = set(_snap_index())
        i = 1
        cand = name
        while cand in idx or ST.recall_get("cfgsnap__" + cand, ""):
            cand = "%s-%d" % (name, i)
            i += 1
        return cand
    except Exception:
        return name


def _snap_index_save(idx):
    try:
        keep = [str(x) for x in (idx or [])][: _CFG_SNAP_MAX]
        ST.recall_set("cfgsnap__index", _json.dumps(keep, ensure_ascii=False))
        # 清理被挤出索引的孤儿快照行 + 扶正 latest（防 kv 无限堆积，旧库一次自愈）
        try:
            if ST._DB is not None:
                with ST._LOCK:
                    if keep:
                        _ph = ",".join("?" * len(keep))
                        _sql = ("DELETE FROM kv WHERE k LIKE 'cfgsnap\\_\\_%' ESCAPE '\\' "
                                "AND k NOT IN ('cfgsnap__index','cfgsnap__latest') "
                                "AND k NOT IN (" + _ph + ")")
                        ST._DB.execute(
                            _sql,
                            ["cfgsnap__" + k for k in keep])
                    ST._safe_commit()
            try:
                _latest = str(ST.recall_get("cfgsnap__latest", "") or "")
                if _latest and _latest not in keep:
                    ST.recall_set("cfgsnap__latest", keep[0] if keep else "")
            except Exception:
                pass
            try:
                if hasattr(ST, "_KV_CACHE_LOCK"):
                    with ST._KV_CACHE_LOCK:
                        for k in list(ST._KV_CACHE.keys()):
                            if k.startswith("cfgsnap__") and k not in ("cfgsnap__index", "cfgsnap__latest") and k[9:] not in keep:
                                ST._KV_CACHE.pop(k, None)
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        pass


def auto_snapshot_if_changed():
    """配置保存后自动留快照：与最新一份一致则跳过，防内部保存刷屏"""
    try:
        cfg = getattr(ST, "_CONFIG", {}) or {}
        data = _json.dumps({"at": int(time.time()), "config": cfg}, ensure_ascii=False, default=str)
        idx = _snap_index()
        if idx:
            try:
                latest = ST.recall_get("cfgsnap__" + idx[0], "")
                if latest and _json.loads(latest).get("config") == _json.loads(data).get("config"):
                    return
            except Exception:
                pass
        name = _snap_name()
        ST.recall_set("cfgsnap__" + name, data)
        ST.recall_set("cfgsnap__latest", name)
        _snap_index_save([name] + [x for x in idx if x != name])
    except Exception:
        pass


async def handle_cfg_snapshots(request, plugin_base=""):
    """列出配置快照"""
    try:
        idx = _snap_index()
        out = []
        for name in idx:
            try:
                raw = ST.recall_get("cfgsnap__" + name, "")
                d = _json.loads(raw) if raw else {}
                secs = sorted((d.get("config") or {}).keys()) if isinstance(d, dict) else []
            except Exception:
                secs = []
            out.append({"name": name, "sections": secs})
        return json_response({"ok": True, "snapshots": out})
    except Exception as e:
        return _err(f"snapshots failed: {e}", 500)


async def handle_cfg_snapshot_save(request, plugin_base=""):
    """立即快照当前全量配置（含必要配置与用户全部自定义）"""
    try:
        cfg = getattr(ST, "_CONFIG", {}) or {}
        data = _json.dumps({"at": int(time.time()), "config": cfg}, ensure_ascii=False, default=str)
        name = _snap_name()
        ST.recall_set("cfgsnap__" + name, data)
        ST.recall_set("cfgsnap__latest", name)
        idx = [name] + [x for x in _snap_index() if x != name]
        _snap_index_save(idx)
        # 超限清理旧快照（保留最近 N 个）
        for old in idx[_CFG_SNAP_MAX:]:
            try:
                if hasattr(ST, "_KV_CACHE_LOCK"):
                    with ST._KV_CACHE_LOCK:
                        ST._KV_CACHE.pop("cfgsnap__" + old, None)
                if ST._DB is not None:
                    with ST._LOCK:
                        ST._DB.execute("DELETE FROM kv WHERE k=?", ("cfgsnap__" + old,))
                        ST._safe_commit()
            except Exception:
                pass
        return json_response({"ok": True, "name": name})
    except Exception as e:
        return _err(f"snapshot save failed: {e}", 500)


async def handle_cfg_snapshot_restore(request, plugin_base=""):
    """一键恢复指定（或最新）配置快照"""
    try:
        p = await get_req_json(request, default={})
        name = str((p.get("name") or "") if isinstance(p, dict) else "").strip()
        if not name:
            name = get_req_query(request, "name", "").strip()
        if not name:
            name = str(ST.recall_get("cfgsnap__latest", "") or "").strip()
        if not name:
            return _err("no snapshot (name required)", 404)
        raw = ST.recall_get("cfgsnap__" + name, "")
        if not raw:
            return _err("snapshot not found", 404)
        d = _json.loads(raw)
        cfg = d.get("config") if isinstance(d, dict) else None
        if not isinstance(cfg, dict):
            return _err("snapshot broken", 500)
        if hasattr(ST, "_CONFIG"):
            ST._CONFIG.clear()
            for sec, kv in cfg.items():
                if isinstance(kv, dict):
                    if sec in getattr(ST, "_COLL_FILES", {}):
                        # 旧快照可能含商城/图鉴：收编进 sidecar，不进内存
                        try:
                            ST.coll_merge(sec, kv)
                        except Exception:
                            pass
                        continue
                    ST._CONFIG[str(sec)] = {str(k): v for k, v in kv.items()}
        try:
            if hasattr(ST, "_bump_config_ver"):
                ST._bump_config_ver()
        except Exception:
            pass
        try:
            ST.save_config()
        except Exception:
            pass
        try:
            ST.sync_astrbot_config(ST._CONFIG)
        except Exception:
            pass
        try:
            if hasattr(ST, "wd_cfg_backup"):
                ST.wd_cfg_backup((ST._CONFIG.get("备份配置") or {}) if isinstance(ST._CONFIG.get("备份配置"), dict) else None)
        except Exception:
            pass
        return json_response({"ok": True, "name": name})
    except Exception as e:
        return _err(f"snapshot restore failed: {e}", 500)


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
        pwd = (p.get("pwd") if isinstance(p, dict) else None) or get_req_query(request, "pwd", None)
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
        pwd = (p.get("pwd") if isinstance(p, dict) else None) or get_req_query(request, "pwd", None)
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
    if not clean_name.endswith(".db"):
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
            try:
                ST.flush_all()
            except Exception:
                pass
            try:
                cur_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            cur_db.commit()
            src_conn = sqlite3.connect(dl_res)
            src_conn.backup(cur_db)
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


