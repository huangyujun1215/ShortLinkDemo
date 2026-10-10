"""SQLite 存储层：links 表的建表与增删改查。"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# 数据库文件固定放在项目根目录下
DB_PATH = Path(__file__).resolve().parent.parent / "shortlink.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等）。short_code 为主键，自带唯一索引保证短码不重复。"""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                short_code      TEXT PRIMARY KEY,
                original_url    TEXT NOT NULL,
                visit_count     INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                last_visited_at TEXT
            )
            """
        )


def code_exists(short_code: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM links WHERE short_code = ?", (short_code,)
        ).fetchone()
        return row is not None


def create_link(short_code: str, original_url: str) -> None:
    """插入一条短链记录；短码重复时抛出 sqlite3.IntegrityError。"""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO links (short_code, original_url, visit_count, created_at)"
            " VALUES (?, ?, 0, ?)",
            (short_code, original_url, now),
        )


def get_link(short_code: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT short_code, original_url, visit_count, created_at, last_visited_at"
            " FROM links WHERE short_code = ?",
            (short_code,),
        ).fetchone()


def record_visit(short_code: str) -> None:
    """访问计数 +1 并刷新最后访问时间（单条 UPDATE，原子完成）。"""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE links SET visit_count = visit_count + 1, last_visited_at = ?"
            " WHERE short_code = ?",
            (now, short_code),
        )
