"""storage/backup.py — 备份生成/串行/防重/修剪（原 store §9）。"""
import json
import os
import time
from . import state as _S
from .state import _safe_commit
from .app_config import cfg, cfgi, save_config
from .kv import recall_get

def set_backup_dir(path):
    _S.BACKUP_DIR = path



def _backup_sidecar_path():
    try:
        if _S.BACKUP_DIR and os.path.isdir(_S.BACKUP_DIR):
            return os.path.join(_S.BACKUP_DIR, ".xb_last_backup.json")
    except Exception:
        pass
    return ""




def _read_backup_sidecar():
    """读跨进程最近备份 (ts, path)，失败回 (0, "")，永不抛错"""
    try:
        _p = _backup_sidecar_path()
        if _p and os.path.isfile(_p):
            with open(_p, "r", encoding="utf-8") as _f:
                _d = json.load(_f)
            if isinstance(_d, dict):
                _ts = float(_d.get("ts", 0) or 0)
                _path = str(_d.get("path", "") or "")
                if _ts > 0 and _path and os.path.isfile(_path):
                    return _ts, _path
    except Exception:
        pass
    return 0.0, ""




def _write_backup_sidecar(ts, path):
    try:
        _p = _backup_sidecar_path()
        if _p:
            with open(_p, "w", encoding="utf-8") as _f:
                json.dump({"ts": float(ts), "path": str(path),
                           "note": "此文件为防重文件，无需删除（文件锁配合防多进程/热重载打出双份备份）"}, _f, ensure_ascii=False)
    except Exception:
        pass




def _clear_backup_busy():
    try:
        if _S.BACKUP_DIR:
            _bp = os.path.join(_S.BACKUP_DIR, ".xb_backup.busy")
            if os.path.isfile(_bp):
                os.remove(_bp)
    except Exception:
        pass




def _reserve_backup_slot():
    """跨进程预约本次生成。返回 (mine, reuse_path)：mine=True 本调用负责生成；
    mine=False 时若 reuse_path 非空可直接复用，否则调用方等待后接管。永不抛错。"""
    try:
        if not (_S.BACKUP_DIR and os.path.isdir(_S.BACKUP_DIR)):
            return True, ""
        _fl = _BackupFileLock()
        try:
            _fl.acquire(timeout=15)
        except Exception:
            pass
        try:
            _now = time.time()
            try:
                _s, _p = _read_backup_sidecar()
                if _s > 0 and (_now - _s < _S._BACKUP_FILE_WINDOW) and _p:
                    return False, _p
            except Exception:
                pass
            _bp = os.path.join(_S.BACKUP_DIR, ".xb_backup.busy")
            _busy_fresh = False
            try:
                if os.path.isfile(_bp) and (_now - os.path.getmtime(_bp) < 120):
                    _busy_fresh = True
            except Exception:
                pass
            if _busy_fresh:
                return False, ""
            try:
                with open(_bp, "w", encoding="utf-8") as _bf:
                    _bf.write(str(_now))
            except Exception:
                pass
            return True, ""
        finally:
            try:
                _fl.release()
            except Exception:
                pass
    except Exception:
        return True, ""




def _wait_backup_slot(timeout=90):
    """等待跨进程在途备份完成，返回复用路径或 ''。永不抛错。"""
    try:
        _deadline = time.time() + timeout
        while time.time() < _deadline:
            time.sleep(0.5)
            try:
                _s, _p = _read_backup_sidecar()
                if _s > 0 and _p:
                    return _p
                if _S.BACKUP_DIR:
                    _bp = os.path.join(_S.BACKUP_DIR, ".xb_backup.busy")
                    if not (os.path.isfile(_bp) and (time.time() - os.path.getmtime(_bp) < 120)):
                        return ""
            except Exception:
                return ""
    except Exception:
        pass
    return ""




class _BackupFileLock:
    """跨进程备份互斥（with 语法）。拿不到锁返回 False，调用方走等待复用；永不抛错。"""

    def __init__(self):
        self._fh = None
        self._locked = False
        self._is_windows = (os.name == "nt")

    def acquire(self, timeout=90):
        try:
            if not _S.BACKUP_DIR:
                return True
            try:
                os.makedirs(_S.BACKUP_DIR, exist_ok=True)
            except Exception:
                pass
            _lp = os.path.join(_S.BACKUP_DIR, ".xb_backup.lock")
            self._fh = open(_lp, "a+b")
            if self._is_windows:
                import msvcrt
                _deadline = time.time() + timeout
                while True:
                    try:
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                        self._locked = True
                        return True
                    except Exception:
                        if time.time() >= _deadline:
                            return False
                        time.sleep(0.5)
            else:
                import fcntl
                _deadline = time.time() + timeout
                while True:
                    try:
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        self._locked = True
                        return True
                    except Exception:
                        if time.time() >= _deadline:
                            return False
                        time.sleep(0.5)
        except Exception:
            return True if self._fh is None else False
        return False

    def release(self):
        try:
            if self._fh is not None and self._locked:
                if self._is_windows:
                    try:
                        import msvcrt
                        self._fh.seek(0)
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    try:
                        import fcntl
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            if self._fh is not None:
                self._fh.close()
        except Exception:
            pass
        self._fh = None
        self._locked = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *a):
        self.release()
        return False




def _valid_backup_file(fp):
    """完好备份校验：存在＋够大＋SQLite 魔数（0 字节坏备份禁复用禁占配额）"""
    try:
        if not fp or not os.path.isfile(fp):
            return False
        if os.path.getsize(fp) < 100:
            return False
        with open(fp, "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except Exception:
        return False


def backup_user_data(force=False, auto_upload=True):
    now = time.time()
    # 5秒全局防抖保护：无论是否 force，若 5 秒内刚生成过完好备份，直接复用，杜绝重复创建双份备份
    if (now - _S._LAST_BACKUP_TIME < 5) and _S._LAST_BACKUP_PATH and os.path.isfile(_S._LAST_BACKUP_PATH):
        return _S._LAST_BACKUP_PATH
    # 跨进程/重载去重：sidecar 在 30 秒窗口内有完好备份直接复用
    try:
        _sts, _sp = _read_backup_sidecar()
        if _sts > 0 and (now - _sts < _S._BACKUP_FILE_WINDOW):
            _S._LAST_BACKUP_TIME = max(_S._LAST_BACKUP_TIME, _sts)
            _S._LAST_BACKUP_PATH = _sp
            return _sp
    except Exception:
        pass
    # 串行化等待：若已有备份正在生成中，等待其完成并复用产物（最多等90秒）
    _wait_dst = None
    with _S._BACKUP_GEN_LOCK:
        _now2 = time.time()
        if (_now2 - _S._LAST_BACKUP_TIME < 5) and _S._LAST_BACKUP_PATH and os.path.isfile(_S._LAST_BACKUP_PATH):
            return _S._LAST_BACKUP_PATH
        if _S._BACKUP_IN_PROGRESS:
            _wait_dst = _S._BACKUP_IN_PROGRESS
    if _wait_dst:
        _deadline = time.time() + 90
        while time.time() < _deadline:
            time.sleep(0.5)
            with _S._BACKUP_GEN_LOCK:
                _still = _S._BACKUP_IN_PROGRESS
                _cur = _S._LAST_BACKUP_PATH
            if not _still:
                if _cur and _valid_backup_file(_cur):
                    return _cur
                break
    if not force and now - _S._LAST_BACKUP_CHECK < 60:
        return None
    _S._LAST_BACKUP_CHECK = now
    try:
        if not force and cfg("备份配置", "自动备份开关", "真") != "真":
            return None
        try:
            hrs = int(float(cfg("备份配置", "备份间隔小时", "3")))
            if hrs < 1:
                hrs = 1
            _S.BACKUP_INTERVAL = hrs * 3600
        except Exception:
            pass
    except Exception:
        pass
    now = time.time()
    # 跨进程/重载收敛：每次都用共享时钟（DB 镜像 + 目录最新）刷新 _last_backup，
    # 多进程各持内存时钟会交错打出双倍备份，取最大后即收敛到单一节拍
    try:
        _shared = 0
        try:
            v = recall_get("last_backup_ts", "")
            if v and str(v).isdigit():
                _shared = int(v)
        except Exception:
            pass
        try:
            if _S.BACKUP_DIR and os.path.isdir(_S.BACKUP_DIR):
                for root, _, files in os.walk(_S.BACKUP_DIR):
                    for fn in files:
                        if fn.endswith(".db"):
                            try:
                                mt = int(os.path.getmtime(os.path.join(root, fn)))
                                if mt > _shared:
                                    _shared = mt
                            except Exception:
                                pass
        except Exception:
            pass
        if _shared > _S._last_backup:
            _S._last_backup = _shared
    except Exception:
        pass
    if not force and now - _S._last_backup < _S.BACKUP_INTERVAL:
        return None
    if not _S.BACKUP_DIR or not _S._DB:
        return None
    if not force:
        with _S._LOCK:
            try:
                cnt = _S._DB.execute("SELECT COUNT(*) FROM wallet").fetchone()
                if cnt and int(cnt[0] or 0) == 0:
                    cnt2 = _S._DB.execute("SELECT COUNT(*) FROM accounts").fetchone()
                    if cnt2 and int(cnt2[0] or 0) == 0:
                        return None
            except Exception:
                pass
    # 跨进程预约：他进程在途则等待复用，否则由本调用生成
    try:
        _mine, _reuse = _reserve_backup_slot()
        if not _mine:
            if _reuse and _valid_backup_file(_reuse):
                _S._LAST_BACKUP_TIME = time.time()
                _S._LAST_BACKUP_PATH = _reuse
                return _reuse
            _wp = _wait_backup_slot(timeout=90)
            if _wp and os.path.isfile(_wp):
                _S._LAST_BACKUP_TIME = time.time()
                _S._LAST_BACKUP_PATH = _wp
                return _wp
    except Exception:
        pass
    try:
        # 冷备前落盘配置，确保备份出来的 db 自包含 100% 配置与用户数据
        try:
            save_config()
        except Exception:
            pass
        day = time.strftime("%Y-%m-%d", time.localtime(now))
        day_dir = os.path.join(_S.BACKUP_DIR, day)
        os.makedirs(day_dir, exist_ok=True)
        fname = f"xbbot_{time.strftime('%Y%m%d_%H%M%S', time.localtime(now))}.db"
        dst = os.path.join(day_dir, fname)
        # 预约在途标记（并发调用已被上游等待复用逻辑拦截；同名文件直接覆盖写新内容，不产生第二份）
        with _S._BACKUP_GEN_LOCK:
            _S._BACKUP_IN_PROGRESS = dst
        import sqlite3 as _sql
        bck = _sql.connect(dst, timeout=_S.DB_TIMEOUT)
        # 非阻塞冷备：仅短持锁做 checkpoint+commit，备份经独立读连接执行，不阻塞消息分发
        with _S._LOCK:
            try:
                _S._DB.execute("PRAGMA wal_checkpoint(PASSIVE)")
                if not _safe_commit():
                    raise RuntimeError("backup checkpoint commit failed")
            except Exception:
                pass
            src_path = _S._DB_PATH
        try:
            src2 = _sql.connect(src_path, timeout=_S.DB_TIMEOUT)
            try:
                src2.execute("PRAGMA query_only=ON")
            except Exception:
                pass
            src2.backup(bck)
            try:
                src2.close()
            except Exception:
                pass
        except Exception:
            # 降级：短持锁直接备份（小库极快）
            with _S._LOCK:
                try:
                    _S._DB.backup(bck)
                except Exception:
                    pass
        # 落盘坏文件直接清掉并走失败路径：禁 0 字节钉住复用窗口＋占配额
        if not _valid_backup_file(dst):
            try:
                bck.close()
            except Exception:
                pass
            try:
                if dst and os.path.isfile(dst):
                    os.remove(dst)
            except Exception:
                pass
            raise RuntimeError("backup file invalid")
        with _S._LOCK:
            _S._last_backup = now
            _S._LAST_BACKUP_TIME = now
            _S._LAST_BACKUP_PATH = dst
        with _S._BACKUP_GEN_LOCK:
            _S._BACKUP_IN_PROGRESS = None
        # 跨进程可见：写 sidecar + 清 busy（重载/他进程 30 秒内直接复用）
        try:
            _write_backup_sidecar(now, dst)
        except Exception:
            pass
        try:
            _clear_backup_busy()
        except Exception:
            pass
        try:
            recall_set("last_backup_ts", str(int(now)))
        except Exception:
            pass
        try:
            bck.close()
        except Exception:
            pass
        try:
            clean_old_backups()
        except Exception:
            pass
        if auto_upload and dst and os.path.isfile(dst):
            try:
                from .. import webdav as _wd
                _wd.async_upload_backup(dst)
            except Exception:
                try:
                    from core import webdav as _wd
                    _wd.async_upload_backup(dst)
                except Exception:
                    pass
        return dst
    except Exception:
        try:
            with _S._BACKUP_GEN_LOCK:
                _S._BACKUP_IN_PROGRESS = None
        except Exception:
            pass
        # 失败残留清掉：connect 预建的空文件禁留（占配额＋钉复用）
        try:
            if dst and os.path.isfile(dst) and not _valid_backup_file(dst):
                os.remove(dst)
        except Exception:
            pass
        try:
            _clear_backup_busy()
        except Exception:
            pass
        return None
    return None


def clean_old_backups(max_keep=None):
    """自动清理旧备份，默认保留最新的 N 份 (默认 30 份)"""
    if max_keep is None:
        try:
            max_keep = cfgi("备份配置", "保留备份数量", 30)
        except Exception:
            max_keep = 30
    if max_keep <= 0:
        max_keep = 30
    if not _S.BACKUP_DIR or not os.path.isdir(_S.BACKUP_DIR):
        return 0
    all_backups = []
    try:
        for root, dirs, files in os.walk(_S.BACKUP_DIR):
            for fn in files:
                if fn.endswith(".db"):
                    fp = os.path.join(root, fn)
                    # 坏备份（0 字节/非 SQLite）直接清，不占配额
                    if not _valid_backup_file(fp):
                        try:
                            os.remove(fp)
                        except Exception:
                            pass
                        continue
                    try:
                        mt = os.path.getmtime(fp)
                        all_backups.append((mt, fp))
                    except Exception:
                        pass
    except Exception:
        return 0
    if len(all_backups) <= max_keep:
        return 0
    all_backups.sort(key=lambda x: x[0])
    to_del_count = len(all_backups) - max_keep
    deleted = 0
    for _, fp in all_backups[:to_del_count]:
        try:
            if os.path.isfile(fp):
                os.remove(fp)
                deleted += 1
            pdir = os.path.dirname(fp)
            if os.path.isdir(pdir) and not os.listdir(pdir):
                try:
                    os.rmdir(pdir)
                except Exception:
                    pass
        except Exception:
            pass
    return deleted


def maybe_auto_backup():
    return backup_user_data(force=False)

__all__ = ["backup_user_data", "clean_old_backups", "maybe_auto_backup", "set_backup_dir"]
