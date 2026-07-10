# Django Disk — 私人网盘系统

一个基于 Django 的全功能私人网盘系统，支持文件管理、存储桶、Markdown 编辑预览、分享、API 密钥和用户管理。

[English Version](README_en.md)

## 项目状态

- Django 单元测试：223 项全部通过
- 生产配置：`python manage.py check --deploy` 通过
- 数据库迁移：`makemigrations --check --dry-run` 无遗漏
- CI：GitHub Actions 分别运行单元测试和 Playwright E2E

## 功能

### 文件管理
- 📁 无限层级文件夹，拖拽上传，批量操作
- 👁 图片/文本/PDF 在线预览
- 📝 **Markdown 编辑器**：左右分栏实时预览，工具栏 + 快捷键，图片上传
- 🎨 **Markdown 渲染**：GFM 表格/任务列表 + 代码高亮 + KaTeX 数学公式 + Mermaid 图表
- 🗑 回收站（Windows 风格：目录折叠、点击进入、智能合并恢复）
- 🔍 搜索、排序、分页
- 🖱 右键菜单（预览/下载/重命名/移动/分享/删除）
- ⚠ 上传同名文件冲突检测（覆盖/保留两者/跳过）

### 存储桶 (Bucket)
- 📦 类 S3 对象存储，支持公有/私有桶
- 📝 Markdown 编辑与渲染（与文件管理一致的完整管线）
- 📄 自动预览 README.md / index.md（当前目录下 index.md 优先）
- 🖼 Markdown 编辑器内图片上传到同级目录，自动插入 `![](url)`
- 🔑 API Key 管理（创建/撤销/删除，最后访问时间追踪）
- 🔗 路径风格下载链接 + 私有桶 Token 鉴权
- 📂 桶内目录管理 + 侧边栏目录树
- 🖱 右键菜单（文件重命名/删除，目录重命名/删除）

### 分享
- 🔗 生成分享链接（可选密码保护 + 过期时间）
- 📦 支持分享文件、文件夹、存储桶
- 📥 分享文件夹支持单文件下载和 ZIP 打包下载
- 👁 分享页 Markdown 渲染预览（含代码高亮、数学公式、图表）
- 👁 分享页图片/PDF 预览

### 用户与权限
- 👤 注册/登录/个人中心
- 🛡 管理员面板：站点设置、用户管理、用户组管理
- 📊 用户组配额管理，管理员保护（至少保留一个管理员）
- 🖼 图片验证码（注册/登录可选）

### REST API
- 🔐 所有 API 通过 `X-Api-Key` Header 认证
- 📦 桶 CRUD + 文件上传/列举/删除
- 📂 文件管理 CRUD
- 📖 完整 API 文档，覆盖桶、文件和目录常用操作
- 🌐 调用示例覆盖 cURL、JavaScript/TypeScript、Python、Go、PHP、Java、C# 和 Ruby

### 其他
- 🌓 暗色模式（全局支持，Markdown 渲染区自适应）
- 🛡 Markdown 允许列表消毒，拦截脚本、事件属性和危险 URL
- 📊 统一存储配额、用量追踪和事务提交后的物理文件清理
- 📥 ZIP 使用临时文件流式返回，并防止 Zip Slip 路径穿越
- 🌐 中英文双语 README

## 快速开始

### 开发环境

```bash
# 创建环境并安装依赖
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 初始化数据库
python manage.py migrate

# 创建管理员
python manage.py createsuperuser

# 启动
python manage.py runserver 8000
```

访问 http://localhost:8000 并使用刚创建的账号登录。`manage.py` 默认加载 `config.settings_dev`，仅用于本地开发。

### Docker 部署

```bash
cp .env.example .env
# 编辑 .env，为数据库密码和 Django SECRET_KEY 设置随机强值
docker compose up -d
```

Docker 生产模式要求 `DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS` 和数据库密码，默认启用 HTTPS 跳转、HSTS 与 Secure Cookie。反向代理需传递 `X-Forwarded-Proto: https`。

| 环境变量 | 说明 |
|---|---|
| `DJANGO_SECRET_KEY` | 生产必填，建议至少 50 个随机字符 |
| `DJANGO_ALLOWED_HOSTS` | 逗号分隔的域名列表 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 逗号分隔的 HTTPS Origin |
| `DJANGO_DEBUG` | 生产必须为 `false` |
| `DATABASE_URL` | PostgreSQL URL，支持 URL 编码密码和查询参数 |

## 技术栈

| 层面 | 技术 |
|------|------|
| 后端 | Django 6.0, Python 3.12 |
| 前端 | Django Templates, HTMX 2.0, Alpine.js 3, Tailwind CSS (CDN) |
| Markdown | marked.js (GFM), highlight.js, KaTeX, Mermaid |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| 部署 | Docker + Gunicorn + PostgreSQL + Caddy |

Markdown 的安全消毒脚本位于本地静态目录；Tailwind、HTMX、Marked、KaTeX 和 Mermaid 等前端库目前仍使用公共 CDN，离线部署时需将它们镜像到本地静态目录。

## 项目结构

```
django_disk/
├── accounts/         # 用户、用户组、站点设置、验证码
├── files/            # 文件管理、文件夹、回收站、Markdown 编辑器
├── buckets/          # 存储桶、桶文件、API Key、REST API
├── sharing/          # 分享链接、分享页面
├── config/           # Django 配置
├── templates/        # 前端模板
│   ├── files/        #   文件管理页面（含 Markdown 编辑/预览）
│   ├── buckets/      #   存储桶页面（含 README 预览）
│   ├── sharing/      #   分享页面
│   └── accounts/     #   账号页面
├── media/            # 用户上传文件
├── static/           # 静态资源
├── .github/workflows/ # 单元测试与 Playwright E2E CI
├── Dockerfile
├── docker-compose.yml
├── Caddyfile
└── requirements.txt
```

## 测试

```bash
# 单元测试
python manage.py test accounts buckets sharing files

# 检查模型变更是否已生成迁移
python manage.py makemigrations --check --dry-run

# E2E 测试（需先启动服务）
python manage.py runserver 8000 &
python tests_e2e.py
```

GitHub Actions 会分别运行单元测试和 Playwright E2E 测试。

## 运维命令

```bash
# 修复所有用户的存储用量
python manage.py recalculate_storage

# 只重算指定用户
python manage.py recalculate_storage --user username

# 清理 30 天前的回收站内容
python manage.py cleanup_trash
```

## ZIP 目录命名

下载目录时，ZIP 文件名使用「当前下载目录」的名称，不使用父目录名。下载桶根目录时使用桶名；ZIP 内部路径均相对于当前目录。

API 调用文档位于 `/buckets/api-keys/docs/`，需登录后访问。
