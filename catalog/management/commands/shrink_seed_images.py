"""
Resize and recompress the seed images so a screen does not cost a megabyte.

A tile is drawn at about 170pt, which is roughly 500px on a 3x phone, and was
being served at 127KB median and 448KB at worst - a grocery aisle pulled 1.5MB
for four pictures.

Two things were wrong, and the format mattered more than the dimensions: these
are photographs stored as PNG, which is a format for flat artwork. They are
written out as WebP, which carries transparency like PNG and compresses
photographs like JPEG, so the cut-outs keep their alpha and everything else
gets small.

The extension changes but the stem does not, and both image importers match on
the stem - so `1.png` becomes `1.webp` and its mapping still finds it.

Originals are kept in an `_originals/` folder beside each file, because a
recompression is not reversible and the photographs are not ours to lose.

    python manage.py shrink_seed_images --dry-run
    python manage.py shrink_seed_images
"""
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

SEED_ROOTS = ["catalog/seed_images", "products/seed_images"]
ORIGINALS = "_originals"
SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# Tiles render around 170pt; 600 covers a 3x screen with room to spare.
# Products are drawn full width on the detail screen, so they keep more.
DEFAULT_WIDTH = 600
PRODUCT_WIDTH = 900


class Command(BaseCommand):
    help = "Resize and recompress the bundled seed images."

    def add_arguments(self, parser):
        parser.add_argument("--max-width", type=int,
                            help=f"Longest side. Defaults to {DEFAULT_WIDTH}, "
                                 f"or {PRODUCT_WIDTH} under products/.")
        parser.add_argument("--quality", type=int, default=82,
                            help="JPEG/WebP quality. Default 82.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change and write nothing.")

    def handle(self, *args, **opts):
        try:
            from PIL import Image
        except ImportError:
            raise CommandError("Pillow is needed for this. pip install Pillow")

        quality = opts["quality"]
        dry = opts["dry_run"]
        before = after = 0
        touched = skipped = 0

        for root in SEED_ROOTS:
            base = Path(root)
            if not base.is_dir():
                continue
            is_products = "products" in base.parts
            width = opts["max_width"] or (PRODUCT_WIDTH if is_products
                                          else DEFAULT_WIDTH)

            for path in sorted(base.rglob("*")):
                if path.suffix.lower() not in SUFFIXES:
                    continue
                if ORIGINALS in path.parts:
                    continue

                size_before = path.stat().st_size
                with Image.open(path) as im:
                    im.load()
                    w, h = im.size
                    has_alpha = im.mode in ("RGBA", "LA") or (
                        im.mode == "P" and "transparency" in im.info)

                    # Even a small PNG photograph is worth rewriting - the
                    # format is most of the cost.
                    if path.suffix.lower() == ".webp" and max(w, h) <= width:
                        skipped += 1
                        continue

                    scale = min(1.0, width / max(w, h))
                    target = (round(w * scale), round(h * scale))

                    if dry:
                        self.stdout.write(
                            "  %-54s %dx%d %dKB -> %dx%d webp"
                            % (path, w, h, size_before // 1024, *target))
                        before += size_before
                        touched += 1
                        continue

                    # Keep the untouched file once, the first time it changes.
                    backup = path.parent / ORIGINALS / path.name
                    if not backup.exists():
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, backup)

                    out = im.resize(target, Image.LANCZOS) if scale < 1 else im
                    out = out.convert("RGBA" if has_alpha else "RGB")
                    target_path = path.with_suffix(".webp")
                    out.save(target_path, "WEBP", quality=quality, method=6)

                if target_path != path:
                    path.unlink()
                path = target_path
                size_after = path.stat().st_size
                before += size_before
                after += size_after
                touched += 1
                self.stdout.write(
                    "  %-58s %dKB -> %dKB" % (path, size_before // 1024,
                                              size_after // 1024))

        self.stdout.write("")
        if dry:
            self.stdout.write(self.style.SUCCESS(
                "%d would change, %d already small enough (%.1f MB today)"
                % (touched, skipped, before / 1e6)))
        else:
            self.stdout.write(self.style.SUCCESS(
                "%d resized, %d left alone: %.1f MB -> %.1f MB (%.0f%% smaller). "
                "Originals are in %s/ beside each file."
                % (touched, skipped, before / 1e6, after / 1e6,
                   100 * (1 - after / before) if before else 0, ORIGINALS)))
            self.stdout.write(
                "Run import_catalog_images --replace and "
                "import_product_images --replace to push them to the database.")
