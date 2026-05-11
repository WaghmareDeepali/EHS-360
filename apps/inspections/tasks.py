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
        return now.day == 1 and now.month in [1, 4, 7, 10]
    # ADD this case in should_run_today
    elif inspection_type == 'ANNUAL':
        return now.day == 1 and now.month == 1  # 1st January
    return False

# Get schedule period & dates
def get_schedule_dates(inspection_type, now, config):

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
        quarter = (now.month - 1) // 3 + 1
        start_month = 3 * (quarter - 1) + 1

        start = now.replace(month=start_month, day=1)

        if start_month + 3 > 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start_month + 3)

        scheduled_date = start.date()
    
    elif inspection_type == 'ANNUAL':
        start = now.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
        scheduled_date = start.date()

    else:
        return None, None, None, None

    due_date = scheduled_date + timezone.timedelta(
        days=config.due_date_offset_days
    )

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
    # from datetime import datetime

    # now = timezone.make_aware(
    #     datetime(2027, 5, 12, 9, 0, 0)
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
                config
            )

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
                        already_exists = InspectionSchedule.objects.filter(
                            template=template,
                            assigned_to=user,
                            scheduled_date=scheduled_date  
                        ).exists()

                        if already_exists:
                            total_skipped += 1
                            continue
                        
                        original_schedule = InspectionSchedule.objects.filter(
                            template=template,
                            assigned_by__isnull=False
                        ).order_by('created_at').first()
                        # Create schedule
                        schedule = InspectionSchedule.objects.create(
                            template=template,
                            assigned_to=user,
                            # assigned_by=None,  # system-created
                            assigned_by=(original_schedule.assigned_by if original_schedule else None),
                            scheduled_date=scheduled_date,
                            due_date=due_date,
                            status='SCHEDULED',
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