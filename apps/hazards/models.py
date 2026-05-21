from django.db import models
from django.contrib.auth import get_user_model
from apps.organizations.models import *
import datetime
from django.utils import timezone
from django.db import transaction

User = get_user_model()


class Hazard(models.Model):
    """
    Hazard Reporting Model
    Supports hazard identification and management
    """
    
    # Detailed Hazard Categories (16 types)
    HAZARD_CATEGORIES = [
        ('electrical', 'Electrical'),
        ('machine_guarding', 'Machine Guarding'),
        ('height_work', 'Height work'),
        ('fire', 'Fire'),
        ('vehicle_including_forklift', 'Vehicle including forklift'),
        ('ppe_violation', 'PPE Violation'),
        ('asbestos_spillage_bag_torn', 'Asbestos Spillage/Bag Torn'),
        ('hot_work', 'Hot work'),
        ('loto', 'LOTO'),
        ('sop_violations', 'SOP Violations'),
        ('unsafe_storage', 'Unsafe Storage'),
        ('slip_trip', 'Slip Trip'),
        ('noise', 'Noise'),
        ('illumination', 'Illumination'),
        ('dust_collection_ventillation', 'Dust collection / Ventillation'),
        ('others', 'Others'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('REPORTED', 'Reported'),
        # ('PENDING_APPROVAL', 'Pending Approval'),
        # ('APPROVED', 'Approved'),
        # ('REJECTED', 'Rejected'),
        # ('UNDER_REVIEW', 'Under Review'),
        ('ACTION_ASSIGNED', 'Action Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending Approval'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    
    HAZARD_TYPE_CHOICES = [
        ('UA', 'Unsafe Act'),
        ('UC', 'Unsafe Condition'),
        ('NM', 'Near Miss')
    ]
    
    hazard_type = models.CharField(
        max_length=2,
        choices=HAZARD_TYPE_CHOICES,
        help_text="UA - Unsafe Act (behavior), UC - Unsafe Condition (environment)"
    )
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hazards_approved"
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    approved_remarks = models.TextField(blank=True)
    
    # Auto-generated Report Number: HAZ-PLANT_CODE-YYYYMMDD-XXX
    report_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    
    # Reporter Information
    reporter_name = models.CharField(max_length=200)
    reporter_email = models.EmailField()
    reporter_phone = models.CharField(max_length=10, blank=True)
    
    # Behalf Information (ForeignKey relationships)

    behalf_person_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Name of the person on whose behalf the report is made"
    )

    # This ForeignKey is no longer actively used by the form but is kept
    # to avoid data loss on existing records. New records will leave this null.
    behalf_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hazards_reported_on_behalf',
        help_text="Employee on whose behalf report is being made"
    )
    behalf_person_dept = models.ForeignKey(
        'organizations.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hazards_on_behalf',
        help_text="Department of person on whose behalf report is being made"
    )
    
    # Basic Hazard Information
    hazard_title = models.CharField(max_length=255)
    hazard_description = models.TextField(help_text="Detailed description of the hazard")
    immediate_action = models.TextField(blank=True)
    hazard_category = models.CharField(max_length=30, choices=HAZARD_CATEGORIES)
    incident_datetime = models.DateTimeField(
        default=timezone.now,
        help_text="Date and time when hazard was identified"
    )
    
    # Risk Assessment
    severity = models.CharField(
        max_length=20, 
        choices=SEVERITY_CHOICES, 
        help_text="Severity level of the hazard"
    )
    
    # Location Information (Using Plant/Zone/Location hierarchy)
    plant = models.ForeignKey(
        Plant, 
        on_delete=models.CASCADE, 
        related_name='hazards',
        help_text="Plant where hazard was identified"
    )
    zone = models.ForeignKey(
        Zone, 
        on_delete=models.CASCADE, 
        related_name='hazards', 
        null=True, 
        blank=True,
        help_text="Zone within the plant"
    )
    location = models.ForeignKey(
        Location, 
        on_delete=models.CASCADE, 
        related_name='hazards',
        help_text="Specific location where hazard exists"
    )
    sublocation = models.ForeignKey(
        SubLocation,
        on_delete=models.SET_NULL,
        related_name='hazards',
        null=True,
        blank=True,
        help_text="Optional: Specific sub-location where hazard was observed"
    )
    location_details = models.TextField(blank=True, help_text="Additional location information")
    
    # GPS Coordinates (Optional)
    # gps_latitude = models.DecimalField(
    #     max_digits=10, 
    #     decimal_places=6, 
    #     null=True, 
    #     blank=True,
    #     help_text="GPS latitude coordinate"
    # )
    # gps_longitude = models.DecimalField(
    #     max_digits=10, 
    #     decimal_places=6, 
    #     null=True, 
    #     blank=True,
    #     help_text="GPS longitude coordinate"
    # )
    
    # Additional Information
    injury_status = models.CharField(
        max_length=10, 
        blank=True,
        help_text="Whether anyone was injured (yes/no)"
    )
    # immediate_action = models.TextField(
    #     blank=True,
    #     help_text="Immediate actions taken to address the hazard"
    # )
    witnesses = models.TextField(
        blank=True,
        help_text="Names and contact details of witnesses"
    )
    
    # System Information
    report_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when report was submitted"
    )   
    user_agent = models.TextField(blank=True, help_text="Browser user agent information")
    report_source = models.CharField(
        max_length=50, 
        default='web_portal',
        help_text="Source of the report (web_portal, mobile_app, etc.)"
    )
    
    # Reporting Information
    reported_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='hazards_reported',
        help_text="User who reported the hazard"
    )
    reported_date = models.DateTimeField(auto_now_add=True)
    
    # Assignment and Status
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hazards_assigned',
        help_text="User assigned to resolve the hazard"
    )
    status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        default='REPORTED',
        db_index=True
    )
    
    # Corrective Actions
    corrective_action_plan = models.TextField(
        blank=True,
        help_text="Planned corrective actions to address the hazard"
    )
    action_deadline = models.DateField(
        null=True, 
        blank=True,
        help_text="Deadline for completing corrective actions"
    )
    action_completed_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date when corrective actions were completed"
    )
    
    # Closure Information
    closure_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date when hazard was closed"
    )
    closure_remarks = models.TextField(
        blank=True,
        help_text="Remarks about hazard closure"
    )
    
    forwarded_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='forwarded_hazards'
    )
    forwarded_from = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True, 
        related_name='forwarding_user'
    )
    forward_reason = models.TextField(blank=True)
    forward_date = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-incident_datetime', '-created_at']
        verbose_name = 'Hazard Report'
        verbose_name_plural = 'Hazard Reports'
        indexes = [
            models.Index(fields=['-incident_datetime']),
            models.Index(fields=['status']),
            models.Index(fields=['severity']),
            models.Index(fields=['hazard_category']),
            models.Index(fields=['plant', 'location']),
        ]
    
    def __str__(self):
        return f"{self.report_number} - {self.hazard_title}"
    
    def save(self, *args, **kwargs):
        # Generate report number if not exists
        if not self.report_number:
            today = datetime.date.today()
            date_str = today.strftime('%Y%m%d')
            plant_code = self.plant.code if self.plant else 'XXX'

            with transaction.atomic():
                last_hazard = Hazard.objects.select_for_update().filter(
                    report_number__startswith=f'HAZ-{plant_code}-{date_str}'
                ).order_by('-report_number').first()

                if last_hazard:
                    last_number = int(last_hazard.report_number.split('-')[-1])
                    new_number = last_number + 1
                else:
                    new_number = 1

                self.report_number = f'HAZ-{plant_code}-{date_str}-{new_number:03d}'

        super().save(*args, **kwargs)
        
    def update_status_from_action_items(self):
        """
        Update hazard status based on action items progress
        """
        action_items = self.action_items.all()
        
        if not action_items.exists():
            return
        
        # Check if all action items are completed
        all_completed = all(item.status == 'COMPLETED' for item in action_items)
        
        if all_completed:
            self.status = 'RESOLVED'
            self.save(update_fields=['status'])
        elif action_items.filter(status='IN_PROGRESS').exists():
            self.status = 'IN_PROGRESS'
            self.save(update_fields=['status'])
        elif action_items.filter(status='PENDING').exists() and self.status == 'REPORTED':
            self.status = 'ACTION_ASSIGNED'
            self.save(update_fields=['status'])      
        
    @property
    def is_action_overdue(self):
        """Check if action is overdue"""
        if self.action_deadline and self.status not in ['RESOLVED', 'CLOSED']:
            return datetime.date.today() > self.action_deadline
        return False

    @property
    def completed_or_closed_date(self):
        """Best-effort date used to determine whether the hazard was closed late."""
        if self.closure_date:
            return self.closure_date
        if self.action_completed_date:
            return self.action_completed_date

        latest_action_completion = self.action_items.filter(
            completion_date__isnull=False
        ).order_by('-completion_date').values_list('completion_date', flat=True).first()
        if latest_action_completion:
            return latest_action_completion

        if self.status in ['RESOLVED', 'CLOSED']:
            return timezone.localtime(self.updated_at).date()
        return None

    @property
    def is_late_closed(self):
        """True when the hazard was resolved/closed after the deadline date."""
        if self.status not in ['RESOLVED', 'CLOSED'] or not self.action_deadline:
            return False

        completed_or_closed_date = self.completed_or_closed_date
        return bool(completed_or_closed_date and completed_or_closed_date > self.action_deadline)

    @property
    def effective_status(self):
        """Computed status used in the UI without changing the stored model field."""
        if self.is_late_closed:
            return 'CLOSED_LATE'
        if self.is_action_overdue:
            return 'OVERDUE'
        return self.status

    @property
    def effective_status_display(self):
        """Human-readable computed status label."""
        status_display_map = {
            'OVERDUE': 'Overdue',
            'CLOSED_LATE': 'Closed Late',
        }
        return status_display_map.get(self.effective_status, self.get_status_display())
    
    @property
    def days_since_reported(self):
        """Days since hazard was reported"""
        return (datetime.date.today() - self.incident_datetime.date()).days
    
    @property
    def severity_badge_class(self):
        """Return Bootstrap badge class based on severity"""
        severity_classes = {
            'low': 'badge-success',
            'medium': 'badge-warning',
            'high': 'badge-orange',
            'critical': 'badge-danger',
        }
        return severity_classes.get(self.severity, 'badge-secondary')
    
    @property
    def status_badge_class(self):
        # --- SUGGESTED UPDATE ---
        # Added 'ACTION_ASSIGNED' for better visual feedback in the UI.
        status_classes = {
            'REPORTED': 'badge-info',
            'UNDER_REVIEW': 'badge-primary',
            'ACTION_ASSIGNED': 'badge-warning', # <-- Updated
            'IN_PROGRESS': 'badge-info',
            'RESOLVED': 'badge-success',
            'CLOSED': 'badge-secondary',
            'REJECTED': 'badge-danger',
            'PENDING_APPROVAL': 'badge-light',
            'APPROVED': 'badge-primary',
            'OVERDUE': 'badge-danger',
            'CLOSED_LATE': 'badge-danger',
        }
        return status_classes.get(self.effective_status, 'badge-secondary')

    @property
    def status_css_class(self):
        """CSS-friendly computed status name for custom template classes."""
        return self.effective_status.lower().replace('_', '-')
    
    @property
    def category_icon(self):
        """Return FontAwesome icon class for hazard category"""
        category_icons = {
            'slip_trip_fall': 'fa-person-falling',
            'chemical': 'fa-flask',
            'electrical': 'fa-bolt',
            'fire': 'fa-fire',
            'equipment': 'fa-cogs',
            'ergonomic': 'fa-chair',
            'biological': 'fa-biohazard',
            'environmental': 'fa-leaf',
            'confined_space': 'fa-box',
            'working_at_height': 'fa-person-climbing',
            'manual_handling': 'fa-box-open',
            'noise': 'fa-volume-up',
            'temperature': 'fa-temperature-high',
            'radiation': 'fa-radiation',
            'vehicular': 'fa-car',
            'other': 'fa-question-circle',
        }
        return category_icons.get(self.hazard_category, 'fa-exclamation-triangle')
    
    def get_full_location(self):
        """Get full location string"""
        parts = [self.plant.name]
        if self.zone:
            parts.append(self.zone.name)
        parts.append(self.location.name)
        if self.sublocation:
            parts.append(self.sublocation.name)
        return ' → '.join(parts)

    def get_severity_deadline_days(self):
        """
        Returns the number of days until deadline based on severity level
        """
        severity_days_map = {
            'low': 30,
            'medium': 15,
            'high': 7,
            'critical': 1
        }
        return severity_days_map.get(self.severity, 15)

class HazardPhoto(models.Model):
    """Photos related to hazard"""
    PHOTO_TYPE_CHOICES = [
        ('evidence', 'Evidence'),
        ('corrective_action', 'Corrective Action'),
        ('before', 'Before'),
        ('after', 'After'),
    ]
    
    hazard = models.ForeignKey(
        Hazard, 
        on_delete=models.CASCADE, 
        related_name='photos'
    )
    photo = models.ImageField(
        upload_to='hazard_photos/%Y/%m/',
        help_text="Hazard photo (max 5MB)"
    )
    photo_type = models.CharField(
        max_length=20,
        choices=PHOTO_TYPE_CHOICES,
        default='evidence',
        blank=True
    )
    description = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Brief description of the photo"
    )
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        help_text="User who uploaded the photo"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Hazard Photo'
        verbose_name_plural = 'Hazard Photos'
    
    def __str__(self):
        return f"{self.hazard.report_number} - Photo {self.id}"


class HazardVideo(models.Model):
    """Videos related to hazard"""

    VIDEO_TYPE_CHOICES = [
        ('evidence', 'Evidence'),
        ('corrective_action', 'Corrective Action'),
        ('before', 'Before'),
        ('after', 'After'),
    ]

    hazard = models.ForeignKey(
        Hazard,
        on_delete=models.CASCADE,
        related_name='videos'
    )
    video = models.FileField(
        upload_to='hazard_videos/%Y/%m/',
        help_text="Hazard video"
    )
    video_type = models.CharField(
        max_length=20,
        choices=VIDEO_TYPE_CHOICES,
        default='evidence',
        blank=True
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Brief description of the video"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="User who uploaded the video"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Hazard Video'
        verbose_name_plural = 'Hazard Videos'

    def __str__(self):
        return f"{self.hazard.report_number} - Video {self.id}"


class HazardActionItem(models.Model):
    """Action items for hazard resolution"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
    ]
    
    hazard = models.ForeignKey(
        Hazard, 
        on_delete=models.CASCADE, 
        related_name='action_items'
    )
    
    action_description = models.TextField(
        blank=True,  # Add this to allow the field to be empty
        help_text="Description of the action to be taken"
    )
    
    # Email addresses (comma-separated)
    responsible_emails = models.TextField(
        blank=True,
        help_text="Email addresses of responsible persons (comma-separated)"
    )
    
    # NEW FIELDS
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hazard_actions_created',
        help_text="User who created this action item"
    )
    
    is_self_assigned = models.BooleanField(
        default=False,
        help_text="Whether this action was self-assigned and completed"
    )
    
    # Attachment field
    attachment = models.FileField(
        upload_to='action_item_attachments/%Y/%m/',
        help_text="Required file attachment (documents, images, etc.)"
    )
    
    target_date = models.DateField(
        help_text="Target date for completing the action"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING',
        db_index=True
    )
    completion_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date when action was completed"
    )
    completion_remarks = models.TextField(
        blank=True,
        help_text="Remarks about action completion"
    )

    # --- ADD THIS FIELD ---
    # completed_by = models.ForeignKey(
    #     User,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='hazard_actions_completed',
    #     help_text="User who completed this action item"
    # )
    completed_by_users = models.ManyToManyField(
        User,
        related_name='hazard_actions_completed',
        blank=True,
        help_text="Users who have completed this action item"
    )
    
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hazard_actions_verified',
        help_text="User who verified the action completion"
    )
    verification_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when action was verified"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['target_date', '-created_at']
        verbose_name = 'Hazard Action Item'
        verbose_name_plural = 'Hazard Action Items'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['target_date']),
        ]
    
    def __str__(self):
        return f"{self.hazard.report_number} - Action Item {self.id}"
    
    def get_emails_list(self):
        """Return list of emails"""
        if self.responsible_emails:
            return [email.strip() for email in self.responsible_emails.split(',') if email.strip()]
        return []
    
    def get_emails_count(self):
        """Return count of emails"""
        return len(self.get_emails_list())
    
    def get_responsible_users(self):
        """Get User objects for assigned emails"""
        emails = self.get_emails_list()
        if emails:
            return User.objects.filter(email__in=emails)
        return User.objects.none()
    
    def get_attachment_name(self):
        """Get filename from attachment"""
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None
    
    def get_attachment_size(self):
        """Get attachment file size in human readable format"""
        if self.attachment:
            size = self.attachment.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return None
    
    @property
    def is_overdue(self):
        """Check if action item is overdue"""
        if self.status == 'COMPLETED':
            return False
        return self.target_date < timezone.now().date()
        
    @property
    def days_until_deadline(self):
        """Calculate days until deadline"""
        if self.target_date and self.status != 'COMPLETED':
            delta = self.target_date - datetime.date.today()
            return delta.days
        return None
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class based on status"""
        status_classes = {
            'PENDING': 'badge-warning',
            'IN_PROGRESS': 'badge-info',
            'COMPLETED': 'badge-success',
            'OVERDUE': 'badge-danger',
        }
        return status_classes.get(self.status, 'badge-secondary')
    
    @property
    def is_fully_completed(self):
        """
        Treat the action item as completed as soon as any assigned user completes it.
        """
        responsible_users_count = self.get_emails_count()

        # If no one is assigned, it cannot be considered complete.
        if responsible_users_count == 0:
            return False

        return self.completed_by_users.exists()

    def get_pending_users(self):
        """
        Returns a queryset of responsible users who have NOT yet completed the action.
        """
        responsible_users = self.get_responsible_users()
        completed_users = self.completed_by_users.all()
        
        # Exclude the users who have already completed the action
        pending_users = responsible_users.exclude(pk__in=completed_users.values_list('pk', flat=True))
        return pending_users
        
    # --- MODIFIED SAVE METHOD ---
    
    def save(self, *args, **kwargs):
            # --- MODIFIED LOGIC ---
            # If the object is already saved in the database (has a primary key),
            # then we can safely check its many-to-many relationships.
            if self.pk:
                if self.is_fully_completed:
                    self.status = 'COMPLETED'
                    # Set completion date only when it becomes fully completed for the first time.
                    if not self.completion_date:
                        self.completion_date = timezone.now().date()
                # If some (but not all) have completed, it's in progress.
                elif self.completed_by_users.exists() and not self.is_fully_completed:
                    self.status = 'IN_PROGRESS'
                    self.completion_date = None # In-progress means it's not fully complete yet
                # If NO ONE has completed it, it must be pending.
                else:
                    self.status = 'PENDING'
                    self.completion_date = None # Clear completion date if it reverts to pending

            # Continue with the original save operation for both new and existing objects
            super().save(*args, **kwargs)

class HazardNotification(models.Model):

    NOTIFICATION_TYPES = [
        ('HAZARD_REPORTED','Hazard Reported'),
        ('HAZARD_DUE','Hazard Due Soon'),
        ('HAZARD_OVERDUE','Hazard Overdue'),
        ('ACTION_ASSIGNED','Action Item Assigned'),
        ('ACTION_DUE','Action Item Due Soon'),
        ('HAZARD_CLOSED','Hazard Closed'),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hazard_notifications'
    )
    hazard = models.ForeignKey(
        Hazard,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notifications_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient','is_read']),
            models.Index(fields=['-created_at']),
        ] 

    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"
    
    def mark_as_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = timezone.now()
            self.save(update_fields=['is_read','read_at'])
