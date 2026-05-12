# apps/inspections/tasks.py

from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


# Decide if schedule should run today
def should_run_today(inspection_type, now):

    if inspection_type == 'DAILY':
        # Skip Sunday
        if now.weekday() == 6:
            return False

        return True

    elif inspection_type == 'WEEKLY':
        return now.weekday() == 0  

    elif inspection_type == 'MONTHLY':
        return now.day == 1

    elif inspection_type == 'QUARTERLY':
        return now.day == 1 and now.month in [4, 7, 10, 1]
    # ADD this case in should_run_today
    elif inspection_type == 'ANNUAL':
        return now.day == 1 and now.month == 4
    return False

# Get schedule period & dates
def get_schedule_dates(inspection_type, now):

    if inspection_type == 'DAILY':
        start = now
        end = now + timezone.timedelta(days=1)
        scheduled_date = now.date()

    elif inspection_type == 'WEEKLY':
        start = now - timezone.timedelta(days=now.weekday())
        end = start + timezone.timedelta(days=7)
        scheduled_date = start.date()

    elif inspection_type == 'MONTHLY':
        start = now.replace(day=1)

        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        scheduled_date = start.date()

    elif inspection_type == 'QUARTERLY':
        # FY Quarter Mapping
        # Apr-Jun = Q1
        # Jul-Sep = Q2
        # Oct-Dec = Q3
        # Jan-Mar = Q4
        if now.month in [4, 5, 6]:
            start_month = 4
        elif now.month in [7, 8, 9]:
            start_month = 7
        elif now.month in [10, 11, 12]:
            start_month = 10
        else:
            start_month = 1
        start = now.replace(month=start_month, day=1)
        if start_month == 1:
            end = start.replace(month=4)
        elif start_month == 10:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start_month + 3)

        scheduled_date = start.date()
    
    elif inspection_type == 'ANNUAL':
        # FY = Apr → Mar
        if now.month >= 4:
            start = now.replace(month=4, day=1)
            end = start.replace(year=start.year + 1,month=4,day=1)
        else:
            start = now.replace(year=now.year - 1,month=4,day=1)
            end = start.replace(year=start.year + 1,month=4,day=1)
        scheduled_date = start.date()

    else:
        return None, None, None, None

    # due_date = scheduled_date + timezone.timedelta(
    #     days=config.due_date_offset_days
    # )

    # DAILY
    if inspection_type == 'DAILY':
        due_date = scheduled_date
    # WEEKLY
    elif inspection_type == 'WEEKLY':
        due_date = scheduled_date + timezone.timedelta(days=6)
    # MONTHLY
    elif inspection_type == 'MONTHLY':
        due_date = end.date() - timezone.timedelta(days=1)
    # QUARTERLY
    elif inspection_type == 'QUARTERLY':
        due_date = end.date() - timezone.timedelta(days=1)
    # ANNUAL
    elif inspection_type == 'ANNUAL':
        due_date = end.date() - timezone.timedelta(days=1)
    else:
        due_date = scheduled_date

    return scheduled_date, start.date(), end.date(), due_date

# MAIN TASK
@shared_task(bind=True, max_retries=3)
def auto_create_inspection_schedules(self):
    """
    Runs on 1st of every month.
    For each active, non-paused TemplateAutoScheduleConfig:
    - Creates one InspectionSchedule per assigned user
    - Skips if schedule already exists for this month + template + user
    - Sends notification to each assigned user
    """
    from .models import (
        TemplateAutoScheduleConfig,
        InspectionSchedule,
    )
    from apps.notifications.services import NotificationService

    now = timezone.now()

    # for testing perpose
    # from datetime import datetime

    # now = timezone.make_aware(
    #     datetime(2029, 4, 1, 9, 0, 0)
    #     # year - month - date - hours - minutes
    # )

    logger.info(f"[AutoSchedule] Running at {now}")

    # Get all active, non-paused configs
    configs = TemplateAutoScheduleConfig.objects.filter(is_active=True,is_paused=False).prefetch_related('plants','zones','locations','sublocations','assigned_users','template')

    total_created = 0
    total_skipped = 0
    total_errors = 0

    for config in configs:
        try:
            template = config.template
            logger.info(f"[AutoSchedule] Config {config.id} | Type: {template.inspection_type}")

            # Skip inactive template
            if not template.is_active:
                continue

            inspection_type = template.inspection_type

            # Run only on correct day
            if not should_run_today(inspection_type, now):
                continue

            # Get dates
            scheduled_date, period_start, period_end, due_date = get_schedule_dates(
                inspection_type,
                now,
            )

            # Stop recurring generation after scheduled_end_date
            original_schedule = InspectionSchedule.objects.filter(
                template=template,
                scheduled_end_date__isnull=False
            ).order_by('created_at').first()

            if (
                original_schedule and
                original_schedule.scheduled_end_date and
                scheduled_date > original_schedule.scheduled_end_date
            ):
                logger.info(
                    f"[AutoSchedule] Stopped for template "
                    f"{template.id} due to scheduled_end_date"
                )
                continue

            if not scheduled_date:
                continue

            # Users
            assigned_users = config.assigned_users.filter(is_active=True,is_active_employee=True)

            if not assigned_users.exists():
                logger.warning(f"[AutoSchedule] No users in config {config.id}")
                continue

            # Plants
            plants = config.plants.filter(is_active=True)
            if not plants.exists():
                logger.warning(f"[AutoSchedule] No plants in config {config.id}")
                continue

            # Create schedules per user
            for user in assigned_users:
                try:
                    with transaction.atomic():
                        # Check if schedule already exists for this
                        # month + template + user to avoid duplicates
                        print(
                            "CHECKING:",
                            template.id,
                            user.id,
                            scheduled_date
                        )
                        already_exists = InspectionSchedule.objects.filter(
                            template=template,
                            assigned_to=user,
                            scheduled_date=scheduled_date  
                        ).exists()

                        print("ALREADY EXISTS:", already_exists)

                        if already_exists:
                            total_skipped += 1
                            continue
                        
                        original_schedule = InspectionSchedule.objects.filter(
                            template=template,
                            scheduled_end_date__isnull=False
                        ).order_by('created_at').first()

                        InspectionSchedule.objects.filter(
                            template=template,
                            assigned_to=user,
                            status__in=['SCHEDULED', 'IN_PROGRESS'],
                            scheduled_date__lt=scheduled_date
                        ).update(status='OVERDUE')
                        # Create schedule
                        schedule = InspectionSchedule.objects.create(
                            template=template,
                            assigned_to=user,
                            # assigned_by=None,  # system-created
                            assigned_by=(original_schedule.assigned_by if original_schedule else None),
                            scheduled_date=scheduled_date,
                            scheduled_end_date=(original_schedule.scheduled_end_date
                                if original_schedule else None),
                            due_date=due_date,
                            status='SCHEDULED',
                            auto_schedule_config=config,
                            assignment_notes=(f"Auto-created for {inspection_type} "f"({scheduled_date})"))

                        # Set M2M
                        schedule.plants.set(plants)
                        schedule.zones.set(config.zones.all())
                        schedule.locations.set(config.locations.all())
                        schedule.sublocations.set(config.sublocations.all())

                        total_created += 1
                        logger.info(
                            f"[AutoSchedule] Created {schedule.schedule_code} "
                            f"for {user.get_full_name()}"
                        )

                        # Send notification
                        try:
                            NotificationService.notify(
                                content_object=schedule,
                                notification_type='INSPECTION_SCHEDULE',
                                module='INSPECTION'
                            )
                        except Exception as notif_error:
                            logger.error(f"[AutoSchedule] Notification error: {notif_error}")

                except Exception as user_error:
                    total_errors += 1
                    logger.error(f"[AutoSchedule] Error for user {user.id}: {user_error}")

        except Exception as config_error:
            total_errors += 1
            logger.error(f"[AutoSchedule] Config error {config.id}: {config_error}")
    logger.info(f"[AutoSchedule] Done | Created: {total_created} | "f"Skipped: {total_skipped} | Errors: {total_errors}")

    return {'created': total_created,'skipped': total_skipped,'errors': total_errors}