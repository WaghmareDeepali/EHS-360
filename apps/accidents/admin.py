from django.contrib import admin
from .models import *


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = [
        'report_number', 'incident_type', 'incident_date', 'incident_time',
        'affected_person_name', 'plant', 'location', 'status', 'reported_by', 'reported_date'
    ]
    list_filter = [
        'incident_type', 'status', 'plant', 'location', 
        'incident_date', 'investigation_required'
    ]
    search_fields = [
        'report_number', 'affected_person_name', 'affected_person_employee_id',
        'description', 'nature_of_injury'
    ]
    readonly_fields = [
        'report_number', 'reported_by', 'reported_date', 
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Incident Information', {
            'fields': (
                'report_number', 'incident_type', 'incident_date', 'incident_time'
            )
        }),
        ('Location', {
            'fields': ('plant', 'zone', 'location', 'sublocation')
        }),
        ('Incident Details', {
            'fields': ('description', 'nature_of_injury')
        }),
        ('Unsafe Acts & Conditions', {
            'fields': (
                'unsafe_acts', 'unsafe_acts_other',
                'unsafe_conditions', 'unsafe_conditions_other'
            ),
            'classes': ('collapse',)
        }),
        ('Affected Person', {
            'fields': (
                'affected_person', 'affected_person_name', 
                'affected_person_employee_id', 'affected_person_department',
                'affected_body_parts'
            )
        }),
        ('Reporting', {
            'fields': ('reported_by', 'reported_date')
        }),
        ('Investigation', {
            'fields': (
                'investigation_required', 'investigation_deadline',
                'investigation_completed_date', 'investigator',
                'root_cause', 'contributing_factors'
            ),
            'classes': ('collapse',)
        }),
        ('Action Plan', {
            'fields': (
                'action_plan', 'action_plan_deadline',
                'action_plan_responsible_person', 'action_plan_status'
            ),
            'classes': ('collapse',)
        }),
        ('Workflow', {
            'fields': ('status', 'assigned_to')
        }),
        ('Notifications', {
            'fields': (
                'safety_manager_notified', 'location_head_notified',
                'plant_head_notified'
            ),
            'classes': ('collapse',)
        }),
        ('Closure', {
            'fields': (
                'closure_date', 'closed_by', 'closure_remarks',
                'lessons_learned', 'preventive_measures', 'is_recurrence_possible'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.reported_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(IncidentPhoto)
class IncidentPhotoAdmin(admin.ModelAdmin):
    list_display = ['incident', 'photo_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['photo_type', 'uploaded_at']
    search_fields = ['incident__report_number', 'description']
    readonly_fields = ['uploaded_by', 'uploaded_at']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(IncidentVideo)
class IncidentVideoAdmin(admin.ModelAdmin):
    list_display = ['incident', 'video_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['video_type', 'uploaded_at']
    search_fields = ['incident__report_number', 'description']
    readonly_fields = ['uploaded_by', 'uploaded_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(IncidentInvestigationReport)
class IncidentInvestigationReportAdmin(admin.ModelAdmin):
    list_display = [
        'incident', 'investigation_date', 'investigator', 
        'completed_by', 'completed_date'
    ]
    list_filter = ['investigation_date', 'completed_date']
    search_fields = [
        'incident__report_number', 'sequence_of_events',
        'root_cause_analysis'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Investigation Details', {
            'fields': (
                'incident', 'investigation_date', 'investigator',
                'investigation_team'
            )
        }),
        ('Findings', {
            'fields': (
                'sequence_of_events', 'root_cause_analysis',
                 'personal_factors', 'job_factors'
            )
        }),
        ('Evidence', {
            'fields': ('evidence_collected', 'witness_statements')
        }),
        # ('Recommendations', {
        #     'fields': (
        #         'immediate_corrective_actions', 'preventive_measures',
        #         'long_term_recommendations'
        #     )
        # }),
        # ✅ FIX: Removed fields that no longer exist on the model
        ('Sign-off', {
            'fields': (
                'completed_by', 'completed_date',
                'reviewed_by', 'reviewed_date'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(IncidentActionItem)
class IncidentActionItemAdmin(admin.ModelAdmin):
    list_display = [
        'incident',
        'action_description',
        'get_responsible_persons',
        'target_date',
        'status',
        'completion_date',
    ]

    list_filter = ['status', 'target_date', 'completion_date']
    search_fields = [
        'incident__report_number',
        'action_description',
        'responsible_person__first_name',
        'responsible_person__last_name',
    ]
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Action Item', {
            'fields': (
                'incident',
                'action_description',
                'responsible_person',
                'target_date'
            )
        }),
        ('Status', {
            'fields': ('status', 'completion_date')
        }),
        ('Verification', {
            'fields': ('verified_by', 'verification_date'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_responsible_persons(self, obj):
        return ", ".join(
            user.get_full_name() or user.username
            for user in obj.responsible_person.all()
        )

    get_responsible_persons.short_description = "Responsible Person(s)"
@admin.register(IncidentNotification)
class IncidentNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient', 'incident', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'incident__report_number', 'title']
    readonly_fields = ['created_at', 'read_at']
    list_per_page = 50
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('recipient', 'incident')