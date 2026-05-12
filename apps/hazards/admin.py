from django.contrib import admin
from .models import Hazard, HazardPhoto, HazardVideo, HazardActionItem, HazardNotification


@admin.register(Hazard)
class HazardAdmin(admin.ModelAdmin):
    list_display = ['report_number', 'hazard_type', 'severity', 'status', 'plant', 'reported_by', 'created_at']
    list_filter = ['hazard_type', 'severity', 'status', 'approval_status', 'plant', 'created_at']
    search_fields = ['report_number', 'hazard_title', 'hazard_description', 'reported_by__email']
    readonly_fields = ['report_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(HazardActionItem)
class HazardActionItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'hazard', 'status', 'created_by', 'is_self_assigned', 'target_date', 'created_at']
    list_filter = ['status', 'is_self_assigned', 'created_at']
    search_fields = ['action_description', 'hazard__report_number', 'responsible_emails']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(HazardPhoto)
class HazardPhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'hazard', 'photo_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['photo_type', 'uploaded_at']
    search_fields = ['hazard__report_number', 'description']
    readonly_fields = ['uploaded_at']


@admin.register(HazardVideo)
class HazardVideoAdmin(admin.ModelAdmin):
    list_display = ['id', 'hazard', 'video_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['video_type', 'uploaded_at']
    search_fields = ['hazard__report_number', 'description']
    readonly_fields = ['uploaded_at']


@admin.register(HazardNotification)
class HazardNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient', 'hazard', 'notifications_type', 'is_read', 'created_at']
    list_filter = ['notifications_type', 'is_read', 'created_at']
    search_fields = ['recipient__email', 'hazard__report_number', 'title', 'message']
    readonly_fields = ['created_at']