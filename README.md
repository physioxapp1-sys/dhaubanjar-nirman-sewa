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
| `hero.svg` | Hero photo, right half | 1600 × 1200 |
| `about.svg` | About section | 800 × 720 |
| `p1`–`p6.svg` | Portfolio grid | 600 × 440 |
| `avatar-1`–`3.svg` | Testimonial portraits | 128 × 128 |

**2. Wire up the forms.** Both forms validate in the browser but do not submit
anywhere yet — see the comment in `wireForm()` in `assets/js/main.js`. Replace the
`setTimeout` block with a `fetch()` to Formspree, Netlify Forms, or your own
endpoint.

Also replace the placeholder phone number (`+977 98-0000-0000`) and email address,
which appear in the contact section and the footer.

## Colours

All colours are CSS custom properties in `:root` at the top of `styles.css`.
Changing `--gold`, `--cream` and `--espresso` re-themes the whole site.
