# apps/inspections/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    InspectionCategory, 
    InspectionQuestion, 
    InspectionTemplate, 
    TemplateQuestion,
    InspectionSchedule,
    InspectionSubmission,
    InspectionResponse,
    InspectionFinding,
    TemplateAutoScheduleConfig
)


@admin.register(InspectionCategory)
class InspectionCategoryAdmin(admin.ModelAdmin):
    list_display = [
        'category_code', 
        'category_name', 
        'questions_count',
        'is_active',
        'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['category_name', 'category_code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category_name', 'category_code', 'description')
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def questions_count(self, obj):
        count = obj.get_active_questions_count()
        return format_html(
            '<span style="color: #0066cc; font-weight: bold;">{}</span>',
            count
        )
    questions_count.short_description = 'Active Questions'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class TemplateQuestionInline(admin.TabularInline):
    model = TemplateQuestion
    extra = 1
    fields = ['question', 'is_mandatory', 'section_name']
    autocomplete_fields = ['question']


@admin.register(InspectionQuestion)
class InspectionQuestionAdmin(admin.ModelAdmin):
    list_display = [
        'question_code',
        'category',
        'question_preview',
        'question_type',
        'is_critical',
        'is_remarks_mandatory',
        'is_active',
        'created_at'
    ]
    list_filter = [
        'category',
        'question_type',
        'is_critical',
        'is_remarks_mandatory',
        'is_photo_required',
        'auto_generate_finding',
        'is_active',
        'created_at'
    ]
    search_fields = [
        'question_code',
        'question_text',
        'reference_standard',
        'guidance_notes'
    ]
    ordering = ['category', 'question_code']
    readonly_fields = ['question_code', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'category',
                'question_code',
                'question_text',
                'question_type'
            )
        }),
        ('Configuration', {
            'fields': (
                'is_remarks_mandatory',
                'is_photo_required',
                'is_critical',
                'auto_generate_finding',
                'weightage',
            )
        }),
        ('Reference & Guidance', {
            'fields': ('reference_standard', 'guidance_notes'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_preview(self, obj):
        preview = obj.question_text[:60] + '...' if len(obj.question_text) > 60 else obj.question_text
        color = '#dc3545' if obj.is_critical else '#333'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            preview
        )
    question_preview.short_description = 'Question'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['make_active', 'make_inactive', 'mark_as_critical']
    
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} questions marked as active.')
    make_active.short_description = "Mark selected questions as active"
    
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} questions marked as inactive.')
    make_inactive.short_description = "Mark selected questions as inactive"
    
    def mark_as_critical(self, request, queryset):
        updated = queryset.update(is_critical=True)
        self.message_user(request, f'{updated} questions marked as critical.')
    mark_as_critical.short_description = "Mark as critical questions"


@admin.register(InspectionTemplate)
class InspectionTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'template_code',
        'template_name',
        'inspection_type',
        'questions_count',
        'is_active',
        'created_at'
    ]
    list_filter = [
        'inspection_type',
        'is_active',
        'created_at',
        'applicable_plants'
    ]
    search_fields = ['template_name', 'template_code', 'description']
    filter_horizontal = ['applicable_plants', 'applicable_departments']
    readonly_fields = ['template_code', 'created_at', 'updated_at']
    inlines = [TemplateQuestionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'template_name',
                'inspection_type',
                'description'
            )
        }),
        ('Template Code', {
            'fields': ('template_code',),
        }),
        ('Applicability', {
            'fields': ('applicable_plants', 'applicable_departments')
        }),
        ('Configuration', {
            'fields': (
                'min_compliance_score',
                'is_active'
            )
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def questions_count(self, obj):
        count = obj.get_total_questions()
        return format_html(
            '<span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            count
        )
    questions_count.short_description = 'Total Questions'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InspectionSchedule)
class InspectionScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'schedule_code',
        'template',
        'assigned_to',
        'get_plants',
        'scheduled_date',
        'due_date',
        'status_badge',
        'is_overdue'
    ]
    list_filter = [
        'status',
        'plants',
        'scheduled_date',
        'due_date',
        'created_at'
    ]
    search_fields = [
        'schedule_code',
        'assigned_to__first_name',
        'assigned_to__last_name',
        'assigned_to__employee_id'
    ]
    readonly_fields = [
        'schedule_code',
        'started_at',
        'closed_at',
        'reminder_sent_at',
        'created_at',
        'updated_at'
    ]
    autocomplete_fields = ['assigned_to', 'assigned_by']
    filter_horizontal = ['plants', 'zones', 'locations', 'sublocations', 'assigned_users']
    
    fieldsets = (
        ('Schedule Information', {
            'fields': (
                'schedule_code',
                'template',
                'status'
            )
        }),
        ('Assignment', {
            'fields': (
                'assigned_to',
                'assigned_by',
                'assigned_users',
                'assignment_notes'
            )
        }),
        ('Location Details', {
            'fields': (
                'plants',
                'zones',
                'locations',
                'sublocations',
                'department'
            )
        }),
        ('Timing', {
            'fields': (
                'scheduled_date',
                'due_date',
                'started_at',
                'closed_at'
            )
        }),
        ('Notifications', {
            'fields': (
                'reminder_sent',
                'reminder_sent_at'
            ),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_plants(self, obj):
        plants = obj.plants.all()
        if plants:
            return ', '.join([p.name for p in plants])
        return '-'
    get_plants.short_description = 'Plants'

    def status_badge(self, obj):
        colors = {
            'SCHEDULED': '#007bff',
            'IN_PROGRESS': '#ffc107',
            'CLOSED': '#28a745',
            'OVERDUE': '#dc3545',
            'CANCELLED': '#6c757d'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def is_overdue(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⚠ Yes</span>'
            )
        return format_html(
            '<span style="color: #28a745;">✓ No</span>'
        )
    is_overdue.short_description = 'Overdue'
    
    actions = ['send_reminders', 'mark_as_closed', 'cancel_schedules']
    
    def send_reminders(self, request, queryset):
        count = queryset.filter(status='SCHEDULED').count()
        self.message_user(request, f'Reminders sent for {count} scheduled inspections.')
    send_reminders.short_description = "Send reminder notifications"
    
    def mark_as_closed(self, request, queryset):
        updated = queryset.filter(status__in=['SCHEDULED', 'IN_PROGRESS']).update(
            status='CLOSED',
            closed_at=timezone.now()
        )
        self.message_user(request, f'{updated} inspections marked as closed.')
    mark_as_closed.short_description = "Mark as closed"
    
    def cancel_schedules(self, request, queryset):
        updated = queryset.exclude(status='CLOSED').update(status='CANCELLED')
        self.message_user(request, f'{updated} inspections cancelled.')
    cancel_schedules.short_description = "Cancel selected schedules"


# ====================================
# INSPECTION SUBMISSION & RESPONSE
# ====================================

class InspectionResponseInline(admin.TabularInline):
    model = InspectionResponse
    extra = 0
    fields = [
        'question', 
        'answer_badge', 
        'remarks_preview', 
        'has_photo',
        'assignment_status',
        'conversion_status'
    ]
    readonly_fields = [
        'question',
        'answer_badge',
        'remarks_preview',
        'has_photo',
        'assignment_status',
        'conversion_status'
    ]
    can_delete = False
    
    def answer_badge(self, obj):
        colors = {
            'Yes': '#28a745',
            'No': '#dc3545',
            'N/A': '#6c757d'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.answer, '#6c757d'),
            obj.answer
        )
    answer_badge.short_description = 'Answer'
    
    def remarks_preview(self, obj):
        if obj.remarks:
            preview = obj.remarks[:40] + '...' if len(obj.remarks) > 40 else obj.remarks
            return format_html('<small>{}</small>', preview)
        return format_html('<span style="color: #999;">-</span>')
    remarks_preview.short_description = 'Remarks'
    
    def has_photo(self, obj):
        if obj.photo:
            return format_html('✓ <span style="color: #28a745;">Yes</span>')
        return format_html('<span style="color: #999;">No</span>')
    has_photo.short_description = 'Photo'
    
    def assignment_status(self, obj):
        if obj.assigned_to:
            return format_html(
                '<span style="color: #0066cc;">👤 {}</span>',
                obj.assigned_to.get_full_name()
            )
        return format_html('<span style="color: #999;">Not Assigned</span>')
    assignment_status.short_description = 'Assigned To'
    
    def conversion_status(self, obj):
        if obj.converted_to_hazard:
            return format_html(
                '<span style="color: #28a745;">✓ {}</span>',
                obj.converted_to_hazard.report_number
            )
        return format_html('<span style="color: #999;">-</span>')
    conversion_status.short_description = 'Hazard'


@admin.register(InspectionSubmission)
class InspectionSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'schedule',
        'submitted_by',
        'submitted_at',
        'compliance_score_badge',
        'total_responses',
        'no_answers_count'
    ]
    list_filter = [
        'submitted_at',
        'schedule__template'
    ]
    search_fields = [
        'schedule__schedule_code',
        'submitted_by__first_name',
        'submitted_by__last_name'
    ]
    readonly_fields = [
        'schedule',
        'submitted_by',
        'submitted_at',
        'compliance_score',
        'total_responses',
        'no_answers_count'
    ]
    inlines = [InspectionResponseInline]
    
    fieldsets = (
        ('Submission Information', {
            'fields': (
                'schedule',
                'submitted_by',
                'submitted_at'
            )
        }),
        ('Results', {
            'fields': (
                'compliance_score',
                'remarks'
            )
        }),
    )
    
    def compliance_score_badge(self, obj):
        score = float(obj.compliance_score or 0)
        if score >= 90:
            color = '#28a745'
        elif score >= 75:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-weight: bold;">{}%</span>',
            color,
            round(score, 1)
        )
    compliance_score_badge.short_description = 'Compliance Score'
    
    def total_responses(self, obj):
        count = obj.responses.count()
        return format_html(
            '<span style="color: #0066cc; font-weight: bold;">{}</span>',
            count
        )
    total_responses.short_description = 'Total Answers'
    
    def no_answers_count(self, obj):
        count = obj.responses.filter(answer='No').count()
        if count > 0:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-weight: bold;">{}</span>',
                count
            )
        return format_html('<span style="color: #28a745;">0</span>')
    no_answers_count.short_description = 'Non-Compliant'


@admin.register(InspectionResponse)
class InspectionResponseAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'submission_link',
        'question_code',
        'answer_badge',
        'is_critical',
        'answered_at',
        'assignment_badge',
        'hazard_link'
    ]
    list_filter = [
        'answer',
        'question__is_critical',
        'answered_at',
        'assigned_to',
        'converted_to_hazard'
    ]
    search_fields = [
        'question__question_code',
        'question__question_text',
        'remarks',
        'submission__schedule__schedule_code'
    ]
    readonly_fields = [
        'submission',
        'question',
        'answer',
        'remarks',
        'photo',
        'answered_at',
        'assigned_to',
        'assigned_by',
        'assigned_at',
        'assignment_remarks',
        'converted_to_hazard'
    ]
    
    fieldsets = (
        ('Response Information', {
            'fields': (
                'submission',
                'question',
                'answer',
                'remarks',
                'photo',
                'answered_at'
            )
        }),
        ('Assignment Details', {
            'fields': (
                'assigned_to',
                'assigned_by',
                'assigned_at',
                'assignment_remarks'
            ),
            'classes': ('collapse',)
        }),
        ('Hazard Conversion', {
            'fields': (
                'converted_to_hazard',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def submission_link(self, obj):
        return format_html(
            '<a href="/admin/inspections/inspectionsubmission/{}/change/">{}</a>',
            obj.submission.id,
            obj.submission.schedule.schedule_code
        )
    submission_link.short_description = 'Inspection'
    
    def question_code(self, obj):
        return obj.question.question_code
    question_code.short_description = 'Question Code'
    
    def answer_badge(self, obj):
        colors = {
            'Yes': '#28a745',
            'No': '#dc3545',
            'N/A': '#6c757d'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            colors.get(obj.answer, '#6c757d'),
            obj.answer
        )
    answer_badge.short_description = 'Answer'
    
    def is_critical(self, obj):
        if obj.question.is_critical:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⚠ Critical</span>'
            )
        return format_html('<span style="color: #999;">Normal</span>')
    is_critical.short_description = 'Priority'
    
    def assignment_badge(self, obj):
        if obj.assigned_to:
            return format_html(
                '<span style="background: #0066cc; color: white; padding: 3px 8px; '
                'border-radius: 3px;">👤 {}</span>',
                obj.assigned_to.get_full_name()
            )
        return format_html('<span style="color: #999;">Not Assigned</span>')
    assignment_badge.short_description = 'Assignment'
    
    def hazard_link(self, obj):
        if obj.converted_to_hazard:
            return format_html(
                '<a href="/admin/hazards/hazard/{}/change/" '
                'style="color: #28a745; font-weight: bold;">✓ {}</a>',
                obj.converted_to_hazard.id,
                obj.converted_to_hazard.report_number
            )
        return format_html('<span style="color: #999;">-</span>')
    hazard_link.short_description = 'Hazard'
    
    actions = ['bulk_assign', 'clear_assignments']
    
    def bulk_assign(self, request, queryset):
        valid_responses = queryset.filter(
            answer='No',
            assigned_to__isnull=True,
            converted_to_hazard__isnull=True
        )
        count = valid_responses.count()
        if count > 0:
            self.message_user(
                request,
                f'{count} responses are ready for assignment. '
                'Use the front-end bulk assignment feature.'
            )
        else:
            self.message_user(
                request,
                'No valid responses selected (must be "No" answers, '
                'unassigned, and not converted)',
                level='warning'
            )
    bulk_assign.short_description = "Prepare for bulk assignment"
    
    def clear_assignments(self, request, queryset):
        valid_responses = queryset.filter(
            assigned_to__isnull=False,
            converted_to_hazard__isnull=True
        )
        updated = valid_responses.update(
            assigned_to=None,
            assigned_by=None,
            assigned_at=None,
            assignment_remarks=''
        )
        self.message_user(request, f'{updated} assignments cleared.')
    clear_assignments.short_description = "Clear assignments (not converted)"


@admin.register(InspectionFinding)
class InspectionFindingAdmin(admin.ModelAdmin):
    list_display = [
        'finding_code',
        'submission',
        'question',
        'priority_badge',
        'status_badge',
        'assigned_to',
        'created_at'
    ]
    list_filter = [
        'priority',
        'status',
        'created_at'
    ]
    search_fields = [
        'finding_code',
        'description',
        'question__question_code'
    ]
    readonly_fields = ['finding_code', 'created_at']
    
    fieldsets = (
        ('Finding Information', {
            'fields': (
                'finding_code',
                'submission',
                'question',
                'description',
                'priority'
            )
        }),
        ('Assignment', {
            'fields': (
                'assigned_to',
                'status'
            )
        }),
        ('Audit', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def priority_badge(self, obj):
        colors = {
            'LOW': '#28a745',
            'MEDIUM': '#ffc107',
            'HIGH': '#fd7e14',
            'CRITICAL': '#dc3545'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            colors.get(obj.priority, '#6c757d'),
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def status_badge(self, obj):
        colors = {
            'OPEN': '#dc3545',
            'IN_PROGRESS': '#ffc107',
            'RESOLVED': '#28a745',
            'CLOSED': '#6c757d'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['mark_as_resolved', 'mark_as_closed']
    
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status='RESOLVED')
        self.message_user(request, f'{updated} findings marked as resolved.')
    mark_as_resolved.short_description = "Mark as resolved"
    
    def mark_as_closed(self, request, queryset):
        updated = queryset.update(status='CLOSED')
        self.message_user(request, f'{updated} findings marked as closed.')
    mark_as_closed.short_description = "Mark as closed"


@admin.register(TemplateAutoScheduleConfig)
class TemplateAutoScheduleConfigAdmin(admin.ModelAdmin):
    list_display = [
        'template',
        'status_badge',
        'due_date_offset_days',
        'get_plants',
        'get_users',
        'created_at'
    ]
    list_filter = [
        'is_active',
        'is_paused',
        'plants',
        'created_at'
    ]
    search_fields = [
        'template__template_name',
        'template__template_code'
    ]
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['plants', 'zones', 'locations', 'sublocations', 'assigned_users']

    fieldsets = (
        ('Template', {
            'fields': ('template',)
        }),
        ('Location Selection', {
            'fields': ('plants', 'zones', 'locations', 'sublocations')
        }),
        ('Assigned Users', {
            'fields': ('assigned_users',)
        }),
        ('Schedule Settings', {
            'fields': ('due_date_offset_days', 'is_active', 'is_paused')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'ACTIVE': '#28a745',
            'PAUSED': '#ffc107',
            'STOPPED': '#dc3545'
        }
        text_colors = {
            'ACTIVE': 'white',
            'PAUSED': '#212529',
            'STOPPED': 'white'
        }
        status = obj.status
        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 10px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            colors.get(status, '#6c757d'),
            text_colors.get(status, 'white'),
            status
        )
    status_badge.short_description = 'Status'

    def get_plants(self, obj):
        plants = obj.plants.all()
        if plants:
            return ', '.join([p.name for p in plants])
        return '-'
    get_plants.short_description = 'Plants'

    def get_users(self, obj):
        users = obj.assigned_users.all()
        if users:
            return ', '.join([u.get_full_name() for u in users])
        return '-'
    get_users.short_description = 'Assigned Users'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
