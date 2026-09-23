# Deploying the Django app on cPanel

The site is served by Django through Passenger. This doc is written from the
actual first deployment, including the two things that broke it silently —
read the two warning boxes below before you start, they will save you hours.

## 0. Clone as a plain folder — do NOT use cPanel's Git Version Control UI

```bash
cd ~/
git clone https://github.com/physioxapp1-sys/dhaubanjar-nirman-sewa.git
```

This must be a plain `git clone` landing at `~/dhaubanjar-nirman-sewa`, **not**
a repo added through cPanel's **Git Version Control** page. That feature clones
into `~/repositories/<name>` with tighter default permissions than a normal
folder — tight enough that LiteSpeed's Passenger worker could never traverse
into it. The app showed as "started" in cPanel, `.htaccess` had the correct
`PassengerAppRoot` directives, and yet no process ever spawned; every request,
including made-up URLs, fell through to a generic LiteSpeed 404. `ps -u
<user> -f | grep passenger` showed worker processes for every *other* Python
app on the account and none for this one — that absence is the tell.

Moving the deployed copy to a plain folder fixed it immediately, matching how
this account's other working Python apps are already set up (their app root
*is* a plain folder directly under `~/`).

## 1. Create the Python app

cPanel → **Setup Python App** → Create Application:

| Field | Value |
|---|---|
| Python version | 3.11 (or the closest available) |
| Application root | `dhaubanjar-nirman-sewa` |
| Application URL | `dhaubanjarnirmansewa.com.np` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

Save. cPanel creates a virtualenv and prints the `source ...activate` command —
copy it, you need it for every step below.

> **cPanel overwrites `passenger_wsgi.py` with a broken template on
> Create.** Its auto-generated stub is:
> ```python
> import imp, os, sys
> sys.path.insert(0, os.path.dirname(__file__))
> wsgi = imp.load_source('wsgi', 'passenger_wsgi.py')
> application = wsgi.application
> ```
> That line reloads the very file it's already running, under a different
> module name, which reloads itself again — infinite recursion. Passenger
> shows no error for this anywhere in the UI; you only see it by running the
> file directly and reading the traceback. **Immediately after every Create
> (or any edit to the app's fields), run:**
> ```bash
> cd ~/dhaubanjar-nirman-sewa
> git checkout -- passenger_wsgi.py
> ```
> before testing anything else. The repo's version is six lines and calls
> `get_wsgi_application()` directly — no `imp.load_source`.

## 2. Create the MySQL database

cPanel → **MySQL Databases**. Create a database and a user, then add the user
to the database with ALL PRIVILEGES. cPanel prefixes both with your account
name, so they end up looking like `madhyapu_dhaubanjar`.

This mirrors the local setup in the README: same engine, same kind of dedicated
user, so the only difference between environments is the values in `.env`.

## 3. Configure the environment

```bash
cd ~/dhaubanjar-nirman-sewa
cp .env.example .env
nano .env          # set SECRET_KEY, DB_NAME, DB_USER, DB_PASSWORD
chmod 600 .env
mkdir -p tmp
```

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

`.env` is gitignored and must never be committed. Quote any password
containing `#`, `$`, `` ` `` or spaces (`DB_PASSWORD='...'`) — `python-dotenv`
handles quoted and unquoted values identically, but quoting is cheap insurance
against a shell-special character being misread.

## 4. Install and migrate

```bash
source ~/virtualenv/dhaubanjar-nirman-sewa/3.11/bin/activate
cd ~/dhaubanjar-nirman-sewa
git checkout -- passenger_wsgi.py     # see the warning in step 1
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py import_catalog ~/pakka-homes/xlsx/data.xlsx
touch tmp/restart.txt
```

## 5. Static and media files

WhiteNoise serves `/static/` from inside the app, which is why `collectstatic`
must run before the first request. Files get hashed names and a one-year
immutable cache, so a deploy invalidates them automatically and browsers never
serve a stale stylesheet.

`/media/` (images uploaded through the admin) is served by Django itself. That
is slower than Apache would be and is a deliberate trade at this scale; move it
to an Apache alias if image traffic ever grows.

**If you skip `collectstatic`, the site raises an error rather than rendering
unstyled** — the manifest storage treats a missing file as a hard failure. That
is intentional: a loud failure at deploy time beats a silently broken page.

## 6. Deploying changes

Install the hook once:

```bash
cd ~/dhaubanjar-nirman-sewa
chmod +x deploy.sh
ln -sf ../deploy.sh .git/hooks/post-merge
```

From then on:

```bash
cd ~/dhaubanjar-nirman-sewa && git pull
```

`deploy.sh` runs `collectstatic`, applies migrations and touches
`tmp/restart.txt`. It calls the virtualenv's Python directly
(`~/virtualenv/dhaubanjar-nirman-sewa/3.11/bin/python`) since the venv isn't
active inside a git hook; override with `VENV_PY=/path/to/python ./deploy.sh`
if that path ever changes.

If `requirements.txt` changed, activate the venv and run `pip install -r
requirements.txt` by hand first — the hook does not do this automatically.

## Checks

```bash
ps -u "$(whoami)" -f | grep -i passenger
# expect a line ending .../dhaubanjar-nirman-sewa/passenger_wsgi.py -
# if it's missing, the worker never started; see step 0.

curl -s https://www.dhaubanjarnirmansewa.com.np/api/v1/health/
# {"status": "ok", "database": true}
```

If you get LiteSpeed's own 404 page (a large "404" heading, dark-mode CSS) on
a URL that isn't even in `urls.py`, that's not Django responding — it means
no worker process exists at all. Check `ps` above before looking at Django's
own logs.

**Do not set `DEBUG=True` on the live server.** It exposes settings and
tracebacks, including database credentials, to anyone who triggers an error.
