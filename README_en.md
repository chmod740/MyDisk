# Django Disk — Personal Cloud Storage

A full-featured personal cloud storage system built with Django, supporting file management, object buckets, sharing, API keys, and user administration.

[中文文档](README.md)

## Features

### File Management
- 📁 Unlimited folder nesting, drag-and-drop upload, batch operations
- 👁 Inline preview for images, text, and PDFs
- 🗑 Recycle bin (Windows-style: collapsible folders, drill-down, smart merge restore)
- 🔍 Search, sort, and pagination
- 🖱 Right-click context menu (preview/download/rename/move/share/delete)
- ⚠ Duplicate filename conflict resolution (overwrite/keep both/skip)

### Object Buckets
- 📦 S3-like object storage with public/private buckets
- 🔑 API Key management (create/revoke/delete, last-access tracking)
- 🔗 Path-style download URLs + token-based auth for private buckets
- 📂 In-bucket directory management + sidebar folder tree
- 🖱 Right-click menu (file rename/delete, folder rename/delete)

### Sharing
- 🔗 Shareable links with optional password protection and expiration
- 📦 Share files, folders, or buckets
- 📥 Shared folders support individual file download and ZIP batch download
- 👁 Share page preview (images/PDFs)

### Users & Permissions
- 👤 Registration, login, profile
- 🛡 Admin panel: site settings, user management, group management
- 📊 Per-group storage quotas, admin protection (minimum one admin)
- 🖼 Image CAPTCHA for registration/login (configurable)

### REST API
- 🔐 All endpoints authenticated via `X-Api-Key` header
- 📦 Bucket CRUD + file upload/list/delete
- 📂 File management CRUD
- 📖 Full API documentation (curl/Python/JS/Go/Java examples)

### Other
- 🌓 Dark mode (global support)
- 🌐 Bilingual README (EN/ZH)

## Quick Start

### Development

```bash
# Install dependencies
pip install django pillow

# Initialize database
python manage.py migrate

# Create admin user
python manage.py shell -c "
from accounts.models import User
User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
"

# Start server
python manage.py runserver 8000
```

Open http://localhost:8000 and login with `admin / admin123`.

### Docker Deployment

```bash
docker compose up -d
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 6.0, Python 3.12 |
| Frontend | Django Templates, HTMX 2.0, Alpine.js 3, Tailwind CSS (CDN) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Deployment | Docker + Gunicorn + PostgreSQL |

## Project Structure

```
django_disk/
├── accounts/         # Users, groups, site settings, captcha
├── files/            # File management, folders, recycle bin
├── buckets/          # Buckets, bucket files, API keys, REST API
├── sharing/          # Share links, share pages
├── config/           # Django configuration
├── templates/        # Frontend templates
├── media/            # User uploads
├── static/           # Static assets
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Testing

```bash
# Unit tests
python manage.py test accounts buckets sharing files

# E2E tests (start server first)
python manage.py runserver 8000 &
python tests_e2e.py
```
