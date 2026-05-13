from django.urls import path
from . import views

app_name = 'accidents'

urlpatterns = [

    # Dashboard
    path('', views.IncidentDashboardView.as_view(), name='dashboard'),
    path('dashboard/', views.IncidentAccidentDashboardView.as_view(), name='IncidentAccidentDashboardView'),

    # incidents types 
    path('incident-types/', views.IncidentTypeListView.as_view(),name='incident_type_list'),
    path('incident-types/create/', views.IncidentTypeCreateView.as_view(),name='incident_type_create'),
    path('incident-types/<int:pk>/update/', views.IncidentTypeUpdateView.as_view(),name='incident_type_update'),
    path('incident-types/<int:pk>/delete/',views.IncidentTypeDeleteView.as_view(),name='incident_type_delete'),
    # Incident URLs
    path('incidents/', views.IncidentListView.as_view(), name='incident_list'),
    path('incidents/create/', views.IncidentCreateView.as_view(), name='incident_create'),
    path('incidents/<int:pk>/', views.IncidentDetailView.as_view(), name='incident_detail'),
    path('incidents/<int:pk>/edit/', views.IncidentUpdateView.as_view(), name='incident_update'),
    path('incidents/<int:pk>/pdf/', views.IncidentPDFDownloadView.as_view(), name='incident_pdf'),
    path('incidents/<int:pk>/delete/', views.IncidentDeleteView.as_view(), name='incident_delete'),

    # Investigation Report
    path('incidents/<int:incident_pk>/investigation/', views.InvestigationReportCreateView.as_view(), name='investigation_create'),
    
    # Action Items
    path('incidents/<int:incident_pk>/action-items/create/', views.ActionItemCreateView.as_view(), name='action_item_create'),
    path('export/excel/', views.ExportIncidentsExcelView.as_view(), name='export_incidents_excel'),
    
    # AJAX endpoints
    path('ajax/get-zones/', views.GetZonesForPlantAjaxView.as_view(), name='ajax_get_zones'),
    path('ajax/get-locations/', views.GetLocationsForZoneAjaxView.as_view(), name='ajax_get_locations'),
    path('ajax/get-sublocations/', views.GetSublocationsForLocationAjaxView.as_view(), name='ajax_get_sublocations'),
    path('api/zones-by-plant/<int:plant_id>/', views.get_zones_by_plant, name='ajax_get_zones_by_plant'),
    path('api/locations-by-zone/<int:zone_id>/', views.get_locations_by_zone, name='ajax_get_locations_by_zone'),
    path('api/sublocations-by-location/<int:location_id>/', views.get_sublocations_by_location, name='ajax_get_sublocations_by_location'),

    path('incidents/<int:pk>/closure-check/', views.IncidentClosureCheckView.as_view(), name='incident_closure_check'),
    path('incidents/<int:pk>/close/', views.IncidentClosureView.as_view(), name='incident_close'),
    path('incidents/<int:pk>/reopen/', views.IncidentReopenView.as_view(), name='incident_reopen'),
    # In apps/accidents/urls.py
    path('investigations/<int:pk>/', views.InvestigationDetailView.as_view(), name='investigation_detail'),
    path('incidents/<int:pk>/approve/', views.IncidentApprovalView.as_view(), name='incident_approve'),



    # accidents/urls.py
    path('notifications/',views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/mark-read/', views.MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_notifications_read'),
    path('my-action-items/', views.MyActionItemsView.as_view(), name='my_action_items'),
    path('action-items/<int:pk>/complete/', views.IncidentActionItemCompleteView.as_view(), name='action_item_complete'),
    
    
    
    path('incidents/<int:pk>/approve/', views.IncidentApprovalView.as_view(), name='incident_approve'),
]
