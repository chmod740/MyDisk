# Django Disk — 私人网盘系统

一个基于 Django 的全功能私人网盘系统，支持文件管理、存储桶、分享、API 密钥和用户管理。

[English Version](README_en.md)

## 功能

### 文件管理
- 📁 无限层级文件夹，拖拽上传，批量操作
- 👁 图片/文本/PDF 在线预览
- 🗑 回收站（Windows 风格：目录折叠、点击进入、智能合并恢复）
- 🔍 搜索、排序、分页
- 🖱 右键菜单（预览/下载/重命名/移动/分享/删除）
- ⚠ 上传同名文件冲突检测（覆盖/保留两者/跳过）

### 存储桶 (Bucket)
- 📦 类 S3 对象存储，支持公有/私有桶
- 🔑 API Key 管理（创建/撤销/删除，最后访问时间追踪）
- 🔗 路径风格下载链接 + 私有桶 Token 鉴权
- 📂 桶内目录管理 + 侧边栏目录树
- 🖱 右键菜单（文件重命名/删除，目录重命名/删除）

### 分享
- 🔗 生成分享链接（可选密码保护 + 过期时间）
- 📦 支持分享文件、文件夹、存储桶
- 📥 分享文件夹支持单文件下载和 ZIP 打包下载
- 👁 分享页预览（图片/PDF）

### 用户与权限
- 👤 注册/登录/个人中心
- 🛡 管理员面板：站点设置、用户管理、用户组管理
- 📊 用户组配额管理，管理员保护（至少保留一个管理员）
- 🖼 图片验证码（注册/登录可选）

### REST API
- 🔐 所有 API 通过 `X-Api-Key` Header 认证
- 📦 桶 CRUD + 文件上传/列举/删除
- 📂 文件管理 CRUD
- 📖 完整 API 文档（含 curl/Python/JS/Go/Java 示例）

### 其他
- 🌓 暗色模式（全局支持）
- 🌐 中英文双语 README

## 快速开始

### 开发环境

```bash
# 安装依赖
pip install django pillow

# 初始化数据库
python manage.py migrate

# 创建管理员
python manage.py shell -c "
from accounts.models import User
User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
"

# 启动
python manage.py runserver 8000
```

访问 http://localhost:8000 ，用 `admin / admin123` 登录。

### Docker 部署

```bash
docker compose up -d
```

## 技术栈

| 层面 | 技术 |
|------|------|
| 后端 | Django 6.0, Python 3.12 |
| 前端 | Django Templates, HTMX 2.0, Alpine.js 3, Tailwind CSS (CDN) |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| 部署 | Docker + Gunicorn + PostgreSQL |

## 项目结构

```
django_disk/
├── accounts/         # 用户、用户组、站点设置、验证码
├── files/            # 文件管理、文件夹、回收站
├── buckets/          # 存储桶、桶文件、API Key、REST API
├── sharing/          # 分享链接、分享页面
├── config/           # Django 配置
├── templates/        # 前端模板
├── media/            # 用户上传文件
├── static/           # 静态资源
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 测试

```bash
# 单元测试
python manage.py test accounts buckets sharing files

# E2E 测试（需先启动服务）
python manage.py runserver 8000 &
python tests_e2e.py
```
