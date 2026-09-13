# -*- coding: utf-8 -*-
"""
小白插件专有日志引擎 (core.logger)
特性与限制：
1. 物理大小限制：xb.log 严格限制在 2MB 以内，超额自动轮转至 xb.log.1 (最多保留 1 份备份)。
2. 内存读取限制：从文件末尾反向截取最多 1000 行，禁止全量读入大文件。
3. 安全路径硬编码：固定写入并读取持久化目录中的 logs/xb.log，杜绝路径穿越。
4. 线程安全：多线程写锁互斥。
"""
import os
import datetime
import re as _re
import threading

_LOCK = threading.RLock()
_MAX_BYTES = 2 * 1024 * 1024   # 2 MB 上限
_MAX_LINES = 1000              # 单次读取上限
_LOG_DIR = ""


def _get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_log_dir():
    global _LOG_DIR
    if _LOG_DIR and os.path.isdir(_LOG_DIR):
        return _LOG_DIR
    try:
        from . import storage as ST
    except ImportError:
        try:
            from core import storage as ST
        except ImportError:
            ST = None

    if ST and hasattr(ST, "get_persistent_data_dir"):
        pdir = ST.get_persistent_data_dir(_get_base_dir())
    else:
        pdir = os.path.join(_get_base_dir(), "data")
    
    ldir = os.path.join(pdir, "logs")
    os.makedirs(ldir, exist_ok=True)
    _LOG_DIR = ldir
    return _LOG_DIR


def set_log_dir(ldir):
    """预置日志目录（XbBot.__init__ 已算出数据目录时调用，省一次目录探测；路径不变）"""
    global _LOG_DIR
    try:
        ldir = str(ldir or "").strip()
        if not ldir:
            return _LOG_DIR
        os.makedirs(ldir, exist_ok=True)
        if os.path.isdir(ldir):
            _LOG_DIR = ldir
    except Exception:
        pass
    return _LOG_DIR


def get_log_file_path():
    return os.path.join(get_log_dir(), "xb.log")


def _rotate_if_needed(log_file):
    try:
        if os.path.isfile(log_file) and os.path.getsize(log_file) >= _MAX_BYTES:
            bk = log_file + ".1"
            if os.path.exists(bk):
                try:
                    os.remove(bk)
                except Exception:
                    pass
            try:
                os.rename(log_file, bk)
            except Exception:
                pass
    except Exception:
        pass


def log(msg, level="INFO"):
    """写入一条日志，格式：[YYYY-MM-DD HH:MM:SS] [LEVEL] msg"""
    level = (level or "INFO").upper()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now_str}] [{level}] {msg}\n"
    
    with _LOCK:
        try:
            log_file = get_log_file_path()
            _rotate_if_needed(log_file)
            with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(line)
        except Exception:
            pass


def info(msg):
    log(msg, "INFO")


def error(msg):
    log(msg, "ERROR")


def clear_logs():
    """清空日志，并留下清空记录"""
    with _LOCK:
        try:
            log_file = get_log_file_path()
            bk = log_file + ".1"
            if os.path.exists(bk):
                try:
                    os.remove(bk)
                except Exception:
                    pass
            with open(log_file, "w", encoding="utf-8") as f:
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{now_str}] [INFO] [系统] 日志已由管理员在 WebUI 手动清空。\n")
            return True
        except Exception:
            return False


def get_logs(limit=200, level="", keyword=""):
    """
    内存安全地读取最近日志行：
    - limit: 最多返回行数，硬限制不超过 1000 行
    - level: 过滤级别 (INFO / WARN / ERROR)，空表示全部
    - keyword: 文本过滤关键词
    """
    try:
        limit = min(max(1, int(limit or 200)), _MAX_LINES)
    except Exception:
        limit = 200

    log_file = get_log_file_path()
    # 如果日志文件不存在，先写一条服务初始化日志，确保日志文件一定被创建且有基线日志
    if not os.path.isfile(log_file):
        try:
            info("小白插件运行日志服务已就绪")
        except Exception:
            pass

    file_size = 0
    try:
        if os.path.isfile(log_file):
            file_size = os.path.getsize(log_file)
    except Exception:
        pass

    level = (level or "").strip().upper()
    if level == "ALL":
        level = ""
    keyword = (keyword or "").strip().lower()

    lines = []
    with _LOCK:
        try:
            # 针对大文件使用块逆向读取，避免全量读入
            # 最多回溯读取末尾 512KB 内容，确保即时响应且不爆内存
            read_size = min(file_size, 512 * 1024)
            with open(log_file, "rb") as f:
                if file_size > read_size:
                    f.seek(file_size - read_size)
                raw_bytes = f.read()
            text = raw_bytes.decode("utf-8", errors="replace")
            all_lines = text.splitlines()
        except Exception:
            all_lines = []

    total_lines = len(all_lines)
    # 从末尾开始收集符合条件的行
    collected = []
    level_re = None
    if level:
        if level in ("WARN", "WARNING"):
            level_re = _re.compile(r"^\[[^\]]*\]\s*\[(?:WARN|WARNING)\]")
        else:
            level_re = _re.compile(r"^\[[^\]]*\]\s*\[" + _re.escape(level) + r"\]")

    for line in reversed(all_lines):
        if not line.strip():
            continue
        if level_re and not level_re.match(line):
            continue
        if keyword and keyword not in line.lower():
            continue
        collected.append(line)
        if len(collected) >= limit:
            break

    # 还原为正序展示
    collected.reverse()

    return {
        "logs": collected,
        "count": len(collected),
        "total_lines": total_lines,
        "file_size_kb": round(file_size / 1024, 1),
        "max_lines": _MAX_LINES,
        "max_file_mb": round(_MAX_BYTES / (1024 * 1024), 1)
    }
