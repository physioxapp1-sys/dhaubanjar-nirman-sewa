"""
Raise this month's rent on every live tenancy.

A rent row has to exist before it can be unpaid, and "unpaid" is what the
whole Rent section is made of - the overdue count, the tenant's next due date,
the owner's expected total. So each month every active lease gets one row,
whether or not anyone has paid.

Idempotent by a unique constraint on (tenancy, period): running it twice, or
running it again after adding a tenancy mid-month, cannot double-bill anyone.

    python manage.py raise_rent                 # this month
    python manage.py raise_rent --month 2026-11
    python manage.py raise_rent --dry-run
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from tenancy.models import RentPayment, Tenancy


class Command(BaseCommand):
    help = "Create this month's rent row for every active tenancy."

    def add_arguments(self, parser):
        parser.add_argument("--month", help="YYYY-MM. Defaults to the current month.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would be raised and write nothing.")

    def handle(self, *args, **opts):
        if opts["month"]:
            try:
                year, month = (int(p) for p in opts["month"].split("-"))
                period = date(year, month, 1)
            except (ValueError, TypeError):
                raise CommandError("--month wants YYYY-MM, e.g. 2026-11")
        else:
            today = date.today()
            period = date(today.year, today.month, 1)

        raised = existing = 0
        for tenancy in Tenancy.objects.filter(
            status=Tenancy.Status.ACTIVE
        ).select_related("property"):
            # Not before the lease starts, and not after it ends.
            if tenancy.start_date > period:
                continue
            if tenancy.end_date and tenancy.end_date < period:
                continue

            if RentPayment.objects.filter(tenancy=tenancy, period=period).exists():
                existing += 1
                continue

            due = tenancy.due_date(period.year, period.month)
            if opts["dry_run"]:
                self.stdout.write(
                    f"  {tenancy.tenant_name} at {tenancy.property.title}: "
                    f"NPR {tenancy.monthly_rent} due {due}"
                )
            else:
                RentPayment.objects.create(
                    tenancy=tenancy,
                    period=period,
                    due_date=due,
                    amount=tenancy.monthly_rent,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"  {tenancy.tenant_name} at {tenancy.property.title}: "
                    f"NPR {tenancy.monthly_rent} due {due}"
                ))
            raised += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{period:%B %Y}: {'would raise' if opts['dry_run'] else 'raised'} "
            f"{raised}, {existing} already there."
        ))
