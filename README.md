# Dhaubanjar Nirman Sewa — website

Static marketing site for a construction company. No build step, no dependencies —
open `index.html` in a browser, or serve the folder:

```bash
python -m http.server 5173
# http://127.0.0.1:5173
```

## Structure

```
index.html            all sections (hero, services, portfolio, contact, footer)
assets/css/styles.css single stylesheet; the palette lives in :root at the top
assets/js/main.js     menu, dropdown, scroll spy, counters, slider, filter, forms
assets/img/*.svg      placeholder artwork
```

## Things to change first

**1. Replace the placeholder artwork.** Every image in `assets/img/` is a generated
SVG standing in for a real photo. Drop your own files in and update the `src`
attributes in `index.html`:

| File | Used for | Suggested size |
|---|---|---|
| `hero.jpg` + `hero-900.jpg` | Hero photo, right half (real photo; regenerate both sizes together) | 1400 × 768 |
| `about.svg` | About section | 800 × 720 |
| `p1`–`p6.svg` | Portfolio grid | 600 × 440 |
| `avatar-1`–`3.svg` | Testimonial portraits | 128 × 128 |

**2. Wire up the contact form.** It validates in the browser but does not submit
anywhere yet — see the comment in `wireForm()` in `assets/js/main.js`. Replace the
`setTimeout` block with a `fetch()` to Formspree, Netlify Forms, or your own
endpoint.

The phone number is real. The email `info@dhaubanjarnirmansewa.com.np` is still a
placeholder — if you change it, update all three places at once: the contact
section, the footer, and the JSON-LD block in `<head>`. Search engines flag
contact details that disagree between the page and the structured data.

## Deployment

Install the hook once on the server:

```bash
cd ~/repositories/dhaubanjar-nirman-sewa
chmod +x deploy.sh
ln -sf ../../deploy.sh .git/hooks/post-merge
```

From then on, deploying is one command:

```bash
cd ~/repositories/dhaubanjar-nirman-sewa && git pull
```

`deploy.sh` replaces `assets/` wholesale (so removed files do not linger) and
copies `index.html`, `robots.txt` and `sitemap.xml` in place. It never deletes
anything else, so `cgi-bin`, `php.ini`, `.user.ini`, `.well-known` and `.htaccess`
in the document root are untouched. `.cpanel.yml` does the same work for cPanel's
**Deploy HEAD Commit** button, if you prefer clicking.

The canonical hostname is **www.dhaubanjarnirmansewa.com.np**. If it ever changes,
update `index.html` (canonical, `og:url`, `og:image`, and the JSON-LD `@id`, `url`,
`image`, `logo`), `sitemap.xml`, `robots.txt`, and the `.htaccess` redirect.

## Colours

All colours are CSS custom properties in `:root` at the top of `styles.css`.
Changing `--gold`, `--cream` and `--espresso` re-themes the whole site.
