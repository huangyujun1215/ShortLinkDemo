"""ShortLink 应用入口：创建 Flask 应用并启动。"""
from flask import Flask, send_from_directory

from routes.api import bp
from storage import database


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static")

    database.init_db()
    app.register_blueprint(bp)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8000)
