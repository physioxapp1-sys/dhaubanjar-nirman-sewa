# Deploying the Django app on cPanel

The site is currently served as **static files** copied into the document root
by `deploy.sh`. That keeps working and is untouched by these steps. Follow this
document when you want Django to take over serving the site.

## 1. Create the Python app

cPanel → **Setup Python App** → Create Application:

| Field | Value |
|---|---|
| Python version | 3.11 (or the closest available) |
| Application root | `repositories/dhaubanjar-nirman-sewa` |
| Application URL | `dhaubanjarnirmansewa.com.np` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

Save. cPanel creates a virtualenv and prints the `source ...activate` command —
copy it, you need it for every step below.

## 2. Create the MySQL database

cPanel → **MySQL Databases**. Create a database and a user, then add the user
to the database with ALL PRIVILEGES. cPanel prefixes both with your account
name, so they end up looking like `madhyapu_dhaubanjar`.

This mirrors the local setup in the README: same engine, same kind of dedicated
user, so the only difference between environments is the values in `.env`.

## 3. Configure the environment

```bash
cd ~/repositories/dhaubanjar-nirman-sewa
cp .env.example .env
nano .env          # set SECRET_KEY, DB_NAME, DB_USER, DB_PASSWORD
```

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

`.env` is gitignored and must never be committed.

## 4. Install and migrate

```bash
source /home2/madhyapu/virtualenv/repositories/dhaubanjar-nirman-sewa/3.11/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py import_catalog ../../pakka-homes/xlsx/data.xlsx
```

## 5. Serving static files

Passenger does not serve `/static/` itself. `collectstatic` writes to
`staticfiles/`, so point the document root at it or add an alias. The simplest
option on cPanel is to keep copying `assets/` into the document root as now —
the URLs already match.

## 6. Deploying changes

```bash
cd ~/repositories/dhaubanjar-nirman-sewa
git pull
source <virtualenv>/bin/activate
pip install -r requirements.txt      # only when requirements change
python manage.py migrate             # only when migrations are added
python manage.py collectstatic --noinput
touch tmp/restart.txt
```

`touch tmp/restart.txt` is what reloads the app — Passenger watches that file.
Create the directory once with `mkdir -p tmp`.

## Checks

```bash
curl -s https://www.dhaubanjarnirmansewa.com.np/api/v1/health/
# {"status": "ok", "database": true}
```

If you get a 500, the cause is almost always in `stderr.log` in the app root,
and is usually a missing `.env` value or a database permission.

**Do not set `DEBUG=True` on the live server.** It exposes settings and
tracebacks, including database credentials, to anyone who triggers an error.
