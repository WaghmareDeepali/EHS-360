# apps/inspections/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User
from apps.organizations.models import Plant, Zone, Location, SubLocation, Department
from django.utils import timezone

class InspectionCategory(models.Model):
    """Categories for organizing inspection questions (Fire Safety, Electrical, etc.)"""
    
    category_name = models.CharField(
        max_length=200, 
        unique=True,
        verbose_name="Category Name"
    )
    category_code = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="Category Code",
        help_text="Short code like FS, ES, HK"
    )
    description = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Description"
    )
    # icon = models.CharField(
    #     max_length=50, 
    #     blank=True, 
    #     null=True,
    #     help_text="FontAwesome icon class"
    # )
    # display_order = models.IntegerField(
    #     default=0,
    #     verbose_name="Display Order",
    #     help_text="Order in which categories appear"
    # )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active Status"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_categories'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inspection_categories'
        # ordering = ['display_order', 'category_name']
        verbose_name = "Inspection Category"
        verbose_name_plural = "Inspection Categories"

    def __str__(self):
        return f"{self.category_code} - {self.category_name}"
    
    def get_active_questions_count(self):
        """Count active questions in this category"""
        return self.questions.filter(is_active=True).count()


class InspectionQuestion(models.Model):
    """Master list of all inspection questions"""
    
    QUESTION_TYPE_CHOICES = [
        ('YES_NO', 'Yes/No'),
        ('TEXT', 'Text Input'),
        ('NUMBER', 'Numeric Input'),
        ('RATING', 'Rating (1-5)'),
        # ('DROPDOWN', 'Dropdown Selection'),
    ]
    
    category = models.ForeignKey(
        InspectionCategory,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name="Category"
    )
    question_text = models.TextField(
        verbose_name="Question Text",
        help_text="The actual inspection question"
    )
    question_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Question Code",
        help_text="Unique identifier like FS-001"
    )
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default='YES_NO',
        verbose_name="Question Type"
    )
    
    # Configuration flags
    is_remarks_mandatory = models.BooleanField(
        default=True,
        verbose_name="Remarks Mandatory",
        help_text="Require remarks for this question"
    )
    is_photo_required = models.BooleanField(
        default=False,
        verbose_name="Photo Required",
        help_text="Require photo evidence for this question"
    )
    is_critical = models.BooleanField(
        default=False,
        verbose_name="Critical Question",
        help_text="Mark as critical/high-priority question"
    )
    auto_generate_finding = models.BooleanField(
        default=True,
        verbose_name="Auto-Generate Finding",
        help_text="Automatically create finding if answered 'No'"
    )
    
    # For scoring/compliance calculation
    weightage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Weightage",
        help_text="Weight for compliance scoring"
    )
    
    # Display configuration
    # display_order = models.IntegerField(
    #     default=0,
    #     verbose_name="Display Order",
    #     help_text="Order within category"
    # )
    
    # Reference/guidance
    reference_standard = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Reference Standard",
        help_text="e.g., OSHA 1910.36, IS 2309"
    )
    guidance_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Guidance Notes",
        help_text="Additional guidance for inspector"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active Status"
    )
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_questions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_questions'
    )

    class Meta:
        db_table = 'inspection_questions'
        ordering = ['category', 'question_code'] #removed - 'display_order',
        verbose_name = "Inspection Question"
        verbose_name_plural = "Inspection Questions"
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['question_code']),
        ]

    def __str__(self):
        return f"{self.question_code} - {self.question_text[:50]}"
    
    def save(self, *args, **kwargs):
        # Auto-generate question code if not provided
        if not self.question_code:
            self.question_code = self.generate_question_code()
        super().save(*args, **kwargs)
    
    def generate_question_code(self):
        """Auto-generate question code based on category"""
        category_code = self.category.category_code
        
        # Get last question number for this category
        last_question = InspectionQuestion.objects.filter(
            category=self.category,
            question_code__startswith=category_code
        ).order_by('-question_code').first()
        
        if last_question:
            try:
                # Extract number from code like "FS-001"
                last_num = int(last_question.question_code.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{category_code}-{new_num:03d}"


class InspectionTemplate(models.Model):
    """Templates define which questions are included in an inspection"""
    
    INSPECTION_TYPE_CHOICES = [
        ('DAILY', 'Daily Inspection'),
        ('WEEKLY', 'Weekly Inspection'),
        ('MONTHLY', 'Monthly Inspection'),
        ('QUARTERLY', 'Quarterly Inspection'),
        ('ANNUAL', 'Annual Inspection'),
    ]
    
    template_name = models.CharField(
        max_length=200,
        verbose_name="Template Name"
    )
    template_code = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name="Template Code"
    )
    inspection_type = models.CharField(
        max_length=20,
        choices=INSPECTION_TYPE_CHOICES,
        verbose_name="Inspection Type"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description"
    )
    
    # Applicability
    applicable_plants = models.ManyToManyField(
        Plant,
        blank=True,
        related_name='inspection_templates',
        verbose_name="Applicable Plants",
        help_text="Leave empty for all plants"
    )
    applicable_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='inspection_templates',
        verbose_name="Applicable Departments"
    )
    
    # Configuration
    # requires_approval = models.BooleanField(
    #     default=False,
    #     verbose_name="Requires Approval",
    #     help_text="Inspection needs approval after submission"
    # )
    min_compliance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=80.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Minimum Compliance Score (%)",
        help_text="Minimum acceptable compliance percentage"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active Status"
    )
    
    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inspection_templates'
        ordering = ['-created_at']
        verbose_name = "Inspection Template"
        verbose_name_plural = "Inspection Templates"

    def __str__(self):
        return f"{self.template_code} - {self.template_name}"
    
    def get_total_questions(self):
        """Get total number of questions in template"""
        return self.template_questions.filter(
            question__is_active=True
        ).count()
    
    def get_categories(self):
        """Get unique categories in this template"""
        return InspectionCategory.objects.filter(
            questions__templatequestion__template=self,
            questions__is_active=True
        ).distinct()
    
    def save(self, *args, **kwargs):
        if not self.template_code:
            self.template_code = self.generate_template_code()
            super().save(*args,**kwargs)
    
    def generate_template_code(self):
        """Generate Unique template code for every template"""
        prefix = f"TEMP-{self.inspection_type}"

        last_template = InspectionTemplate.objects.filter(template_code__startswith=prefix).order_by('-template_code').first()

        if last_template:
            try:
                last_num = int(last_template.template_code.split('-')[-1])
                new_num = last_num + 1
            except(ValueError,IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}-{new_num:03d}"


class TemplateQuestion(models.Model):
    """Maps questions to templates with additional configuration"""
    
    template = models.ForeignKey(
        InspectionTemplate,
        on_delete=models.CASCADE,
        related_name='template_questions',
        verbose_name="Template"
    )
    question = models.ForeignKey(
        InspectionQuestion,
        on_delete=models.CASCADE,
        related_name='template_mappings',
        verbose_name="Question"
    )
    is_mandatory = models.BooleanField(
        default=True,
        verbose_name="Mandatory",
        help_text="Must be answered"
    )
    # display_order = models.IntegerField(
    #     default=0,
    #     verbose_name="Display Order"
    # )
    section_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Section Name",
        help_text="Group questions into sections"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'template_questions'
        # ordering = ['display_order', 'question__display_order']
        unique_together = ['template', 'question']
        verbose_name = "Template Question"
        verbose_name_plural = "Template Questions"

    def __str__(self):
        return f"{self.template.template_name} - {self.question.question_code}"


class InspectionSchedule(models.Model):
    """Schedule inspections for HODs at plants"""
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('CLOSED', 'Closed'),
        ('CLOSED_LATE', 'Closed Late'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    schedule_code = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Schedule Code"
    )
    template = models.ForeignKey(
        InspectionTemplate,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name="Inspection Template"
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_inspections',
        verbose_name="Assigned To (HOD)",
        help_text="HOD who will conduct the inspection"
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='scheduled_inspections',
        verbose_name="Assigned By (Safety Officer)"
    )
    
    # Location details
    plants = models.ManyToManyField(
        Plant,
        blank=True,
        related_name='plant_many',
    )
    zones = models.ManyToManyField(
        Zone,
        blank=True,
        related_name='Zone_many',
    )
    locations = models.ManyToManyField(
        Location,
        blank=True,
        related_name='locations_many',
    )
    sublocations = models.ManyToManyField(
        SubLocation,
        blank=True,
        related_name='sublocation_many',
    )
    assigned_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='assigned_users_many',
        help_text="Multiple HODs/Safety Managers assigned"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspection_schedules'
    )
    
    # Timing
    scheduled_date = models.DateField(
        verbose_name="Scheduled Date"
    )
    due_date = models.DateField(
        verbose_name="Due Date"
    )
    scheduled_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Schedule End Date",
        help_text="Stop auto-generating inspections after this date"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Started At"
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Closed At"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SCHEDULED',
        verbose_name="Status"
    )
    
    # Notes
    assignment_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Assignment Notes",
        help_text="Notes from Safety Officer"
    )
    
    # Notifications
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name="Reminder Sent"
    )
    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True
    )
    auto_schedule_config = models.ForeignKey(
        'TemplateAutoScheduleConfig',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_schedules',
        help_text="If created via auto schedule"
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inspection_schedules'
        ordering = ['-scheduled_date', '-created_at']
        verbose_name = "Inspection Schedule"
        verbose_name_plural = "Inspection Schedules"
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.schedule_code} - {self.template.template_name}"
    
    def save(self, *args, **kwargs):
        if not self.schedule_code:
            self.schedule_code = self.generate_schedule_code()
        
        # Update status based on dates
        if self.status not in ['CLOSED', 'LATE_CLOSE', 'CANCELLED']:
            if self.closed_at:
                self.status = 'CLOSED'
            elif timezone.now().date() > self.due_date:
                self.status = 'OVERDUE'
            elif self.started_at:
                self.status = 'IN_PROGRESS'
        
        super().save(*args, **kwargs)
    
    def generate_schedule_code(self):
        """Generate unique schedule code"""
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m')
        
        last_schedule = InspectionSchedule.objects.filter(
            schedule_code__startswith=f"INSP-{date_str}"
        ).order_by('-schedule_code').first()
        
        if last_schedule:
            try:
                last_num = int(last_schedule.schedule_code.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"INSP-{date_str}-{new_num:04d}"
    
    @property
    def is_overdue(self):
        """Check if inspection is overdue"""
        return (
            self.status not in ['CLOSED', 'LATE_CLOSE', 'CANCELLED'] and
            timezone.now().date() > self.due_date
        )
class TemplateAutoScheduleConfig(models.Model):
    """
    Auto-schedule configuration for a template.
    Celery runs on 1st of every month and creates
    one InspectionSchedule per plant per assigned user.
    """

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAUSED = 'PAUSED'
    STATUS_STOPPED = 'STOPPED'

    template = models.ForeignKey(
        InspectionTemplate,
        on_delete=models.CASCADE,
        related_name='auto_schedule_configs'
    )
    # Selected plants (checkboxes)
    plants = models.ManyToManyField(
        Plant,
        related_name='auto_schedule_configs'
    )
    # Selected zones per plant
    zones = models.ManyToManyField(
        Zone,
        blank=True,
        related_name='auto_schedule_configs'
    )
    # Selected locations per zone
    locations = models.ManyToManyField(
        Location,
        blank=True,
        related_name='auto_schedule_configs'
    )
    # Selected sublocations
    sublocations = models.ManyToManyField(
        SubLocation,
        blank=True,
        related_name='auto_schedule_configs'
    )
    # HODs + Safety Managers from selected plants
    assigned_users = models.ManyToManyField(
        User,
        related_name='auto_schedule_configs',
        help_text="HODs and Safety Managers to assign monthly"
    )
    due_date_offset_days = models.IntegerField(
        default=7,
        help_text="Due date = 1st of month + this many days"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Stop/Start auto-scheduling"
    )
    is_paused = models.BooleanField(
        default=False,
        help_text="Temporarily pause without deleting"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_auto_schedule_configs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'template_auto_schedule_configs'
        verbose_name = "Auto Schedule Config"
        verbose_name_plural = "Auto Schedule Configs"

    def __str__(self):
        return f"Auto Config: {self.template.template_name} ({self.status})"

    @property
    def status(self):
        if not self.is_active:
            return self.STATUS_STOPPED
        if self.is_paused:
            return self.STATUS_PAUSED
        return self.STATUS_ACTIVE    

class InspectionSubmission(models.Model):
    """Stores the CLOSED inspection submission"""
    
    schedule = models.OneToOneField(
        InspectionSchedule,
        on_delete=models.CASCADE,
        related_name='submission'
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inspection_submissions'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    compliance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage of questions answered 'Yes'"
    )
    remarks = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'inspection_submissions'
    
    def __str__(self):
        return f"Submission for {self.schedule.schedule_code}"
    
    def calculate_compliance_score(self):
        """Calculate compliance percentage"""
        total_questions = self.responses.count()
        if total_questions == 0:
            return 0
        
        yes_answers = self.responses.filter(answer='Yes').count()
        score = (yes_answers / total_questions) * 100
        return round(score, 2)


class InspectionDraft(models.Model):
    """Stores in-progress inspection data before final submission."""

    schedule = models.OneToOneField(
        InspectionSchedule,
        on_delete=models.CASCADE,
        related_name='draft'
    )
    saved_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inspection_drafts'
    )
    data = models.JSONField(default=dict, blank=True)
    saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inspection_drafts'

    def __str__(self):
        return f"Draft for {self.schedule.schedule_code}"


class InspectionDraftPhoto(models.Model):
    """Stores per-question photo uploads for inspection drafts."""

    draft = models.ForeignKey(
        InspectionDraft,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    question = models.ForeignKey(
        InspectionQuestion,
        on_delete=models.CASCADE,
        related_name='draft_photos'
    )
    photo = models.ImageField(upload_to='inspection_drafts/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inspection_draft_photos'
        unique_together = ['draft', 'question']

    def __str__(self):
        return f"Draft photo for {self.draft.schedule.schedule_code} - {self.question.question_code}"


class InspectionResponse(models.Model):
    submission = models.ForeignKey(
        'InspectionSubmission',
        on_delete=models.CASCADE,
        related_name='responses'
    )
    question = models.ForeignKey(
        'InspectionQuestion',
        on_delete=models.CASCADE
    )
    answer = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    photo = models.ImageField(upload_to='inspection_responses/', blank=True, null=True)
    answered_at = models.DateTimeField(auto_now_add=True)
    
    # ✅ ADD THESE NEW FIELDS
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_inspection_responses',
        help_text="Person assigned to address this non-compliance"
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspection_responses_assigned_by',
        help_text="Person who assigned this response"
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    specific_location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Exact location where the issue was observed"
    )
    assignment_remarks = models.TextField(blank=True)
    
    converted_to_hazard = models.ForeignKey(
        'hazards.Hazard',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_inspection_responses',
        help_text="Hazard created from this inspection response"
    )
    
    class Meta:
        ordering = ['-answered_at']
    
    def __str__(self):
        return f"{self.question.question_code} - {self.answer}"
class InspectionFinding(models.Model):
    """Issues found during inspection (auto-generated from 'No' answers)"""
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    
    submission = models.ForeignKey(
        InspectionSubmission,
        on_delete=models.CASCADE,
        related_name='findings'
    )
    question = models.ForeignKey(
        InspectionQuestion,
        on_delete=models.CASCADE
    )
    finding_code = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='MEDIUM'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_findings'
    )
    due_date = models.DateField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inspection_findings'
    
    def __str__(self):
        return f"{self.finding_code} - {self.question.question_code}"
