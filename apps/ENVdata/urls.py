from django.urls import path
from .views import *

app_name = 'environmental'

urlpatterns = [
    # Main views
    path('plant-entry/', PlantMonthlyEntryView.as_view(), name='plant-entry'),
    path('plant-data-view/', PlantDataDisplayView.as_view(), name='plant-data-view'),
    path('admin-all-plants/', AdminAllPlantsDataView.as_view(), name='admin-all-plants'),
    path('questions-manager/', EnvironmentalQuestionsManagerView.as_view(), name='questions-manager'),
    path('questions-manager/edit/<int:question_id>/', EnvironmentalQuestionsManagerView.as_view(), name='questions-manager-edit'),
    path('unit-manager/', UnitManagerView.as_view(), name='unit-manager'),
    # path('api/get-source-fields/', views.get_source_fields, name='get-source-fields'),

    # API endpoints
    path('api/get-category-units/', GetCategoryUnitsAPIView.as_view(), name='get-category-units'),
    path('update-question-sequence/',UpdateQuestionSequenceView.as_view(),name='update-question-sequence'),
    path('api/get-source-fields/', GetSourceFieldsAPIView.as_view(), name='get-source-fields'),
    path('api/get-base-unit/', GetCategoryBaseUnitAPIView.as_view(), name='api-get-base-unit'),
    path('dashboard/', EnvironmentalDashboardView.as_view(), name='dashboard'),

    path("export_excel/",ExportExcelView.as_view(),name="export_excel"),

    path('attachment/upload/',UploadAttachmentView.as_view(),   name='attachment-upload'),
    path('attachment/<int:attachment_id>/download/',DownloadAttachmentView.as_view(), name='attachment-download'),
    path('attachment/<int:attachment_id>/delete/', DeleteAttachmentView.as_view(),   name='attachment-delete'),
]