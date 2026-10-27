# SLC Database – Production Deployment Documentation

## 1. Server Overview

The SLC Database is hosted on a Hetzner Cloud server.

- **Server:** `slcdb-prod`
- **Operating system:** Ubuntu 24.04 LTS
- **Project directory:** `/var/www/SLC`
- **Python:** 3.13
- **Django:** 5.2.x
- **Database:** PostgreSQL 16
- **Web server:** Nginx
- **Application server:** Gunicorn
- **Domain:** https://slcdb.de
- **HTTPS:** Let's Encrypt / Certbot

Server administration is performed via SSH using individual Linux accounts. SSH access is restricted by the Hetzner Cloud Firewall and public-key authentication.

## 2. Application Code and Versioning

Repository:

https://github.com/DavidOhlendorf/SLC-Database

The application code is located on the production server at:

`/var/www/SLC`

Production deployments are based on explicitly selected GitHub releases (Git tags), rather than automatically tracking the newest commit on `main`.

The production repository may therefore be in a *detached HEAD* state. This is intentional.

Changes are developed and tested locally, committed to GitHub and subsequently deployed as a release.

## 3. Python Environment

The Python virtual environment is located at:

`/var/www/SLC/venv`

It can be activated using:

`source /var/www/SLC/venv/bin/activate`

Python dependencies are defined in:

`/var/www/SLC/requirements.txt`

The virtual environment is not part of the Git repository.

## 4. Environment Variables

The production environment configuration is stored in:

`/var/www/SLC/.env`

It contains environment-specific and sensitive settings, including database credentials and the Django secret key.

The file is excluded from Git version control.

File permissions are restricted to the owning Linux user (`slcdbadmin`, mode `600`).


## 5. PostgreSQL Database

PostgreSQL runs locally on the production server.

The database is accessed by Django using the connection settings defined in the production `.env` file.

The database contents are not stored in the Git repository.

Database maintenance, backups and recovery procedures are documented separately in the administration manual.

## 6. Static and Media Files

Static source files are located in:

`/var/www/SLC/static/`

For production, Django collects static files into:

`/var/www/SLC/staticfiles/`

Command:

`python manage.py collectstatic --noinput`

Nginx serves the collected files directly under `/static/`.

Uploaded media files are stored in:

`/var/www/SLC/media/`

The additional directory `/var/www/SLC/private_uploads/` is used for private uploads.

Generated static files and uploaded files are not maintained through Git.

## 7. Gunicorn Configuration

Gunicorn runs as a systemd service.

Service configuration:

`/etc/systemd/system/gunicorn.service`

- **User:** `slcdbadmin`
- **Group:** `www-data`
- **Working directory:** `/var/www/SLC`
- **Executable:** `/var/www/SLC/venv/bin/gunicorn`
- **Workers:** 3
- **Bind address:** `127.0.0.1:8000`
- **Application:** `SLC.wsgi:application`

Gunicorn is accessible locally on the server; incoming web requests are forwarded by Nginx.

## 8. Nginx Configuration

Nginx configuration:

`/etc/nginx/sites-available/slcdb`

Nginx is responsible for:

- Handling incoming HTTP and HTTPS connections
- Forwarding application requests to Gunicorn at `127.0.0.1:8000`
- Serving static files from `/var/www/SLC/staticfiles/`
- Serving media files from `/var/www/SLC/media/`
- Using TLS certificates provided by Let's Encrypt

## 9. Production Deployment

Production updates are performed manually and are based on a specific release tag.

The general deployment procedure is:

1. Connect to the production server using SSH.
2. Change to `/var/www/SLC`.
3. Fetch the latest Git tags.
4. Check out the intended release tag.
5. Activate the Python virtual environment.
6. Install or update Python dependencies if necessary.
7. Apply database migrations.
8. Collect static files.
9. Restart Gunicorn.
10. Verify that the application is accessible and functioning correctly.

Example commands (replace `vX.Y.Z` with the intended release):

```bash
cd /var/www/SLC
git fetch --tags
git switch --detach vX.Y.Z

source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput

sudo systemctl restart gunicorn
```

Before deployment, verify the intended release, the repository state and database backup availability.

Nginx normally does not need to be restarted when only the Django application is updated.

Detailed deployment, verification and rollback procedures are documented in the administration manual.

---

*Documentation updated: October 2026.*