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

{"url": "<长网址>", "custom_code": "<可选自定义短码>", "password": "<可选访问密码>"}
```

- 成功：`201`，返回

  ```json
  {
    "short_code": "aB3xY9",
    "short_url": "http://localhost:8000/aB3xY9",
    "original_url": "https://example.com/long/path",
    "has_password": false,
    "created_at": "2026-10-10T08:00:00.000000+00:00"
  }
  ```

- `400`：`url` 缺失 / 不是合法 http/https 地址；`custom_code` 含非法字符
  （仅允许大小写字母、数字、`-`、`_`，长度 4–16）；`password` 非法
  （须为 1–32 个可见字符，不含空格与控制字符）
- `409`：`custom_code` 与已有短码重复
- 带 `password` 创建的短链为受保护短链：访问与统计须通过 `?password=` 提供
  正确密码，否则返回 `401`（见第 3、4 节）；密码以 SHA-256 哈希存储，不存明文

### 2. 修改短链指向

```
PUT /api/shorten/<short_code>
Content-Type: application/json

{"url": "<新长网址>"}
```

- 成功：`200`，返回更新后的信息（响应体同创建接口），访问统计不受影响
- `400`：`url` 缺失 / 不是合法 http/https 地址
- `404`：短码不存在

### 3. 访问短链接

```
GET /<short_code>            # 无密码短链
GET /<short_code>?password=  # 受保护短链
```

- 存在且密码正确（或无密码）：访问计数 +1，返回 `302`，`Location` 头指向原网址
- 受保护短链未带 / 密码错误：`401`，`{"error": "短链受密码保护，..."}`，不计数
- 不存在：`404`，`{"error": "短码不存在"}`

### 4. 查询统计

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
- 受保护短链同访问接口：须带 `?password=<正确密码>`，否则 `401`

### 5. 分页列出短链

```
GET /api/links?page=1&page_size=20
```

查询参数：`page`（默认 1，正整数）、`page_size`（默认 20，1–100）。

- 成功：`200`，按创建时间倒序返回，附分页元数据：

  ```json
  {
    "items": [
      {
        "short_code": "aB3xY9",
        "short_url": "http://localhost:8000/aB3xY9",
        "original_url": "https://example.com/long/path",
        "visit_count": 3,
        "created_at": "2026-10-10T08:00:00.000000+00:00",
        "last_visited_at": "2026-10-10T09:30:00.000000+00:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 42,
    "total_pages": 3
  }
  ```

  （空库时 `items` 为 `[]`、`total_pages` 为 `0`）
- `400`：`page` 非正整数，或 `page_size` 超出 1–100

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

# 创建受密码保护的短链
curl -X POST http://localhost:8000/api/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.org/private", "custom_code": "secret-1", "password": "hunter2"}'

# 修改短链指向
curl -X PUT http://localhost:8000/api/shorten/my-link \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/new-target"}'

# 分页列出短链（按创建时间倒序）
curl 'http://localhost:8000/api/links?page=1&page_size=20'

# 访问短链（302 跳转）
curl -i http://localhost:8000/my-link

# 访问受密码保护的短链（错误密码 → 401）
curl -i 'http://localhost:8000/secret-1?password=hunter2'

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
- **密码保护**：可选 `password`（1–32 个可见字符）以 SHA-256 哈希存储、
  不落明文，校验用 `hmac.compare_digest` 常数时间比较；受保护短链的跳转与
  统计都须带 `?password=`，未通过时不计数、不暴露原网址。旧数据库文件启动时
  自动 `ALTER TABLE` 补齐 `password_hash` 列。

## 限制

- 单机单进程，不做分布式 / 高可用
- 不含用户系统、鉴权、URL 内容抓取、过期删除、HTTPS 部署
