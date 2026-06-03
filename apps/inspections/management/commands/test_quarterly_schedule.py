# apps/inspections/management/commands/test_quarterly_schedule.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.inspections.models import (
    TemplateAutoScheduleConfig,
    InspectionSchedule,
    InspectionTemplate
)
from apps.inspections.tasks import should_run_today, get_schedule_dates
from apps.accounts.models import User
from apps.organizations.models import Plant


class Command(BaseCommand):
    help = 'Test quarterly auto-schedule creation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='QUARTERLY',
            help='Inspection type to test: DAILY, WEEKLY, MONTHLY, QUARTERLY'
        )
        parser.add_argument(
            '--month',
            type=int,
            default=4,
            help='Month to simulate (1-12). Default: 4 (April)'
        )
        parser.add_argument(
            '--day',
            type=int,
            default=1,
            help='Day to simulate. Default: 1'
        )

    def handle(self, *args, **options):
        inspection_type = options['type']
        month = options['month']
        day = options['day']

        # ─── Simulate date ───────────────────────────────────────
        fake_now = timezone.now().replace(
            month=month, day=day, hour=6, minute=0, second=0
        )
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"Simulated date : {fake_now.strftime('%d %B %Y')}")
        self.stdout.write(f"Inspection type: {inspection_type}")
        self.stdout.write(f"{'='*50}\n")

        # ─── Check should_run_today ───────────────────────────────
        should_run = should_run_today(inspection_type, fake_now)
        self.stdout.write(
            self.style.SUCCESS(f"should_run_today: {should_run}")
            if should_run else
            self.style.ERROR(f"should_run_today: {should_run}")
        )

        if not should_run:
            self.stdout.write(self.style.WARNING(
                f"\nTask would NOT run on {fake_now.strftime('%d %B %Y')} "
                f"for type '{inspection_type}'"
            ))
            return

        # ─── Get configs ──────────────────────────────────────────
        configs = TemplateAutoScheduleConfig.objects.filter(
            is_active=True,
            is_paused=False,
            template__inspection_type=inspection_type
        ).prefetch_related('plants', 'zones', 'locations', 'sublocations', 'assigned_users')

        self.stdout.write(f"\nConfigs found: {configs.count()}")

        if not configs.exists():
            self.stdout.write(self.style.WARNING(
                f"No active configs found for type '{inspection_type}'.\n"
                f"Create a schedule with 'Enable Auto Monthly Schedule' checked first."
            ))
            return

        # ─── Process each config ──────────────────────────────────
        total_created = 0
        total_skipped = 0
        total_errors = 0

        for config in configs:
            template = config.template
            self.stdout.write(f"\nConfig ID   : {config.id}")
            self.stdout.write(f"Template    : {template.template_name} ({template.template_code})")
            self.stdout.write(f"Plants      : {', '.join(config.plants.values_list('name', flat=True))}")
            self.stdout.write(f"Users       : {', '.join([u.get_full_name() for u in config.assigned_users.all()])}")
            self.stdout.write(f"Due offset  : {config.due_date_offset_days} days")

            # Get dates
            scheduled_date, period_start, period_end, due_date = get_schedule_dates(
                inspection_type, fake_now
            )
            self.stdout.write(f"\nScheduled date : {scheduled_date}")
            self.stdout.write(f"Period         : {period_start} → {period_end}")
            self.stdout.write(f"Due date       : {due_date}")

            assigned_users = config.assigned_users.filter(
                is_active=True,
                is_active_employee=True
            )
            plants = config.plants.filter(is_active=True)

            self.stdout.write(f"\nProcessing {assigned_users.count()} user(s)...")

            for user in assigned_users:
                # Check duplicate
                already_exists = InspectionSchedule.objects.filter(
                    template=template,
                    assigned_to=user,
                    scheduled_date=scheduled_date
                ).exists()

                if already_exists:
                    self.stdout.write(self.style.WARNING(
                        f"  ⏭  SKIPPED — already exists for {user.get_full_name()}"
                    ))
                    total_skipped += 1
                    continue

                try:
                    with transaction.atomic():
                        schedule = InspectionSchedule.objects.create(
                            template=template,
                            assigned_to=user,
                            assigned_by=None,
                            scheduled_date=scheduled_date,
                            due_date=due_date,
                            status='SCHEDULED',
                            assignment_notes=(
                                f"Auto-created {inspection_type} test "
                                f"({scheduled_date})"
                            )
                        )
                        schedule.plants.set(plants)
                        schedule.zones.set(config.zones.all())
                        schedule.locations.set(config.locations.all())
                        schedule.sublocations.set(config.sublocations.all())
                        schedule.assigned_users.set(assigned_users)

                        total_created += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✅ CREATED: {schedule.schedule_code} "
                            f"for {user.get_full_name()}"
                        ))

                except Exception as e:
                    total_errors += 1
                    self.stdout.write(self.style.ERROR(
                        f"  ❌ ERROR for {user.get_full_name()}: {str(e)}"
                    ))

        # ─── Summary ──────────────────────────────────────────────
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(self.style.SUCCESS(f"Created : {total_created}"))
        self.stdout.write(self.style.WARNING(f"Skipped : {total_skipped}"))
        self.stdout.write(self.style.ERROR(f"Errors  : {total_errors}") if total_errors else f"Errors  : {total_errors}")
        self.stdout.write(f"{'='*50}\n")