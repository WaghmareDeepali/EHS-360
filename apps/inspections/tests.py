from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.inspections.models import InspectionSchedule, InspectionTemplate
from apps.inspections.views import _get_inspection_completion_status
from apps.notifications.services import NotificationService


class ScheduleRestartNotificationTests(TestCase):
    def setUp(self):
        self.assigned_to = User.objects.create_user(
            username='hod.one',
            email='hod.one@example.com',
            password='test-pass-123',
            first_name='Hod',
            last_name='One',
        )
        self.template = InspectionTemplate.objects.create(
            template_name='Restart Regression Template',
            inspection_type='DAILY',
            created_by=self.assigned_to,
        )

        today = timezone.localdate()
        self.schedule = InspectionSchedule.objects.create(
            template=self.template,
            assigned_to=self.assigned_to,
            assigned_by=None,
            scheduled_date=today - timedelta(days=2),
            due_date=today - timedelta(days=1),
            status='OVERDUE',
        )

    def test_build_inspection_context_handles_missing_assigned_by(self):
        context = NotificationService._build_inspection_context(self.schedule)

        self.assertIn('Assigned By        : N/A', context['message'])

    @patch.object(NotificationService, 'send_email', return_value=True)
    def test_restart_overdue_schedule_without_assigned_by_reuses_same_record(self, mock_send_email):
        self.client.force_login(self.assigned_to)

        response = self.client.get(
            reverse('inspections:schedule_restart', args=[self.schedule.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(InspectionSchedule.objects.count(), 1)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status, 'IN_PROGRESS')
        self.assertIn(f'[RESTARTED_FROM:{self.schedule.schedule_code}]', self.schedule.assignment_notes)
        self.assertEqual(
            response.url,
            reverse('inspections:inspection_start', args=[self.schedule.pk])
        )
        self.assertTrue(mock_send_email.called)

    def test_completion_helper_marks_restarted_inspections_as_late_close(self):
        self.schedule.assignment_notes = f'[RESTARTED_FROM:{self.schedule.schedule_code}]'

        self.assertEqual(_get_inspection_completion_status(self.schedule), 'LATE_CLOSE')
