# Django Disk — Personal Cloud Storage

A full-featured personal cloud storage system built with Django, supporting file management, object buckets, Markdown editing & preview, sharing, API keys, and user administration.

[中文文档](README.md)

## Project Status

- Django unit tests: all 223 tests pass
- Production configuration: `python manage.py check --deploy` passes
- Database migrations: `makemigrations --check --dry-run` reports no missing migrations
- CI: GitHub Actions runs unit tests and Playwright E2E in separate jobs

## Features

### File Management
- 📁 Unlimited folder nesting, drag-and-drop upload, batch operations
- 👁 Inline preview for images, text, and PDFs
- 📝 **Markdown Editor**: side-by-side live preview, toolbar + keyboard shortcuts, image upload
- 🎨 **Markdown Rendering**: GFM tables/task lists + code highlighting + KaTeX math + Mermaid diagrams
- 🗑 Recycle bin (Windows-style: collapsible folders, drill-down, smart merge restore)
- 🔍 Search, sort, and pagination
- 🖱 Right-click context menu (preview/download/rename/move/share/delete)
- ⚠ Duplicate filename conflict resolution (overwrite/keep both/skip)

### Object Buckets
- 📦 S3-like object storage with public/private buckets
- 📝 Markdown editing & rendering (full pipeline, same as file manager)
- 📄 Auto-preview of README.md / index.md (index.md takes priority)
- 🖼 In-editor image upload to same directory, auto-insert `![](url)`
- 🔑 API Key management (create/revoke/delete, last-access tracking)
- 🔗 Path-style download URLs + token-based auth for private buckets
- 📂 In-bucket directory management + sidebar folder tree
- 🖱 Right-click menu (file rename/delete, folder rename/delete)

### Sharing
- 🔗 Shareable links with optional password protection and expiration
- 📦 Share files, folders, or buckets
- 📥 Shared folders support individual file download and ZIP batch download
- 👁 Share page Markdown rendering (code highlighting, math, diagrams)
- 👁 Share page image/PDF preview

### Users & Permissions
- 👤 Registration, login, profile
- 🛡 Admin panel: site settings, user management, group management
- 📊 Per-group storage quotas, admin protection (minimum one admin)
- 🖼 Image CAPTCHA for registration/login (configurable)

### REST API
- 🔐 All endpoints authenticated via `X-Api-Key` header
- 📦 Bucket CRUD + file upload/list/delete
- 📂 File management CRUD
- 📖 Full API documentation for common bucket, file, and folder operations
- 🌐 Examples for cURL, JavaScript/TypeScript, Python, Go, PHP, Java, C#/.NET, and Ruby

### Other
- 🌓 Dark mode (global, Markdown rendering adapts automatically)
- 🛡 Allowlist-based Markdown sanitization for scripts, event handlers, and unsafe URLs
- 📊 Enforced storage quotas, consistent usage accounting, and post-commit file cleanup
- 📥 Temporary-file ZIP streaming with Zip Slip path validation
- 🌐 Bilingual README (EN/ZH)

## Quick Start

### Development

```bash
# Create an environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Initialize database
python manage.py migrate

# Create an admin user
python manage.py createsuperuser

# Start server
python manage.py runserver 8000
```

Open http://localhost:8000 and sign in with the account you created. `manage.py` uses `config.settings_dev` for local development.

### Docker Deployment

```bash
cp .env.example .env
# Edit .env and set random, strong database and Django secret values.
docker compose up -d
```

Production requires `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and the database password. HTTPS redirect, HSTS, and secure cookies are enabled when `DJANGO_DEBUG=false`; the reverse proxy must send `X-Forwarded-Proto: https`.

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Required in production; use at least 50 random characters |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `DJANGO_DEBUG` | Must be `false` in production |
| `DATABASE_URL` | PostgreSQL URL with encoded credentials and query options supported |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 6.0, Python 3.12 |
| Frontend | Django Templates, HTMX 2.0, Alpine.js 3, Tailwind CSS (CDN) |
| Markdown | marked.js (GFM), highlight.js, KaTeX, Mermaid |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Deployment | Docker + Gunicorn + PostgreSQL + Caddy |

The Markdown sanitizer is served locally. Tailwind, HTMX, Marked, KaTeX, Mermaid, and related frontend packages still use public CDNs; mirror them into local static assets for offline deployments.

## Project Structure

```
django_disk/
├── accounts/         # Users, groups, site settings, captcha
├── files/            # File management, folders, recycle bin, Markdown editor
├── buckets/          # Buckets, bucket files, API keys, REST API
├── sharing/          # Share links, share pages
├── config/           # Django configuration
├── templates/        # Frontend templates
│   ├── files/        #   File manager pages (Markdown edit/preview)
│   ├── buckets/      #   Bucket pages (README preview)
│   ├── sharing/      #   Share pages
│   └── accounts/     #   Account pages
├── media/            # User uploads
├── static/           # Static assets
├── .github/workflows/ # Unit and Playwright E2E CI
├── Dockerfile
├── docker-compose.yml
├── Caddyfile
└── requirements.txt
```

## Testing

```bash
# Unit tests
python manage.py test accounts buckets sharing files

# Confirm that model changes have migrations
python manage.py makemigrations --check --dry-run

# E2E tests (start server first)
python manage.py runserver 8000 &
python tests_e2e.py
```

GitHub Actions runs unit tests and Playwright E2E tests as separate jobs.

## Operations

```bash
python manage.py recalculate_storage
python manage.py recalculate_storage --user username
python manage.py cleanup_trash
```

## ZIP Naming

Directory downloads use the current directory name for the ZIP, never the parent directory name. A bucket-root download uses the bucket name, and archive entries are relative to the downloaded directory.

The authenticated API documentation is available at `/buckets/api-keys/docs/`.
