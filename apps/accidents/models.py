from django.db import models
from django.contrib.auth import get_user_model
from apps.organizations.models import *
import datetime
from django.conf import settings
from django.utils import timezone

User = get_user_model()

class IncidentType(models.Model):
    name=models.CharField(max_length=100,unique=True,help_text="full name of incident type")
    code=models.CharField(max_length=100,unique=True,help_text="short code")
    description=models.TextField(blank=True,help_text="Description of this incident type")
    is_active=models.BooleanField(default=True,help_text="Is this incident type active?")
    create_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    created_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='incident_types_created')
    class Meta:
        ordering=['name']
        verbose_name='Incident Type'
        verbose_name_plural='Incident Types'
    def __str__(self):
        return f"{self.name}({self.code})"
class Incident(models.Model):
    """
    Incident/Accident Reporting Model
    Types: LTI (Lost Time Injury), MTC/RWC (Medical Treatment Case), 
           FA (First Aid), HLFI (High Lost Frequency Injury), FATALITY
    """
    
    # INCIDENT_TYPES = [
    #     ('LTI', 'Lost Time Injury (LTI)'),
    #     ('MTC', 'Medical Treatment Case (MTC/RWC)'),
    #     ('FA', 'First Aid (FA)'),
    #     ('HLFI', 'High Lost Frequency Injury (HLFI)'),
    #     ('FATALITY', 'Fatality'),
    # ]
    
class Incident(models.Model):
    
    STATUS_CHOICES = [
        ('REPORTED', 'Reported'),
        ('INVESTIGATION_IN_PROGRESS', 'Investigation in Progress'), 
        ('ACTION_PLAN_PENDING', 'Action Plan Pending'),        
        ('PENDING_APPROVAL', 'Pending Approval'),           
        ('REJECTED', 'Rejected'),                           
        ('PENDING_CLOSE', 'Pending Close'),                  
        ('CLOSED', 'Closed'),                                 
    ]  
    
    APPROVAL_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='PENDING',
        help_text="Approval status of the investigation report"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents_approved',
        help_text="User who approved the investigation"
    )
    approved_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time of approval"
    )
    rejection_remarks = models.TextField(
        blank=True,
        help_text="Remarks if the investigation is rejected"
    )
        
    # Employment Category
    EMPLOYMENT_CATEGORY_CHOICES = [
        ('PERMANENT', 'Permanent'),
        ('CONTRACT', 'Contract'),
        ('ON_ROLL', 'On Roll'),
    ]
    # Gender
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
        ('PREFER_NOT_TO_SAY', 'Prefer not to say'),
    ]
    affected_employment_category = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_CATEGORY_CHOICES,
        blank=True,
        help_text="Employment category of affected person"
    )
       # Basic Information (already exists - keep these)
    affected_person_name = models.CharField(max_length=200)
    affected_person_employee_id = models.CharField(max_length=50, blank=True)
    
    # Department - FROM MASTER TABLE (ForeignKey)
    affected_person_department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='incidents_affected',
        help_text="Department from master table"
    )
    # Date of Birth and Age
    affected_date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Date of birth of affected person"
    )
    affected_age = models.IntegerField(
        null=True,
        blank=True,
        help_text="Age of affected person (calculated from DOB)"
    )
    affected_gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
        help_text="Gender of affected person"
    )
    # Job Title
    affected_job_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Job title or designation of affected person"
    )
    # Date of Joining
    affected_date_of_joining = models.DateField(
        null=True,
        blank=True,
        help_text="Date of joining of affected person"
    )
    # Auto-generated Report Number: INC-PLANT-YYYYMMDD-XXX
    report_number = models.CharField(max_length=50, unique=True, editable=False)
    
    # Basic Information
    # incident_type = models.CharField(max_length=10, choices=INCIDENT_TYPES)
    incident_type = models.ForeignKey(IncidentType,on_delete=models.CASCADE,related_name='incidents',help_text='Type of incient',blank=True,null=True)
    incident_date = models.DateField()
    incident_time = models.TimeField()
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='incidents')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='incidents', null=True, blank=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='incidents')
    sublocation = models.ForeignKey(
        SubLocation,
        on_delete=models.SET_NULL,
        related_name='incidents',
        null=True,
        blank=True,
        help_text="Optional: Specific sub-location where incident occurred"
    )
    additional_location_details = models.TextField(
        blank=True,
        help_text="Specific area, equipment, or landmark near the incident location"
    )
    # Incident Details
    description = models.TextField(help_text="Detailed description of what happened")
    
    # Unsafe Acts and Unsafe Conditions
    unsafe_acts = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of unsafe acts that contributed to the incident"
    )
    unsafe_acts_other = models.TextField(
        blank=True,
        help_text="Explanation for 'Other' unsafe acts"
    )
    
    unsafe_conditions = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of unsafe conditions that contributed to the incident"
    )
    unsafe_conditions_other = models.TextField(
        blank=True,
        help_text="Explanation for 'Other' unsafe conditions"
    )
    
    # Affected Person(s) - Using ForeignKey to User
    affected_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents_as_affected_person',
        help_text="Employee who was affected by the incident"
    )
    affected_person_name = models.CharField(max_length=200)
    affected_person_employee_id = models.CharField(max_length=50, blank=True)
    affected_person_department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='incidents_affected'
    )
    
    affected_body_parts = models.JSONField(default=list, blank=True)
    nature_of_injury = models.TextField(
        help_text="Required: Describe the type and extent of injury"
    )
    
    # Reporting Information
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incidents_reported')
    reported_date = models.DateTimeField(auto_now_add=True)
    
    # Investigation (Required within 7 days)
    investigation_required = models.BooleanField(default=True)
    investigation_deadline = models.DateField(null=True, blank=True)
    investigation_completed_date = models.DateField(null=True, blank=True)
    investigator = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='incidents_investigated'
    )
    
    # Root Cause Analysis
    root_cause = models.TextField(blank=True)
    contributing_factors = models.TextField(blank=True)
    
    # Action Plan
    action_plan = models.TextField(blank=True)
    action_plan_deadline = models.DateField(null=True, blank=True)
    action_plan_responsible_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents_action_responsible'
    )
    action_plan_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('IN_PROGRESS', 'In Progress'),
            ('COMPLETED', 'Completed'),
        ],
        default='PENDING'
    )

    # Workflow Management
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='REPORTED')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents_assigned'
    )
    
    # Notifications
    safety_manager_notified = models.BooleanField(default=False)
    location_head_notified = models.BooleanField(default=False)
    plant_head_notified = models.BooleanField(default=False)
    
    # Closure
    closure_date = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents_closed'
    ) 
    attachment = models.FileField(
        upload_to='action_item_attachments/%Y/%m/',
        help_text="Optional file attachment (documents, images, etc.)"
    )   
    closure_remarks = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    preventive_measures = models.TextField(blank=True)
    is_recurrence_possible = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-incident_date', '-incident_time']
        verbose_name = 'Incident Report'
        verbose_name_plural = 'Incident Reports'
    
    def __str__(self):
        incident_type_name = self.incident_type.name if self.incident_type else "N/A"
        return f"{self.report_number} - {incident_type_name}"

    
    def save(self, *args, **kwargs):
        # Generate report number if not exists
        if not self.report_number:
            today = datetime.date.today()
            date_str = today.strftime('%Y%m%d')
            plant_code = self.plant.code if self.plant else 'XXX'
            
            count = Incident.objects.filter(
                report_number__contains=f'INC-{plant_code}-{date_str}'
            ).count()
            
            self.report_number = f'INC-{plant_code}-{date_str}-{count + 1:03d}'
        
        # Set investigation deadline (7 days)
        if self.investigation_required and not self.investigation_deadline:
            self.investigation_deadline = self.incident_date + datetime.timedelta(days=7)
        
        super().save(*args, **kwargs)
    
    @property
    def is_investigation_overdue(self):
        if self.investigation_deadline and not self.investigation_completed_date:
            return datetime.date.today() > self.investigation_deadline
        return False
    
    @property
    def days_since_incident(self):
        return (datetime.date.today() - self.incident_date).days
    
    
    @property
    def can_be_closed(self):
        """
        Checks if the incident meets all conditions to be closed.
        Now includes a check for approval status.
        
        Returns:
            (bool, str): A tuple containing a boolean and a message.
        """
        # 1. NEW: Check if the incident has been approved. This is the first and most important check.
        if self.approval_status != 'APPROVED':
            return False, 'The incident has not been approved yet.'

        # 2. Check if the incident is already closed.
        if self.status == 'CLOSED':
            return False, "The incident is already closed."
            
        # 3. Check if investigation is completed (if required).
        if self.investigation_required and not self.investigation_completed:
            return False, "The investigation has not been completed."
        
        # 4. Check for any pending action items.
        pending_actions = self.action_items.exclude(status='COMPLETED').count()
        if pending_actions > 0:
            return False, f"{pending_actions} action item(s) are still pending."
        
        # 5. Check if the final closure attachment has been uploaded.
        if not self.attachment:
            return False, "A final closure attachment is required."
        
        # If all checks pass
        return True, "Ready for closure"
    
    @property
    def can_be_closed(self):
       
        if self.investigation_required and not self.investigation_completed_date:
            return False, "Investigation not completed"
        
        pending_actions = self.action_items.exclude(status='COMPLETED').count()
        if pending_actions > 0:
            return False, f"{pending_actions} action item(s) still pending"
        
        if self.status == 'CLOSED':
            return False, "Incident is already closed"
            
     
        if not self.attachment:
            return False, "A final closure attachment is required before proceeding."
        
        return True, "Ready for closure"
    
    @property
    def days_to_close(self):
        if self.closure_date:
            return (self.closure_date.date() - self.incident_date).days
        return None
    
    @property
    def investigation_completed(self):
        return bool(self.investigation_completed_date)


class IncidentPhoto(models.Model):
    """Photos related to incident"""
    
    PHOTO_TYPES = [
        ('INCIDENT_SCENE', 'Incident Scene'),
        ('INJURY', 'Injury Photo'),
        ('EVIDENCE', 'Evidence'),
        ('CORRECTIVE_ACTION', 'Corrective Action'),
    ]
    
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='incident_photos/%Y/%m/')
    photo_type = models.CharField(max_length=20, choices=PHOTO_TYPES)
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"{self.incident.report_number} - {self.photo_type}"


class IncidentVideo(models.Model):
    """Videos related to incident"""

    VIDEO_TYPES = [
        ('INCIDENT_SCENE', 'Incident Scene'),
        ('INJURY', 'Injury Video'),
        ('EVIDENCE', 'Evidence'),
        ('CORRECTIVE_ACTION', 'Corrective Action'),
    ]

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='videos')
    video = models.FileField(upload_to='incident_videos/%Y/%m/')
    video_type = models.CharField(max_length=20, choices=VIDEO_TYPES)
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.incident.report_number} - {self.video_type}"



class IncidentInvestigationReport(models.Model):
    """Investigation Report (Required within 7 days)"""
    
    incident = models.OneToOneField(Incident, on_delete=models.CASCADE, related_name='investigation_report')
    
    # Investigation Details
    investigation_date = models.DateField()
    investigator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investigations_conducted')
    investigation_team = models.TextField(help_text="Names of investigation team members Emails")
    
    # Findings
    sequence_of_events = models.TextField()
    root_cause_analysis = models.TextField()
    # contributing_factors = models.TextField()
    # unsafe_conditions_identified = models.TextField(blank=True)
    # unsafe_acts_identified = models.TextField(blank=True)
    personal_factors = models.JSONField(default=list, blank=True)
    job_factors = models.JSONField(default=list, blank=True)
    
    # Evidence
    evidence_collected = models.TextField(blank=True)
    witness_statements = models.TextField(blank=True)
    
    # Recommendations
    immediate_corrective_actions = models.TextField()
    preventive_measures = models.TextField()
    
    # ===== MODIFIED SECTION START =====
    # The following fields have been removed as action items are now managed dynamically.
    # action_items = models.TextField(help_text="Specific action items with responsibilities")
    # target_completion_date = models.DateField()
    # ===== MODIFIED SECTION END =====
    
    # Sign-off
    completed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='investigation_reports_completed'
    )
    completed_date = models.DateField()
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investigation_reports_reviewed'
    )
    reviewed_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Investigation Report'
        verbose_name_plural = 'Investigation Reports'
    
    def __str__(self):
        return f"Investigation Report - {self.incident.report_number}"


class IncidentActionItem(models.Model):
    """Action items from investigation/action plan"""
    
    # --- Choices ---
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
    ]

    ASSIGNMENT_TYPE_CHOICES = [
        ('SELF', 'Assign to Self & Close'),
        ('FORWARD', 'Forward to Others'),
    ]

    # --- Fields ---
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='action_items')
    
    action_description = models.TextField(blank=True)


    responsible_person = models.ManyToManyField(User, related_name='incident_actions_responsible', blank=True)
    completed_by = models.ManyToManyField(
        User,
        related_name='incident_actions_completed',
        blank=True,
        help_text="Users who have marked this action item as completed."
    )
    target_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    completion_date = models.DateField(null=True, blank=True)
    
    completion_remarks = models.TextField(
        blank=True,
        help_text="Remarks about how the action was completed."
    )
    
    # --- NEW FIELDS START ---
    # Field to determine how the action was assigned.
    assignment_type = models.CharField(
        max_length=10, 
        choices=ASSIGNMENT_TYPE_CHOICES, 
        default='FORWARD'
    )
    
    # Field for uploading evidence or reference documents.
    attachment = models.FileField(
        upload_to='incident_action_attachments/%Y/%m/',
        blank=True,
        null=True,
        help_text="Attachment for evidence or reference."
    )
    # --- NEW FIELDS END ---
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incident_actions_created',
        help_text="User who created this action item"
    )
    
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incident_actions_verified'
    )
    verification_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['target_date']
    
    def __str__(self):
        return f"{self.incident.report_number} - Action Item"
    
    @property
    def is_overdue(self):
        if self.status != 'COMPLETED' and self.target_date:
            from django.utils import timezone
            return timezone.now().date() > self.target_date
        return False  
    
    
class ActionItemCompletion(models.Model):
    """
    Registra los detalles de finalización para cada usuario responsable
    de un IncidentActionItem.
    """
    action_item = models.ForeignKey(
        IncidentActionItem,
        on_delete=models.CASCADE,
        related_name='completions'
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='action_completions'
    )
    completion_date = models.DateField(default=timezone.now)
    completion_remarks = models.TextField()
    attachment = models.FileField(
        upload_to='action_item_completion_proofs/%Y/%m/',
        help_text="Upload Proof/Attachment"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('action_item', 'completed_by') # Cada usuario puede completar una acción solo una vez
        verbose_name = 'Action Item Completion'
        verbose_name_plural = 'Action Item Completions'

    def __str__(self):
        return f"Completion for {self.action_item.id} by {self.completed_by.get_full_name()}"
  

###notification module 

User = get_user_model()

class IncidentNotification(models.Model):
    
    NOTIFICATION_TYPES = [
        ('INCIDENT_REPORTED', 'Incident Reported'),
        ('INVESTIGATION_DUE', 'Investigation Due Soon'),
        ('INVESTIGATION_OVERDUE', 'Investigation Overdue'),
        ('ACTION_ASSIGNED', 'Action Item Assigned'),
        ('ACTION_DUE', 'Action Item Due Soon'),
        ('INCIDENT_CLOSED', 'Incident Closed'),
        ('INCIDENT_REOPENED', 'Incident Reopened'),
    ]
    
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='incident_notifications'
    )
    incident = models.ForeignKey(
        Incident, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"
    
    def mark_as_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])