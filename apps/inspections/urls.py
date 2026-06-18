from django.urls import path
from . import views

app_name = 'inspections'

urlpatterns = [
    # Dashboard
    # path('', views.inspection_dashboard, name='inspection_dashboard'),
    
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # Questions
    path('questions/', views.question_list, name='question_list'),
    path('questions/create/', views.question_create, name='question_create'),
    path('questions/<int:pk>/', views.question_detail, name='question_detail'),
    path('questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('questions/<int:pk>/delete/', views.question_delete, name='question_delete'),
    
    # Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/', views.template_detail, name='template_detail'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/add-question/', views.template_add_question, name='template_add_question'),
    path('templates/<int:pk>/bulk-add-questions/', views.template_bulk_add_questions, name='template_bulk_add_questions'),
    path('templates/<int:template_pk>/remove-question/<int:question_pk>/', views.template_remove_question, name='template_remove_question'),
    path('templates/<int:pk>/reorder-questions/', views.template_reorder_questions, name='template_reorder_questions'),
    path('templates/<int:pk>/clone/', views.template_clone, name='template_clone'),
    
    # Schedules
    path('schedules/', views.schedule_list, name='schedule_list'),
    path('schedules/create/', views.schedule_create, name='schedule_create'),
    path('schedules/<int:pk>/', views.schedule_detail, name='schedule_detail'),
    path('schedules/<int:pk>/pdf/', views.InspectionPDFDownloadView.as_view(), name='schedule_pdf'),
    path('schedules/<int:pk>/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedules/<int:pk>/delete/', views.schedule_delete, name='schedule_delete'),
    path('schedules/<int:pk>/cancel/', views.schedule_cancel, name='schedule_cancel'),
    path('schedules/<int:pk>/send-reminder/', views.schedule_send_reminder, name='schedule_send_reminder'),
    path('schedules/<int:pk>/restart/', views.schedule_restart, name='schedule_restart'),
    # path('inspection_dashboard/', views.InspectionDashboardView.as_view(), name='inspection_dashboard'), 
    path(
        "inspection_dashboard/",
        views.InspectionDashboardView.as_view(),
        name="inspection_dashboard"
    ),
    # My Inspections (for HODs)
    path('my-inspections/', views.my_inspections, name='my_inspections'),
    
    # Inspection Execution
    path('inspection/<int:schedule_id>/start/', views.inspection_start, name='inspection_start'),
    path('inspection/<int:schedule_id>/submit/', views.inspection_submit, name='inspection_submit'),
    path('inspection/review/<int:submission_id>/', views.inspection_review, name='inspection_review'),
    
    # ✅ No Answers Views - ADD THESE
    path('no-answers/', views.no_answers_list, name='no_answers_list'),
    path('no-answers/by-question/', views.no_answers_by_question, name='no_answers_by_question'),
    
    # ✅ Bulk Assignment - ADD THIS
    # path('no-answers/bulk-assign/', views.bulk_assign_no_answers, name='bulk_assign_no_answers'),
    
    # ✅ Convert to Hazard - ADD THIS
    path('response/<int:response_id>/convert-to-hazard/', views.convert_no_answer_to_hazard, name='convert_no_answer_to_hazard'),
    # Auto-schedule toggle (stop/pause/resume)
    path('autoschedule/<int:config_id>/toggle/', views.autoschedule_toggle, name='autoschedule_toggle'),

    # AJAX: Get users by selected plants
    path('ajax/get-users-by-plants/', views.get_users_by_plants, name='get_users_by_plants'),
    path('ajax/get-users-by-role/', views.get_users_by_role, name='get_users_by_role'),
    path('ajax/get-users-by-roles/', views.get_users_by_roles, name='get_users_by_roles'),
    # AJAX Endpoints

    path('ajax/get-zones/', views.get_zones_by_plant, name='get_zones_by_plant'),
    path('ajax/get-locations/', views.get_locations_by_zone, name='get_locations_by_zone'),
    path('ajax/get-sublocations/', views.get_sublocations_by_location, name='get_sublocations_by_location'),
    path('ajax/get-questions/', views.get_questions_by_category, name='get_questions_by_category'),
    path('ajax/get-template-inspection-type/', views.get_template_inspection_type, name='get_template_inspection_type'),
    path('schedules/<int:pk>/clone/', views.schedule_clone, name='schedule_clone'),
]
