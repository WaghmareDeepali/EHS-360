# hazards/urls.py

from django.urls import path
from . import views

app_name = 'hazards'

urlpatterns = [
    # IMPORTANT: Dashboard URL ko HazardDashboardViews 
    path('', views.HazardDashboardView.as_view(), name='dashboard'),
    path('hazards/dashboard/', views.HazardDashboardViews.as_view(), name='hazard_dashboard'),
    
    
    path('hazards/', views.HazardListView.as_view(), name='hazard_list'),
    path('hazards/create/', views.HazardCreateView.as_view(), name='hazard_create'),
    path('hazards/<int:pk>/', views.HazardDetailView.as_view(), name='hazard_detail'),
    path('hazards/<int:pk>/edit/', views.HazardUpdateView.as_view(), name='hazard_update'),
    path('hazards/<int:pk>/delete/', views.HazardDeleteView.as_view(), name='hazard_delete'),
    path('hazards/<int:pk>/pdf/', views.HazardPDFView.as_view(), name='hazard_pdf'),
    
    # Action Items URLs
    path('hazards/<int:hazard_pk>/action-items/create/', views.HazardActionItemCreateView.as_view(), name='action_item_create'),
    path('action-items/<int:pk>/edit/', views.HazardActionItemUpdateView.as_view(), name='action_item_update'),

    # AJAX URLs for Cascading Dropdown
    path('ajax/get-zones/', views.GetZonesForPlantAjaxView.as_view(), name='ajax_get_zones'),
    path('ajax/get-locations/', views.GetLocationsForZoneAjaxView.as_view(), name='ajax_get_locations'),
    path('ajax/get-sublocations/', views.GetSubLocationsForLocationAjaxView.as_view(), name='ajax_get_sublocations'),
    path('<int:hazard_pk>/action/create/', views.HazardActionItemCreateView.as_view(), name='action_item_create'),
    path('action/<int:pk>/update/', views.HazardActionItemUpdateView.as_view(), name='action_item_update'),
    path('api/get-zones/<int:plant_id>/', views.get_zones_by_plant, name='ajax_get_zones_by_plant'),
    path('api/get-locations/<int:zone_id>/', views.get_locations_by_zone, name='ajax_get_locations_by_zone'),
    path('api/get-sublocations/<int:location_id>/', views.get_sublocations_by_location, name='ajax_get_sublocations_by_location'),

    # Export URL
    path('export-hazards/', views.ExportHazardsView.as_view(), name='export_hazards'),
    
    path('my-action-items/', views.MyActionItemsView.as_view(), name='my_action_items'),
    path('action-item/<int:pk>/complete/', views.ActionItemCompleteView.as_view(), name='action_item_complete'),

]