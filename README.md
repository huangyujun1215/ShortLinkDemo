# ShortLink 短链接服务

把长网址压缩为短链接、访问短链接时 302 跳转到原网址，并附带最基础的访问统计。

- 单机单进程，SQLite 本地文件持久化，无其他外部依赖
- 默认短码为随机 6 位 `[A-Za-z0-9]`，支持自定义短码
- 极简前端页面（单 HTML + 原生 JS，无框架、无构建）

## 运行

需要 Python 3.10+。

```bash
cd shortlink
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

服务启动在 `http://localhost:8000`，数据库文件自动创建于项目根目录 `shortlink.db`。

- 前端页面：<http://localhost:8000/>
- REST API：见下文

## 项目结构

```
shortlink/
├── app.py                     # 应用入口：创建 Flask 应用、托管静态页
├── requirements.txt           # Python 依赖（仅 Flask）
├── routes/
│   └── api.py                 # REST API 与 302 跳转路由
├── storage/
│   └── database.py            # SQLite 存储层（links 表建表与读写）
├── services/
│   └── code_generator.py      # 短码生成与自定义短码校验
└── static/
    └── index.html             # 极简前端页面（原生 JS）
```

## API

### 1. 创建短链接

```
POST /api/shorten
Content-Type: application/json

{"url": "<长网址>", "custom_code": "<可选自定义短码>"}
```

- 成功：`201`，返回

  ```json
  {
    "short_code": "aB3xY9",
    "short_url": "http://localhost:8000/aB3xY9",
    "original_url": "https://example.com/long/path",
    "created_at": "2026-10-10T08:00:00.000000+00:00"
  }
  ```

- `400`：`url` 缺失 / 不是合法 http/https 地址；`custom_code` 含非法字符
  （仅允许大小写字母、数字、`-`、`_`，长度 4–16）
- `409`：`custom_code` 与已有短码重复

### 2. 访问短链接

```
GET /<short_code>
```

- 存在：访问计数 +1，返回 `302`，`Location` 头指向原网址
- 不存在：`404`，`{"error": "短码不存在"}`

### 3. 查询统计

```
GET /api/stats/<short_code>
```

- 存在：`200`，返回

  ```json
  {
    "short_code": "aB3xY9",
    "original_url": "https://example.com/long/path",
    "visit_count": 3,
    "created_at": "2026-10-10T08:00:00.000000+00:00",
    "last_visited_at": "2026-10-10T09:30:00.000000+00:00"
  }
  ```

  （从未被访问过时 `last_visited_at` 为 `null`）
- 不存在：`404`，`{"error": "短码不存在"}`

## curl 示例

```bash
# 创建短链（随机短码）
curl -X POST http://localhost:8000/api/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/some/very/long/path?utm_source=x"}'

# 创建短链（自定义短码）
curl -X POST http://localhost:8000/api/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.org", "custom_code": "my-link"}'

# 访问短链（302 跳转）
curl -i http://localhost:8000/my-link

# 查询统计
curl http://localhost:8000/api/stats/my-link
```

## 设计说明

- **存储**：`links` 表以 `short_code` 为主键（自带唯一索引），存短码、原网址、
  访问次数、创建时间、最后访问时间；每次访问用单条 `UPDATE` 原子地完成
  计数 +1 与 `last_visited_at` 刷新。
- **短码生成**：`secrets` 密码学安全随机源，默认 6 位 62 字符集
  （约 568 亿组合），插入前查重，冲突自动重试；自定义短码用正则
  `^[A-Za-z0-9_-]{4,16}$` 校验，重复时依赖唯一索引兜底返回 409。
- **校验**：仅接受 scheme 为 `http`/`https` 且带 host 的 URL。

## 限制

- 单机单进程，不做分布式 / 高可用
- 不含用户系统、鉴权、URL 内容抓取、过期删除、HTTPS 部署
