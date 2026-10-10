"""REST API 与跳转路由。"""
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


@bp.post("/api/shorten")
def shorten():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("请求体必须是 JSON 对象", 400)

    url = data.get("url")
    custom_code = data.get("custom_code")

    if not isinstance(url, str) or not url.strip():
        return _error("缺少必填字段 url", 400)
    url = url.strip()
    if not _is_valid_http_url(url):
        return _error("url 必须是合法的 http/https 地址", 400)

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
        db.create_link(short_code, url)
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
                "created_at": link["created_at"],
            }
        ),
        201,
    )


@bp.get("/<short_code>")
def redirect_to_original(short_code: str):
    link = db.get_link(short_code)
    if link is None:
        return _error("短码不存在", 404)
    db.record_visit(short_code)
    return redirect(link["original_url"], code=302)


@bp.get("/api/stats/<short_code>")
def stats(short_code: str):
    link = db.get_link(short_code)
    if link is None:
        return _error("短码不存在", 404)
    return jsonify(
        {
            "short_code": link["short_code"],
            "original_url": link["original_url"],
            "visit_count": link["visit_count"],
            "created_at": link["created_at"],
            "last_visited_at": link["last_visited_at"],
        }
    )
