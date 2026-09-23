# Dhaubanjar Nirman Sewa — website

Django web app for Dhaubanjar Nirman Sewa. It serves two consumers:

* the **public website** (server-rendered templates)
* the **Pakka Homes** Flutter app, over a JSON API at `/api/v1/`

```bash
pip install -r requirements.txt
cp .env.example .env                      # set SECRET_KEY and DB_* values
```

### Local MySQL

Development uses MySQL, same engine as production, so migrations and queries
behave identically in both. Create the schema and a dedicated app user once:

```bash
cp scripts/create_local_db.sql.example scripts/create_local_db.sql
# put the DB_PASSWORD from your .env into that file, then:
mysql -u root -p < scripts/create_local_db.sql
```

The copy is gitignored because it carries a real password; the `.example`
template never does. The app deliberately does not connect as `root`.

Django creates and drops `test_dhaubanjar` when running tests, which is why the
script grants rights over that name too.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py import_catalog ../pakka-homes/xlsx/data.xlsx
python manage.py runserver
```

`DB_ENGINE=sqlite` still works as an escape hatch if MySQL is unavailable, but
it is not the default — SQLite is lax about constraints and column types that
MySQL enforces, so a green test run there proves less.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/categories/?vertical=service` | Categories in one vertical (`service`, `shop`, `rental`) |
| `GET /api/v1/categories/tree/?vertical=shop` | Whole catalog nested, for the app's first load |
| `GET /api/v1/categories/<slug>/?vertical=service` | One category with its items |
| `GET /api/v1/subcategories/?search=geyser&popular=true` | Flat list; backs search and the popular row |
| `POST /api/v1/enquiries/` | Contact form submissions (rate limited, write-only) |
| `GET /api/v1/health/` | Liveness plus a database check |

Slugs are unique **per vertical**, not globally — `electrical` is both a service and a
shop category — so pass `vertical` when fetching a category by slug.

## Catalog data

`python manage.py import_catalog <path-to-data.xlsx>` loads the Pakka Homes
spreadsheet: 38 categories and 343 items across the three verticals. It is
idempotent, so re-running updates in place rather than duplicating. Rates and
images set in the admin survive a re-import unless you pass `--overwrite-rates`.
`--dry-run` reports what would change; `--prune` deactivates rows dropped from
the sheet.

Everything is editable at `/admin/`.

## Structure

```
config/               settings, urls, wsgi
catalog/              Category + Subcategory, API, xlsx importer
enquiries/            Enquiry model and the write-only submission endpoint
website/              public page views
templates/website/    home.html, robots.txt, sitemap.xml (all served by Django)
assets/css/styles.css single stylesheet; the palette lives in :root at the top
assets/js/main.js     menu, dropdown, scroll spy, counters, slider, filter, forms
assets/img/           hero photo plus placeholder artwork
passenger_wsgi.py     cPanel entry point
```

## Things to change first

**1. Replace the placeholder artwork.** Every image in `assets/img/` is a generated
SVG standing in for a real photo. Drop your own files in and update the `src`
attributes in `templates/website/home.html`:

| File | Used for | Suggested size |
|---|---|---|
| `hero.jpg` + `hero-900.jpg` | Hero photo, right half (real photo; regenerate both sizes together) | 1400 × 768 |
| `about.svg` | About section | 800 × 720 |
| `p1`–`p6.svg` | Portfolio grid | 600 × 440 |
| `avatar-1`–`3.svg` | Testimonial portraits | 128 × 128 |

**2. The contact form now posts to `/api/v1/enquiries/`.** Submissions land in the
admin and trigger a notification email when `EMAIL_HOST` is configured; without it
mail is printed to the log instead. This only works once Django is serving the site
— on the current static deploy the endpoint does not exist.

The phone number is real. The email `info@dhaubanjarnirmansewa.com.np` is still a
placeholder — if you change it, update all three places at once: the contact
section, the footer, and the JSON-LD block in `<head>`. Search engines flag
contact details that disagree between the page and the structured data.

## Deployment

The site is served by Django through Passenger on cPanel, deployed as a
**plain `git clone`** directly at `/home2/madhyapu/dhaubanjar-nirman-sewa` —
deliberately *not* inside cPanel's Git Version Control "repositories/" folder.
That folder's tighter default permissions silently blocked LiteSpeed's
Passenger worker from ever starting: the app showed as "started" in cPanel,
`.htaccess` was correct, but no process was ever spawned and every request
fell through to a generic 404. Moving the deployed copy to a plain folder
(matching how the account's other working Python apps are set up) fixed it.

Install the hook once:

```bash
cd ~/dhaubanjar-nirman-sewa
chmod +x deploy.sh
ln -sf ../deploy.sh .git/hooks/post-merge
```

From then on, deploying is one command:

```bash
cd ~/dhaubanjar-nirman-sewa && git pull
```

`deploy.sh` runs `collectstatic`, applies migrations and touches
`tmp/restart.txt`, which is what makes Passenger reload. It locates the repo
root itself, so it works regardless of the clone's path.

> **The document root must not contain `index.html`, `robots.txt` or
> `sitemap.xml`.** Apache serves matching files directly and Passenger never
> sees the request, so the old static page would silently shadow the app —
> the site looks fine while `/admin/` and `/api/` return 404. Django serves
> all three itself.

> **cPanel's Setup Python App regenerates `passenger_wsgi.py` with a broken
> template on Create/Delete.** Its stub tries to reload itself via
> `imp.load_source('wsgi', 'passenger_wsgi.py')`, which recurses infinitely.
> After creating or recreating the app, always run
> `git checkout -- passenger_wsgi.py` before testing.

Full first-time setup, including the cPanel Python app and the MySQL database,
is in [docs/django-deploy.md](docs/django-deploy.md).

## Colours

All colours are CSS custom properties in `:root` at the top of `styles.css`,
following the design brief:

| Token | Hex | Role |
|---|---|---|
| `--cream` | `#F4F2EE` | alabaster white — page background |
| `--cream-2` | `#E6E1DA` | champagne sand — cards and bands |
| `--espresso` / `--ink` | `#3A332C` | charcoal-bronze — bold typography |
| `--bronze` | `#A38363` | brushed bronze — CTAs and micro-interactions |

`--bronze-dark` (`#7F6448`) exists because `#A38363` only reaches 3.5:1 against
both white and charcoal, which fails WCAG AA for normal-size text. Button fills
and small bronze text use the deeper shade; the exact `#A38363` carries borders,
icons, hover underlines and the hero headline, where the type is large enough to
pass. If you change `--bronze`, re-check those pairs.
