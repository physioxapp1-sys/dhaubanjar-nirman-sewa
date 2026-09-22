"""
Load the Pakka Homes catalog from the app's spreadsheet.

The sheets are ragged: row 1 is a header, column A is the main category and
every remaining populated cell on the row is one subcategory. The "Copy"
variant of the workbook interleaves blank 'Rate' columns between the names,
so blank cells are skipped rather than treated as positional.

Idempotent - re-running updates in place and never duplicates. Rates and
images set in the admin are preserved unless --overwrite-rates is passed.

    python manage.py import_catalog ../pakka-homes/xlsx/data.xlsx
    python manage.py import_catalog <path> --dry-run
    python manage.py import_catalog <path> --prune
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Subcategory, Vertical

# Spreadsheet sheet name -> vertical. Sheets not listed here are ignored,
# which is what keeps 'Sheet1'/'Sheet2' scratch tabs out of the database.
SHEET_VERTICALS = {
    "services": Vertical.SERVICE,
    "shop": Vertical.SHOP,
    "rentals": Vertical.RENTAL,
}

# Cells that are structural rather than data.
SKIP_CELLS = {"rate", "alias", "main category", "subcategories", ""}


class Command(BaseCommand):
    help = "Import the Pakka Homes catalog from an xlsx workbook."

    def add_arguments(self, parser):
        parser.add_argument("workbook", type=str, help="Path to data.xlsx")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change without writing.")
        parser.add_argument("--overwrite-rates", action="store_true",
                            help="Reset rates edited in the admin back to the sheet.")
        parser.add_argument("--prune", action="store_true",
                            help="Deactivate rows no longer present in the sheet.")

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError("openpyxl is required: pip install openpyxl") from exc

        path = Path(opts["workbook"]).expanduser()
        if not path.exists():
            raise CommandError(f"Workbook not found: {path}")

        wb = openpyxl.load_workbook(path, data_only=True)
        dry = opts["dry_run"]
        stats = {k: 0 for k in
                 ("cats_new", "cats_upd", "subs_new", "subs_upd", "pruned")}

        with transaction.atomic():
            for sheet_name, vertical in SHEET_VERTICALS.items():
                if sheet_name not in wb.sheetnames:
                    self.stdout.write(self.style.WARNING(
                        f"  sheet '{sheet_name}' not in workbook - skipped"))
                    continue
                self._import_sheet(wb[sheet_name], vertical, opts, stats)

            if dry:
                transaction.set_rollback(True)

        verb = "Would import" if dry else "Imported"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verb}: {stats['cats_new']} new categories, "
            f"{stats['cats_upd']} updated, {stats['subs_new']} new items, "
            f"{stats['subs_upd']} updated, {stats['pruned']} deactivated."
        ))
        if dry:
            self.stdout.write(self.style.WARNING("Dry run - nothing was saved."))

    # ------------------------------------------------------------------
    def _import_sheet(self, ws, vertical, opts, stats):
        self.stdout.write(f"\n{ws.title} -> {vertical}")
        seen_categories = []

        for row in ws.iter_rows(values_only=True):
            cells = [self._clean(c) for c in row]
            cells = [c for c in cells if c]
            if not cells:
                continue

            head, *rest = cells
            if head.lower() in SKIP_CELLS:
                continue

            names = [n for n in rest if n.lower() not in SKIP_CELLS]
            # De-duplicate within a row while keeping sheet order: a couple of
            # rows repeat a name ('Boundary Wall' twice under Construction).
            names = list(dict.fromkeys(names))

            category = self._upsert_category(head, vertical, len(seen_categories), opts, stats)
            seen_categories.append(category.pk if category else None)
            if category is None:
                continue

            seen_subs = []
            for i, name in enumerate(names):
                sub = self._upsert_subcategory(category, name, i, opts, stats)
                if sub:
                    seen_subs.append(sub.pk)

            if opts["prune"] and not opts["dry_run"]:
                stale = category.subcategories.filter(is_active=True).exclude(pk__in=seen_subs)
                stats["pruned"] += stale.update(is_active=False)

            self.stdout.write(f"  {category.name:<26} {len(names):>3} items")

        if opts["prune"] and not opts["dry_run"]:
            stale = Category.objects.filter(vertical=vertical, is_active=True).exclude(
                pk__in=[p for p in seen_categories if p])
            stats["pruned"] += stale.update(is_active=False)

    def _upsert_category(self, name, vertical, order, opts, stats):
        slug = slugify(name)[:140]
        existing = Category.objects.filter(vertical=vertical, name=name).first()
        if existing:
            changed = False
            if existing.sort_order != order:
                existing.sort_order, changed = order, True
            if not existing.is_active:
                existing.is_active, changed = True, True
            if not existing.image_key:
                existing.image_key, changed = slug, True
            if changed and not opts["dry_run"]:
                existing.save()
            stats["cats_upd"] += int(changed)
            return existing

        stats["cats_new"] += 1
        obj = Category(vertical=vertical, name=name, slug=slug,
                       image_key=slug, sort_order=order)
        if not opts["dry_run"]:
            obj.save()
            return obj
        # In a dry run nothing is written, so hand back an unsaved instance
        # only when it can still be used for reporting.
        return obj if obj.pk else None

    def _upsert_subcategory(self, category, name, order, opts, stats):
        if not category.pk:
            return None
        slug = slugify(name)[:180]
        existing = Subcategory.objects.filter(category=category, slug=slug).first()
        if existing:
            changed = False
            if existing.name != name:
                existing.name, changed = name, True
            if existing.sort_order != order:
                existing.sort_order, changed = order, True
            if not existing.is_active:
                existing.is_active, changed = True, True
            if opts["overwrite_rates"] and existing.rate is not None:
                existing.rate, changed = None, True
            if changed and not opts["dry_run"]:
                existing.save()
            stats["subs_upd"] += int(changed)
            return existing

        stats["subs_new"] += 1
        obj = Subcategory(category=category, name=name, slug=slug, sort_order=order)
        if not opts["dry_run"]:
            obj.save()
        return obj

    @staticmethod
    def _clean(value):
        if value is None:
            return ""
        text = str(value).strip()
        # Emoji-only scratch cells and stray numeric markers are not data.
        if text in {"0", "None"}:
            return ""
        return text
