# Django Disk

A private cloud storage and object-bucket application built with Django. It combines file management, live Markdown editing, enhanced previews, secure sharing, API keys, quotas, and administration in one deployable service.

[中文文档](README.md) · [Test status](https://github.com/chmod740/MyDisk/actions/workflows/test.yml)

[![Tests](https://github.com/chmod740/MyDisk/actions/workflows/test.yml/badge.svg)](https://github.com/chmod740/MyDisk/actions/workflows/test.yml)

## Screenshots

### File manager

![Django Disk file manager](docs/screenshots/file-manager.jpg)

### Live Markdown editor

![Live split-pane Markdown editor](docs/screenshots/markdown-editor.jpg)

### Mermaid diagram preview

![Rendered Markdown Mermaid flowchart](docs/screenshots/markdown-diagrams.jpg)

## Project Status

- Django unit tests: all 234 tests pass
- Migration check: `makemigrations --check --dry-run` reports no missing migrations
- CI: GitHub Actions runs unit and Playwright E2E jobs separately
- Development database: SQLite
- Production database: PostgreSQL
- Runtime: Python 3.12 and Django 6.0

## Features

### File Management

- Unlimited folder nesting, search, sorting, and pagination
- Drag-and-drop upload plus batch move, delete, and download
- Duplicate-name handling with overwrite, keep-both, or skip behavior
- Inline previews for images, text, PDFs, and Markdown
- Rename, move, download, share, and delete actions for files and folders
- Hierarchical recycle bin with restore and permanent deletion
- Temporary-file ZIP streaming with archive-path validation

### Markdown Editing and Preview

- 120 ms debounced live rendering with edit, split, and preview modes
- Formatting toolbar, keyboard shortcuts, counters, and bidirectional scroll sync
- GitHub, clean-reading, and WeChat layouts with browser-persisted preferences
- Rich HTML copy
- CommonMark 0.31.2 and GFM tables, task lists, strikethrough, autolinks, and alerts
- Multi-language syntax highlighting with highlight.js
- KaTeX inline and display math using `$...$`, `$$...$$`, `\(...\)`, or `\[...\]`
- Mermaid flowcharts, sequence/class/state/ER diagrams, Gantt, pie, quadrant, XY charts, and mind maps
- Responsive diagram and formula sizing plus contained horizontal scrolling for wide tables
- Allowlist-based HTML sanitization for scripts, event handlers, and unsafe URLs

File previews, bucket READMEs, share pages, and the live editor all use the same Markdown rendering and sanitization pipeline.

### Object Buckets

- S3-like public and private buckets
- In-bucket folders, upload, rename, delete, and download operations
- Automatic `index.md` or `README.md` preview, with `index.md` taking priority
- In-editor image upload to the current bucket path with automatic link insertion
- Path-style downloads and token authentication for private buckets
- API Key creation, revocation, deletion, and last-access tracking

### Sharing

- Share individual files, folders, or buckets
- Optional password protection and expiration
- Individual downloads and recursive ZIP downloads for shared folders
- Image, PDF, text, and full Markdown rendering on public share pages
- Automatic share-link revocation when a target is deleted or soft-deleted

### Users and Administration

- Registration, login, profiles, and optional image CAPTCHA
- User groups and per-user storage quotas
- Site settings, user management, and group management
- Protection that keeps at least one administrator account
- Global light/dark mode and a responsive mobile navigation drawer

### REST API

- `X-Api-Key` header authentication
- File listing, upload, download, deletion, and folder creation
- Bucket creation, listing, deletion, folder operations, and file operations
- Examples for cURL, JavaScript/TypeScript, Python, Go, PHP, Java, C#/.NET, and Ruby

Sign in and open `/buckets/api-keys/docs/` for the complete endpoint reference and language examples.

## Quick Start

### Local Development

```bash
git clone git@github.com:chmod740/MyDisk.git
cd MyDisk

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>. `manage.py` uses `config.settings_dev` by default, so production secrets are not required for local development.

### Docker Deployment

```bash
cp .env.example .env
# Replace the database password, SECRET_KEY, host names, and CSRF origins.
docker compose up -d --build
```

The Web container waits for PostgreSQL, applies migrations, runs `collectstatic`, and starts Gunicorn automatically.

## Environment Variables

| Variable | Required | Description |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Production | Use at least 50 random characters |
| `DJANGO_ALLOWED_HOSTS` | Production | Comma-separated host names |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Production | Comma-separated full HTTPS origins |
| `DJANGO_DEBUG` | Production | Must be `false` in production |
| `DATABASE_URL` | Set by Docker | PostgreSQL URL with encoded credentials and query options supported |
| `POSTGRES_PASSWORD` | Docker | PostgreSQL user password |

Production mode enables HTTPS redirect, HSTS, Secure Cookie settings, and `X-Content-Type-Options`. A reverse proxy must pass `X-Forwarded-Proto: https`.

## Upgrading Existing Data

Existing databases and uploaded files can be upgraded in place; do not delete or reinitialize them. Back up the database, `media/`, and environment configuration before upgrading.

### Source Deployment

```bash
git pull --ff-only
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check

# Replace with the service name used by your deployment.
sudo systemctl restart django-disk
```

Do not replace the application code while skipping migrations. `migrate` applies only migrations that have not run yet and does not clear existing business data. Temporarily stopping writes provides the simplest consistency window during an upgrade.

### Docker Upgrade

```bash
git pull --ff-only
docker compose up -d --build
```

`pgdata` and `media_data` are persistent volumes, so rebuilding the Web container does not remove the database or uploaded files.

## Testing

```bash
# Full unit suite
python manage.py test

# Confirm that model changes have migrations
python manage.py makemigrations --check --dry-run

# E2E
pip install -r requirements-dev.txt
playwright install chromium
python manage.py migrate
python manage.py runserver 127.0.0.1:8000 &
python tests_e2e.py
```

## Operations

```bash
# Recalculate storage usage for every user
python manage.py recalculate_storage

# Recalculate one user
python manage.py recalculate_storage --user username

# Remove recycle-bin content older than 30 days
python manage.py cleanup_trash
```

## Technology

| Layer | Technology |
|---|---|
| Backend | Django 6.0, Python 3.12 |
| Frontend | Django Templates, HTMX 2.0, Alpine.js 3, Tailwind CSS |
| Markdown | Marked 18, highlight.js 11, KaTeX 0.17, Mermaid 11 |
| Database | SQLite for development, PostgreSQL 16 for production |
| Deployment | Docker, Gunicorn, external HTTPS reverse proxy |
| CI | GitHub Actions, Django TestCase, Playwright |

The sanitizer and application logic are served from local static assets. Tailwind, HTMX, Marked, KaTeX, Mermaid, and related frontend packages currently use public CDNs; mirror them into local static assets for fully offline deployments.

## Project Structure

```text
django_disk/
├── accounts/              # Users, groups, quotas, CAPTCHA, and admin views
├── buckets/               # Buckets, API keys, bucket files, and REST API
├── files/                 # Files, folders, recycle bin, and storage services
├── sharing/               # Share links and public previews
├── config/                # Django settings, URLs, WSGI, and ASGI
├── static/                # Markdown renderer, editor, and sanitization assets
├── templates/             # Pages and shared components
├── docs/screenshots/      # README screenshots
├── .github/workflows/     # Unit and E2E CI
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── manage.py
```

## ZIP Naming

Directory downloads use the current directory name for the ZIP, never the parent directory name. A bucket-root download uses the bucket name, and archive entries are relative to the downloaded directory.

## Design References

The Markdown editing experience takes design cues from [doocs/md](https://github.com/doocs/md) and [WeMD](https://github.com/tenngoxars/WeMD), including view switching, preview themes, and rich HTML copy. This project implements those ideas independently with Django templates, a shared renderer, and an allowlist security pipeline.
