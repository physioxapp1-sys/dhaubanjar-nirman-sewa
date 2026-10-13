# Catalog tile images

The pictures behind each subcategory tile in the app.

They used to ship inside the APK, with the app drawing tile *N* from the *N*th
file and pairing it with the *N*th row the API returned. That pairing is
positional, so adding, removing or reordering a subcategory in admin put the
wrong name and rate under a picture — and it had already happened in five
service categories. The app now renders whatever the API gives it, so these
live here and get attached to rows in the database:

```bash
python manage.py import_catalog_images              # services
python manage.py import_catalog_images --dry-run    # report, change nothing
python manage.py import_catalog_images --replace    # overwrite existing
```

Re-running is safe: a subcategory that already has an image is left alone
unless `--replace` is passed.

## mapping.json

`services/mapping.json` says which subcategory each numbered file belongs to.
It is not file order — the names were read off the labels printed in the
images, and **cleaning 8–10 and painting 6–8 are not in catalog order**. The
file also records which images have no subcategory to attach to, and which
subcategories have no image.

A folder with no `mapping.json` is skipped rather than guessed at. `shop/` and
`rentals/` are parked here unmapped: nothing in the app reaches those sections
yet, and their folder names do not all match the category slugs
(`electricals` vs `electrical`, `sanitaryware` vs `sanitary-ware`,
`watertanks` vs `water-tanks`, `plumbing` vs `plumbing-materials`). Write a
mapping for them when those sections get built.

## Adding a picture later

Upload it on the subcategory in Django admin. Nothing needs rebuilding and no
app release is involved — the next time someone opens that category it is
there. These files are only the bulk first load, and a record of where the
originals came from.
