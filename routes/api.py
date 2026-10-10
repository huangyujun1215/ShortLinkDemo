"""REST API 与跳转路由。"""
import hashlib
import hmac
import math
import sqlite3
from urllib.parse import urlparse

from flask import Blueprint, jsonify, redirect, request

from services.code_generator import generate_code, is_valid_custom_code
from storage import database as db

bp = Blueprint("api", __name__)

# 随机短码冲突时的最大重试次数（62^6 ≈ 568 亿，碰撞概率极低）
MAX_GENERATE_ATTEMPTS = 10


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _is_valid_http_url(url: str) -> bool:
    """仅接受合法的 http/https 地址。"""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_valid_password(password) -> bool:
    """密码须为 1–32 个可见字符（不含空白与控制字符）。"""
    return (
        isinstance(password, str)
        and 1 <= len(password) <= 32
        and password.isprintable()
        and not any(c.isspace() for c in password)
    )


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _check_password(link) -> bool:
    """无密码短链直接放行；有密码则校验 ?password= 参数（常数时间比较）。"""
    if link["password_hash"] is None:
        return True
    supplied = request.args.get("password")
    return supplied is not None and hmac.compare_digest(
        _hash_password(supplied), link["password_hash"]
    )


@bp.post("/api/shorten")
def shorten():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("请求体必须是 JSON 对象", 400)

    url = data.get("url")
    custom_code = data.get("custom_code")
    password = data.get("password")

    if not isinstance(url, str) or not url.strip():
        return _error("缺少必填字段 url", 400)
    url = url.strip()
    if not _is_valid_http_url(url):
        return _error("url 必须是合法的 http/https 地址", 400)

    password_hash = None
    if password is not None:
        if not _is_valid_password(password):
            return _error("password 非法：须为 1–32 个可见字符（不含空格与控制字符）", 400)
        password_hash = _hash_password(password)

    if custom_code is not None:
        if not is_valid_custom_code(custom_code):
            return _error(
                "custom_code 非法：仅允许大小写字母、数字、-、_，长度 4–16", 400
            )
        if db.code_exists(custom_code):
            return _error(f"短码 {custom_code} 已被占用", 409)
        short_code = custom_code
    else:
        short_code = None
        for _ in range(MAX_GENERATE_ATTEMPTS):
            candidate = generate_code()
            if not db.code_exists(candidate):
                short_code = candidate
                break
        if short_code is None:
            return _error("短码生成失败，请重试", 500)

    try:
        db.create_link(short_code, url, password_hash)
    except sqlite3.IntegrityError:
        # 并发下自定义短码可能恰好被抢占
        return _error(f"短码 {short_code} 已被占用", 409)

    link = db.get_link(short_code)
    return (
        jsonify(
            {
                "short_code": short_code,
                "short_url": f"{request.host_url.rstrip('/')}/{short_code}",
                "original_url": link["original_url"],
                "has_password": password_hash is not None,
                "created_at": link["created_at"],
            }
        ),
        201,
    )


@bp.put("/api/shorten/<short_code>")
def update_short_code(short_code: str):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("请求体必须是 JSON 对象", 400)

    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        return _error("缺少必填字段 url", 400)
    url = url.strip()
    if not _is_valid_http_url(url):
        return _error("url 必须是合法的 http/https 地址", 400)

    if not db.update_link_url(short_code, url):
        return _error("短码不存在", 404)

    link = db.get_link(short_code)
    return jsonify(
        {
            "short_code": short_code,
            "short_url": f"{request.host_url.rstrip('/')}/{short_code}",
            "original_url": link["original_url"],
            "created_at": link["created_at"],
        }
    )


MAX_PAGE_SIZE = 100


@bp.get("/api/links")
def list_all_links():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    if page is None or page < 1:
        return _error("page 必须为正整数", 400)
    if page_size is None or page_size < 1 or page_size > MAX_PAGE_SIZE:
        return _error(f"page_size 必须为 1–{MAX_PAGE_SIZE} 的整数", 400)

    total = db.count_links()
    rows = db.list_links(page, page_size)
    base_url = request.host_url.rstrip("/")
    return jsonify(
        {
            "items": [
                {
                    "short_code": row["short_code"],
                    "short_url": f"{base_url}/{row['short_code']}",
                    "original_url": row["original_url"],
                    "visit_count": row["visit_count"],
                    "created_at": row["created_at"],
                    "last_visited_at": row["last_visited_at"],
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    )


@bp.get("/<short_code>")
def redirect_to_original(short_code: str):
    link = db.get_link(short_code)
    if link is None:
        return _error("短码不存在", 404)
    if not _check_password(link):
        return _error("短链受密码保护，请通过 ?password= 提供正确密码", 401)
    db.record_visit(short_code)
    return redirect(link["original_url"], code=302)


@bp.get("/api/stats/<short_code>")
def stats(short_code: str):
    link = db.get_link(short_code)
    if link is None:
        return _error("短码不存在", 404)
    if not _check_password(link):
        return _error("短链受密码保护，请通过 ?password= 提供正确密码", 401)
    return jsonify(
        {
            "short_code": link["short_code"],
            "original_url": link["original_url"],
            "visit_count": link["visit_count"],
            "created_at": link["created_at"],
            "last_visited_at": link["last_visited_at"],
        }
    )
