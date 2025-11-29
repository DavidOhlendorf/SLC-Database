# Production Deployment Documentation

This document describes the current production deployment of the SLC Database hosted on Hetzner Cloud.  

---

## 1. Server Overview

- **Hosting:** Hetzner Cloud
- **OS:** Ubuntu 24.04 LTS
- **Project directory:** `/var/www/SLC`
- **Python version:** 3.13
- **PostgreSQL version:** (Hetzner default, 15.x)
- **Web stack:**
  - Gunicorn (WSGI application server)
  - Nginx (reverse proxy, static/media serving)
  - HTTPS via Let’s Encrypt (Certbot)

---

## 2. Application Code

- Production branch: **`main`**
- Repository: `https://github.com/DavidOhlendorf/SLC-Database`
- The deployed code is a shallow clone in `/var/www/SLC`
- Updates are applied via `git pull origin main`

---

## 3. Python Environment

- Virtual environment located at:
  `/var/www/SLC/.venv`
- Dependencies installed from:
  `/var/www/SLC/requirements.txt`
- The production environment uses exactly the versions in `requirements.txt` at deployment time.

---

## 4. Environment Variables

The production `.env` file is located at:
`/var/www/SLC/.env`

---

## 5. Database Configuration

- **Database:** `slcdb`
- **Extensions enabled:**
  - `pg_trgm` 
- **Location:** Local PostgreSQL server on the same machine


## 6. Static & Media Files

### Static files
Collected into:
`/var/www/SLC/static/`
via:
`python manage.py collectstatic`

### Media files (screenshots)
Stored in:
`/var/www/SLC/media/`

This directory is persistent and not part of the Git repository.

## 7. Gunicorn Configuration

Systemd service file:
`/etc/systemd/system/gunicorn.service`
- Socket used: `/run/gunicorn.slcdb.sock`
- Gunicorn is controlled via `systemctl` and restarts automatically on deployment.
  
## 8. Nginx Configuration

Nginx site file:
`/etc/nginx/sites-available/slcdb`


Key responsibilities:

- Reverse proxy to Gunicorn via UNIX socket
- Serve `/static/` and `/media/` from the filesystem
- Automatic HTTPS management via Certbot

Nginx reloads are triggered on each deployment.

---

## 9. HTTPS / TLS

- HTTPS certificates issued by **Let’s Encrypt**
- Managed automatically via Certbot


## 10. Deployment Process (Production)

Updates to the production system are executed manually via:
```
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
sudo systemctl reload nginx
```

This sequence reflects the current operational workflow.
A helper script exists under:

/var/www/SLC/scripts/deploy.sh

**This document reflects the state of the production deployment as of:**
**November 2025**

