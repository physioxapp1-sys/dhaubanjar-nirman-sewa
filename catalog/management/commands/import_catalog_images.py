"""
Attach catalog tile images to subcategories.

The app used to ship these images in its APK and draw tile N from the Nth
file, pairing it with the Nth subcategory from the API. That pairing is
positional, so the moment a subcategory is added, removed or reordered in
admin, every tile after it shows someone else's name and rate. It had already
drifted: five service categories were out, and grocery was showing Rice's rate
under Vegetables & Fruits.

So the images live here now and the app renders what the API gives it. Which
image belongs to which subcategory comes from mapping.json next to the files -
read off the labels printed in the images themselves, not assumed from file
order, because cleaning 8-10 and painting 6-8 are not in catalog order.

    python manage.py import_catalog_images                 # services
    python manage.py import_catalog_images --vertical shop
    python manage.py import_catalog_images --replace       # overwrite existing
    python manage.py import_catalog_images --dry-run       # report, change nothing
"""
# A folder whose mapping is "by-filename" is matched on the file name instead,
# which is what newer artwork does: deep-cleaning.png belongs to Deep Cleaning
# and nothing has to agree about ordering.
import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils.text import slugify

from catalog.models import Category, Subcategory, Vertical

# Pictures for the categories themselves rather than what is inside them, in a
# folder of that name beside them. Always matched on the file name - there is
# no ordering to get wrong, and a category list is short enough to name.
CATEGORY_FOLDER = "_categories"

BUNDLED = Path(__file__).resolve().parents[2] / "seed_images"
SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# A mapping value of this, instead of a list of names, means the files in that
# folder are named after the subcategory they belong to.
BY_FILENAME = "by-filename"

# The folder under seed_images/ for each vertical. They are named for the
# section as the app speaks of it, not for the Vertical constant.
FOLDERS = {
    Vertical.SERVICE: "services",
    Vertical.SHOP: "shop",
    Vertical.RENTAL: "rentals",
}


class Command(BaseCommand):
    help = "Attach subcategory tile images, matched by the mapping file."

    def _categories(self, folder, vertical, opts):
        """Attach the category pictures, if there are any.

        A category is a different row from the services under it - Maintenance
        lists Plumbing and Electrical, and those tiles want a picture of the
        trade, not of one job within it.
        """
        source = folder / CATEGORY_FOLDER
        if not source.is_dir():
            return 0

        self.stdout.write(self.style.MIGRATE_HEADING("Categories"))
        attached = 0
        for path in sorted(p for p in source.iterdir() if p.suffix.lower() in SUFFIXES):
            category = Category.objects.filter(
                vertical=vertical, slug=slugify(path.stem)[:140]
            ).first()
            if category is None:
                self.stdout.write(
                    self.style.WARNING(f"  no category '{path.stem}' - skipped")
                )
                self._unmatched += 1
                continue
            if category.image and not opts["replace"]:
                self.stdout.write(f"  {category.name}: already has an image - left alone")
                self._skipped += 1
                continue

            target = f"{category.slug}{path.suffix.lower()}"
            if opts["dry_run"]:
                self.stdout.write(f"  {category.name}  <-  {path.name}  (as {target})")
            else:
                with path.open("rb") as handle:
                    category.image.save(target, File(handle), save=True)
                self.stdout.write(self.style.SUCCESS(f"  {category.name}  <-  {path.name}"))
            attached += 1
        return attached

    def add_arguments(self, parser):
        parser.add_argument(
            "--vertical",
            default=Vertical.SERVICE,
            choices=[v for v in FOLDERS],
            help="Which section to load. Defaults to service.",
        )
        parser.add_argument("--folder", help=f"Defaults to {BUNDLED}/<section>.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Overwrite images already set. Without this they are left alone.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen and write nothing.",
        )

    def handle(self, *args, **opts):
        vertical = opts["vertical"]
        folder = (
            Path(opts["folder"]).expanduser()
            if opts["folder"]
            else BUNDLED / FOLDERS[vertical]
        )
        if not folder.is_dir():
            raise CommandError(f"Not a folder: {folder}")

        mapping_file = folder / "mapping.json"
        if not mapping_file.is_file():
            raise CommandError(
                f"No mapping.json in {folder}. Without it the only way to pair an "
                f"image with a subcategory is file order, which is what this "
                f"command exists to stop relying on."
            )
        mapping = json.loads(mapping_file.read_text(encoding="utf-8"))

        attached = skipped = unmatched = 0
        dry = opts["dry_run"]
        self._skipped = self._unmatched = 0

        attached += self._categories(folder, vertical, opts)

        for category_folder in sorted(p for p in folder.iterdir() if p.is_dir()):
            if category_folder.name == CATEGORY_FOLDER:
                continue
            names = mapping.get(category_folder.name)
            if not names:
                self.stdout.write(
                    self.style.WARNING(
                        f"{category_folder.name}: not in mapping.json - skipped"
                    )
                )
                continue
            # "by-filename" for a folder whose files are named after the
            # service rather than numbered - there is nothing to line up, so
            # there is nothing to line up wrongly.
            by_filename = names == BY_FILENAME

            category = Category.objects.filter(
                vertical=vertical, slug=category_folder.name
            ).first()
            if category is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"{category_folder.name}: no such category - skipped"
                    )
                )
                continue

            self.stdout.write(self.style.MIGRATE_HEADING(category.name))

            files = sorted(
                (p for p in category_folder.iterdir() if p.suffix.lower() in SUFFIXES),
                key=lambda p: int(p.stem) if p.stem.isdigit() else 0,
            )
            for path in files:
                if by_filename:
                    slug, name = slugify(path.stem)[:180], path.stem
                else:
                    index = int(path.stem) if path.stem.isdigit() else 0
                    if not 1 <= index <= len(names):
                        self.stdout.write(
                            f"  {path.name}: nothing mapped to it - skipped"
                        )
                        unmatched += 1
                        continue
                    name = names[index - 1]
                    slug = slugify(name)[:180]

                subcategory = Subcategory.objects.filter(
                    category=category, slug=slug
                ).first()
                if subcategory is None:
                    self.stdout.write(
                        self.style.WARNING(f"  no subcategory '{name}' - skipped")
                    )
                    unmatched += 1
                    continue
                name = subcategory.name

                if subcategory.image and not opts["replace"]:
                    self.stdout.write(f"  {name}: already has an image - left alone")
                    skipped += 1
                    continue

                target = f"{category.slug}-{subcategory.slug}{path.suffix.lower()}"
                if dry:
                    self.stdout.write(f"  {name}  <-  {path.name}  (as {target})")
                else:
                    with path.open("rb") as handle:
                        subcategory.image.save(target, File(handle), save=True)
                    self.stdout.write(self.style.SUCCESS(f"  {name}  <-  {path.name}"))
                attached += 1

        skipped += self._skipped
        unmatched += self._unmatched

        # The ones with no picture matter as much as the ones with: they are
        # what will render a placeholder in the app.
        bare = (
            Subcategory.objects.filter(category__vertical=vertical, is_active=True)
            # The field is null=True as well as blank=True, so an untouched
            # row can be either.
            .filter(Q(image="") | Q(image__isnull=True))
            .select_related("category")
            .order_by("category__sort_order", "sort_order")
        )
        if bare:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(f"{bare.count()} subcategories still have no image:")
            )
            for sub in bare[:40]:
                self.stdout.write(f"  {sub.category.name} / {sub.name}")
            if bare.count() > 40:
                self.stdout.write(f"  ... and {bare.count() - 40} more")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would attach' if dry else 'Attached'} {attached}, "
                f"left {skipped} alone, {unmatched} unmatched."
            )
        )
