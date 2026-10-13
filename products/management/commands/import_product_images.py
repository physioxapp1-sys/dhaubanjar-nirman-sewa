"""
Attach product photos from a folder, matched to products by filename.

`tomato.png` finds the product whose slug is `tomato`. Saves re-uploading a
dozen files one at a time through the admin, and makes a fresh deploy
reproducible rather than something someone has to remember to redo.

Defaults to the copies vendored at products/seed_images/.

    python manage.py import_product_images
    python manage.py import_product_images /path/to/folder
    python manage.py import_product_images --replace   # overwrite existing
"""
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from products.models import Product

BUNDLED = Path(__file__).resolve().parents[2] / "seed_images"
SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class Command(BaseCommand):
    help = "Attach product images from a folder, matched by filename to slug."

    def add_arguments(self, parser):
        parser.add_argument("folder", nargs="?", help=f"Defaults to {BUNDLED}.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Overwrite images already set. Without this they are left alone.",
        )

    def handle(self, *args, **opts):
        folder = Path(opts["folder"]).expanduser() if opts["folder"] else BUNDLED
        if not folder.is_dir():
            raise CommandError(f"Not a folder: {folder}")

        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in SUFFIXES)
        if not files:
            raise CommandError(f"No images in {folder}")

        attached = skipped = unmatched = 0
        for path in files:
            slug = path.stem
            # Slugs are unique per subcategory, not globally, so a name used in
            # two aisles would match more than one product. Name them all.
            matches = list(Product.objects.filter(slug=slug))
            if not matches:
                self.stdout.write(self.style.WARNING(f"  no product '{slug}' - skipped"))
                unmatched += 1
                continue

            for product in matches:
                if product.image and not opts["replace"]:
                    self.stdout.write(f"  {product} already has an image - left alone")
                    skipped += 1
                    continue
                with path.open("rb") as handle:
                    product.image.save(path.name, File(handle), save=True)
                self.stdout.write(self.style.SUCCESS(f"  {product} <- {path.name}"))
                attached += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n{attached} attached, {skipped} left alone, {unmatched} unmatched."
        ))
        if skipped:
            self.stdout.write("Re-run with --replace to overwrite those.")
