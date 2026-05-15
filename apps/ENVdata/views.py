from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import models
from django.http import FileResponse, Http404, JsonResponse
from django.http import HttpResponse
from datetime import datetime
from django.core.paginator import Paginator 
from apps.accounts.models import User
from apps.accidents.models import Incident
from apps.hazards.models import Hazard
from apps.inspections.models import InspectionTemplate, InspectionSchedule
from apps.organizations.models import Plant
from .models import *
from .utils import *
from django.shortcuts import render, redirect, get_object_or_404
from apps.notifications.services import NotificationService

from django.views.generic import TemplateView
from django.db.models import Count, Sum, Q
from django.utils import timezone
import json
from .models import MonthlyIndicatorData, EnvironmentalQuestion, UnitCategory
from collections import Counter
from .models import MonthlyIndicatorAttachment
from datetime import datetime
# =========================================================
# API ENDPOINTS FOR QUESTIONS MANAGER
# =========================================================

class GetSourceFieldsAPIView(LoginRequiredMixin, View):
    """
    API to get available fields and their choices for a source type
    Incident types are fetched from database, Hazard types are hardcoded choices
    """
    def get(self, request):
        from apps.accidents.models import IncidentType
        
        source_type = request.GET.get('source_type')
        
        if not source_type:
            return JsonResponse({
                'success': False,
                'error': 'Source type is required'
            }, status=400)
        
        try:
            fields = []
            
            if source_type == 'INCIDENT':
                # ✅ Get incident types from database (DYNAMIC)
                incident_types = IncidentType.objects.filter(is_active=True).order_by('name')
                incident_type_choices = [
                    {'value': str(it.id), 'display': f"{it.code} - {it.name}"}
                    for it in incident_types
                ]
                
                # ✅ Get incident status choices from model
                from apps.accidents.models import Incident
                status_choices = []
                if hasattr(Incident, 'STATUS_CHOICES'):
                    status_choices = [
                        {'value': choice[0], 'display': choice[1]} 
                        for choice in Incident.STATUS_CHOICES
                    ]
                
                fields = [
                    {
                        'field_name': 'incident_type',
                        'field_verbose_name': 'Incident Type',
                        'choices': incident_type_choices
                    },
                    {
                        'field_name': 'status',
                        'field_verbose_name': 'Status',
                        'choices': status_choices if status_choices else [
                            {'value': 'REPORTED', 'display': 'Reported'},
                            {'value': 'UNDER_INVESTIGATION', 'display': 'Under Investigation'},
                            {'value': 'ACTION_IN_PROGRESS', 'display': 'Action In Progress'},
                            {'value': 'COMPLETED', 'display': 'Completed'},
                            {'value': 'CLOSED', 'display': 'Closed'},
                        ]
                    },
                    {
                        'field_name': 'plant',
                        'field_verbose_name': 'Plant',
                        'choices': [
                            {'value': str(p.id), 'display': p.name}
                            for p in Plant.objects.filter(is_active=True).order_by('name')
                        ]
                    }
                ]
            
            elif source_type == 'HAZARD':
                try:
                    # ✅ Get hazard types from MODEL CHOICES (HARDCODED)
                    from apps.hazards.models import Hazard
                    
                    # Get hazard type choices from model
                    hazard_type_choices = []
                    if hasattr(Hazard, 'HAZARD_TYPE_CHOICES'):
                        hazard_type_choices = [
                            {'value': choice[0], 'display': choice[1]} 
                            for choice in Hazard.HAZARD_TYPE_CHOICES
                        ]
                    
                    # Get severity choices from model
                    severity_choices = []
                    if hasattr(Hazard, 'SEVERITY_CHOICES'):
                        severity_choices = [
                            {'value': choice[0], 'display': choice[1]} 
                            for choice in Hazard.SEVERITY_CHOICES
                        ]
                    
                    # Get status choices from model
                    hazard_status_choices = []
                    if hasattr(Hazard, 'STATUS_CHOICES'):
                        hazard_status_choices = [
                            {'value': choice[0], 'display': choice[1]} 
                            for choice in Hazard.STATUS_CHOICES
                        ]
                    
                    fields = [
                        {
                            'field_name': 'hazard_type',
                            'field_verbose_name': 'Hazard Type',
                            'choices': hazard_type_choices if hazard_type_choices else []
                        },
                        {
                            'field_name': 'severity',
                            'field_verbose_name': 'Severity',
                            'choices': severity_choices if severity_choices else [
                                {'value': 'low', 'display': 'Low'},
                                {'value': 'medium', 'display': 'Medium'},
                                {'value': 'high', 'display': 'High'},
                                {'value': 'critical', 'display': 'Critical'},
                            ]
                        },
                        {
                            'field_name': 'status',
                            'field_verbose_name': 'Status',
                            'choices': hazard_status_choices if hazard_status_choices else []
                        },
                        {
                            'field_name': 'plant',
                            'field_verbose_name': 'Plant',
                            'choices': [
                                {'value': str(p.id), 'display': p.name}
                                for p in Plant.objects.filter(is_active=True).order_by('name')
                            ]
                        }
                    ]
                
                except ImportError:
                    # ✅ Fallback if hazard module doesn't exist
                    return JsonResponse({
                        'success': False,
                        'error': 'Hazard module is not available'
                    }, status=400)
            elif source_type=='INSPECTION':
                try:
                    from apps.inspections.models import InspectionTemplate
                    templates=InspectionTemplate.objects.filter(is_active=True).order_by('template_name')
                    template_choices=[
                        {'value':str(t.id),'display':f"{t.template_code}-{t.template_name}"}
                        for t in templates
                    ]
                    inspection_type_choices=[
                        {'value':choice[0],'display':choice[1]}
                        for choice in InspectionTemplate.INSPECTION_TYPE_CHOICES
                    ]
                    from apps.inspections.models import InspectionSchedule
                    status_choices=[
                        {'value':choice[0],'display':choice[1]}
                        for choice in InspectionSchedule.STATUS_CHOICES
                    ]
                    fields = [
                        {
                            'field_name': 'template',
                            'field_verbose_name': 'Inspection Template',
                            'choices': template_choices
                        },
                        {
                            'field_name': 'inspection_type',
                            'field_verbose_name': 'Inspection Type',
                            'choices': inspection_type_choices
                        },
                        {
                            'field_name': 'status',
                            'field_verbose_name': 'Status',
                            'choices': status_choices
                        },
                        {
                            'field_name': 'plant',
                            'field_verbose_name': 'Plant',
                            'choices': [
                                {'value': str(p.id), 'display': p.name}
                                for p in Plant.objects.filter(is_active=True).order_by('name')
                            ]
                        }
                    ]
                except ImportError:
                    return JsonResponse({
                        'success':False,
                        'error':'Inspection module is not available'
                    },status=400)
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid source type'
                }, status=400)
            
            return JsonResponse({
                'success': True,
                'fields': fields
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
# =========================================================
# UNIT MANAGER
# =========================================================

class UnitManagerView(LoginRequiredMixin, View):
    template_name = "data_collection/unit_manager.html"

    def get(self, request):
        categories = UnitCategory.objects.filter(is_active=True).prefetch_related('units')
        units = Unit.objects.filter(is_active=True).select_related("category")
        cancel_url = (request.GET.get('next')or request.META.get('HTTP_REFERER')or '/')

        return render(request, self.template_name, {
            "categories": categories,
            "units": units,
            "cancel_url": cancel_url
        })

    def post(self, request):
        action = request.POST.get("action")

        # ---------- CREATE CATEGORY ----------
        if action == "create_category":
            name = (request.POST.get("category_name") or "").strip()
            description = (request.POST.get("category_description") or "").strip()
            is_active = request.POST.get("category_is_active") == "on"

            if not name:
                messages.error(request, "Category name is required")
                return redirect("environmental:unit-manager")

            # Check if category already exists
            if UnitCategory.objects.filter(name__iexact=name).exists():
                messages.error(request, f"Category '{name}' already exists")
                return redirect("environmental:unit-manager")

            try:
                UnitCategory.objects.create(
                    name=name,
                    description=description,
                    is_active=is_active,
                    created_by=request.user,
                    created_at=datetime.now()
                )
                messages.success(request, f"✓ Category '{name}' created successfully!")
            except Exception as e:
                messages.error(request, f"Error creating category: {str(e)}")

            return redirect("environmental:unit-manager")

        # ---------- CREATE UNIT ----------
        elif action == "create_unit":
            category_id = request.POST.get("unit_category")
            name = (request.POST.get("unit_name") or "").strip()
            base_unit = (request.POST.get("unit_base_unit") or "").strip()
            conversion_rate = request.POST.get("unit_conversion_rate")
            is_active = request.POST.get("unit_is_active") == "on"

            # Validate only unit fields
            if not category_id:
                messages.error(request, "Please select a category for the unit")
                return redirect("environmental:unit-manager")

            if not name:
                messages.error(request, "Unit name is required")
                return redirect("environmental:unit-manager")

            if not base_unit:
                messages.error(request, "Base unit is required")
                return redirect("environmental:unit-manager")

            if not conversion_rate:
                messages.error(request, "Conversion rate is required")
                return redirect("environmental:unit-manager")

            try:
                category = UnitCategory.objects.get(id=category_id)
                conversion_rate = float(conversion_rate)

                if conversion_rate <= 0:
                    messages.error(request, "Conversion rate must be greater than 0")
                    return redirect("environmental:unit-manager")

                # Check if unit already exists in this category
                if Unit.objects.filter(category=category, name__iexact=name).exists():
                    messages.error(request, f"Unit '{name}' already exists in category '{category.name}'")
                    return redirect("environmental:unit-manager")

                Unit.objects.create(
                    category=category,
                    name=name,
                    base_unit=base_unit,
                    conversion_rate=conversion_rate,
                    is_active=is_active,
                    created_by=request.user,
                )

                messages.success(request, f"✓ Unit '{name}' created successfully in category '{category.name}'!")

            except UnitCategory.DoesNotExist:
                messages.error(request, "Invalid category selected")
            except ValueError:
                messages.error(request, "Conversion rate must be a valid number")
            except Exception as e:
                messages.error(request, f"Error creating unit: {str(e)}")

            return redirect("environmental:unit-manager")

        # ---------- DELETE CATEGORY ----------
        elif action == "delete_category":
            category_id = request.POST.get("category_id")
            try:
                category = UnitCategory.objects.get(id=category_id)
                category_name = category.name
                
                # Hard Delete: Database se permanent delete karne ke liye
                category.delete() 
                
                messages.success(request, f"✓ Category '{category_name}' and its units deleted permanently!")
            except UnitCategory.DoesNotExist:
                messages.error(request, "Category not found")
            except Exception as e:
                messages.error(request, f"Error deleting category: {str(e)}")
            
            return redirect("environmental:unit-manager")

        # ---------- DELETE UNIT ----------
        elif action == "delete_unit":
            unit_id = request.POST.get("unit_id")
            try:
                unit = Unit.objects.get(id=unit_id)
                unit_name = unit.name
                
                # Hard Delete: Database se permanent delete karne ke liye
                unit.delete()
                
                messages.success(request, f"✓ Unit '{unit_name}' deleted permanently!")
            except Unit.DoesNotExist:
                messages.error(request, "Unit not found")
            except Exception as e:
                messages.error(request, f"Error deleting unit: {str(e)}")
            
            return redirect("environmental:unit-manager")

        return redirect("environmental:unit-manager")


# =========================================================
# PLANT MONTHLY ENTRY
# =========================================================
from decimal import Decimal  # <-- add this

class PlantMonthlyEntryView(LoginRequiredMixin, View):
    template_name = "data_collection/data_env.html"

    def get_user_plants(self, request):
        user = request.user
        if user.is_superuser or user.is_staff or getattr(user, 'is_admin_user', False):
            return Plant.objects.filter(is_active=True).order_by('name')

        assigned = user.assigned_plants.filter(is_active=True)
        if not assigned.exists() and getattr(user, 'plant', None):
            return Plant.objects.filter(id=user.plant.id, is_active=True)

        return assigned.order_by('name')

    def get_selected_plant(self, request):
        plant_id = request.GET.get('plant_id') or request.POST.get('selected_plant_id')
        if plant_id:
            return self.get_user_plants(request).filter(id=plant_id).first()
        return self.get_user_plants(request).first()

    def get_questions(self):
        return EnvironmentalQuestion.objects.filter(
            is_active=True
        ).select_related('unit_category', 'default_unit').prefetch_related('selected_units').order_by("is_system", "order", "id")

    def slugify_field(self, text):
        return (
            text.lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("(", "")
            .replace(")", "")
            .replace("+", "")
            .replace(",", "")
            .replace(".", "")
            .replace(";", "")
            .replace("'", "")
        )

    def get(self, request):
        user_plants = self.get_user_plants(request)
        if not user_plants.exists():
            return render(request, "no_plant_assigned.html")

        selected_plant = self.get_selected_plant(request)
        if not selected_plant:
            return render(request, "no_plant_assigned.html")

        questions = self.get_questions()
        if not questions.exists():
            return render(request, self.template_name, {
                "selected_plant": selected_plant,
                "user_plants": user_plants,
                "no_questions": True,
            })

        current_year = datetime.now().year

        # Get auto-populated data
        auto_data = EnvironmentalDataFetcher.get_data_for_plant_year(selected_plant, current_year)

        # Fetch saved monthly data
        saved_data = MonthlyIndicatorData.objects.filter(
            plant=selected_plant,
            indicator__isnull=False,
            indicator__source_type='MANUAL'  # only manual data
        ).select_related('indicator', 'unit')
        
        # Organize saved data including units
        saved_dict = {}
        for d in saved_data:
            if d.indicator not in saved_dict:
                saved_dict[d.indicator] = {}
            saved_dict[d.indicator][d.month.lower()] = {
                'value': d.value,
                'unit': d.unit  # Store the Unit object
            }

        # MONTHS = MonthlyIndicatorData.MONTH_CHOICES

        today = datetime.now()
        current_year = today.year

        current_month = today.strftime("%b").upper()
        from calendar import month_abbr

        current_month_num = today.month
        prev_month_num = current_month_num - 1 if current_month_num > 1 else 12
        previous_month = month_abbr[prev_month_num].upper()

        current_day = today.day

        is_admin = request.user.is_superuser or request.user.is_staff or getattr(request.user, 'is_admin_user', False)
        FREEZE_DAY = 10

        # If current month is Jan–Mar → FY started last year
        if today.month < 4:
            fy_start_year = current_year - 1
        else:
            fy_start_year = current_year

        FY_MONTH_ORDER = [
            "APR", "MAY", "JUN", "JUL", "AUG", "SEP",
            "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"
        ]

        month_dict = dict(MonthlyIndicatorData.MONTH_CHOICES)

        MONTHS = []
        for m in FY_MONTH_ORDER:
            month_name = month_dict.get(m)

            # Jan–Mar → next year
            if m in ["JAN", "FEB", "MAR"]:
                year = fy_start_year + 1
            else:
                year = fy_start_year

            MONTHS.append((m, f"{month_name} {year}"))
            
        # Build question + month data for template
        questions_with_data = []
        for q in questions:
            default_unit_name = q.default_unit.name if q.default_unit else "Count"
            default_unit_id = q.default_unit.id if q.default_unit else None
            
            # Check if this question has auto-calculation
            is_auto = q.source_type != 'MANUAL'

            # Get available units for this question
            available_units = []
            if q.selected_units.exists():
                available_units = list(q.selected_units.all())
            elif q.default_unit:
                available_units = [q.default_unit]

            month_rows = []
            for month_code, month_name in MONTHS:
                if is_admin:
                    is_editable = True
                else:
                    is_editable = (month_code == previous_month and current_day <= FREEZE_DAY)
                    # This for testing Freeze data "Monthly Testing and Date "
                    # TEST_MODE = True

                    # if TEST_MODE:
                    #     current_month = "NOV"
                    #     previous_month = "OCT"
                    # else:
                    #     current_month = today.strftime("%b").upper()
                    #     prev_month_num = current_month_num - 1 if current_month_num > 1 else 12
                    #     previous_month = month_abbr[prev_month_num].upper()
                    # is_editable = (month_code == previous_month and current_day <= FREEZE_DAY)
                    # This for testing Freeze data
                    # is_editable = (month_code == previous_month and 1 <= current_day <= 7)
                month_key = month_code.lower()
                value = ''
                saved_unit_name = default_unit_name

                # MANUAL data
                if q.source_type == 'MANUAL':
                    if q in saved_dict and month_key in saved_dict[q]:
                        value = saved_dict[q][month_key]['value']
                        saved_unit_name = saved_dict[q][month_key]['unit'].name if saved_dict[q][month_key]['unit'] else default_unit_name

                # AUTO data 
                else:
                    base_month_name = month_name.split(" ")[0]
                    if base_month_name in auto_data.get(q.question_text, {}):
                        value = auto_data[q.question_text][base_month_name]

                        saved_unit_name = "Count"

                # Find the unit ID for the saved unit
                saved_unit_id = default_unit_id
                for unit in available_units:
                    if unit.name == saved_unit_name:
                        saved_unit_id = unit.id
                        break
                attachments_dict = {}
                for att in MonthlyIndicatorAttachment.objects.filter(plant=selected_plant).select_related('indicator'):
                    attachments_dict[(att.indicator_id, att.month)] = att

                month_rows.append({
                    "code": month_code,
                    "name": month_name,
                    "value": value,
                    "saved_unit_id": saved_unit_id,
                    "saved_unit_name": saved_unit_name,
                    "attachment":attachments_dict.get((q.id,month_code)),
                    "is_editable": is_editable
                })

            questions_with_data.append({
                "question": q.question_text,
                "question_id": q.id,
                "default_unit_name": default_unit_name,
                "default_unit_id": default_unit_id,
                "available_units": available_units,
                "months": month_rows,
                "slugified": self.slugify_field(q.question_text),
                "is_auto_populated": is_auto,
                "source_type": q.source_type,
            })

        context = {
            "selected_plant": selected_plant,
            "user_plants": user_plants,
            "questions_with_data": questions_with_data,
            "months": MONTHS,
            "current_year": current_year,
            "total_questions": len(questions_with_data),
            "auto_populated_count": sum(1 for q in questions_with_data if q['is_auto_populated']),
            "manual_entry_count": len(questions_with_data) - sum(1 for q in questions_with_data if q['is_auto_populated']),
        }

        return render(request, self.template_name, context)

    def post(self, request):
        selected_plant_id = request.POST.get('selected_plant_id')
        if not selected_plant_id:
            messages.error(request, "Please select a plant")
            return redirect("environmental:plant-entry")

        user_plants = self.get_user_plants(request)
        selected_plant = user_plants.filter(id=selected_plant_id).first()
        if not selected_plant:
            messages.error(request, "Invalid plant selected")
            return redirect("environmental:plant-entry")

        questions = self.get_questions()
        # ✅ ADD THIS BLOCK
        today = datetime.now()
        current_month = today.strftime("%b").upper()
        current_day = today.day

        from calendar import month_abbr

        current_month_num = today.month
        prev_month_num = current_month_num - 1 if current_month_num > 1 else 12
        previous_month = month_abbr[prev_month_num].upper()

        is_admin = request.user.is_superuser or request.user.is_staff or getattr(request.user, 'is_admin_user', False)
        FREEZE_DAY = 10

        # ✅ Replace MONTHS with FY order
        FY_MONTH_ORDER = [
            "APR", "MAY", "JUN", "JUL", "AUG", "SEP",
            "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"
        ]

        MONTHS = [(m, dict(MonthlyIndicatorData.MONTH_CHOICES).get(m)) for m in FY_MONTH_ORDER]

        saved_count = 0

        for q in questions:
            # Skip auto-calculated questions
            if q.source_type != 'MANUAL':
                continue

            slug = self.slugify_field(q.question_text)
            default_unit = q.default_unit  # fallback Unit object
            for month_code, month_name in MONTHS:
                if not is_admin:
                    if not (month_code == previous_month and current_day <= FREEZE_DAY):
                    # This for testing Freeze data
                    # if not (month_code == current_month and 9 <= current_day <= 16):
                        continue
                value_field = f"{slug}_{month_code.lower()}"
                unit_field = f"{slug}_{month_code.lower()}_unit"

                value = (request.POST.get(value_field) or "").strip()
                selected_unit_id = request.POST.get(unit_field)

                # Determine selected Unit object
                unit_obj = default_unit
                if selected_unit_id:
                    try:
                        unit_obj = Unit.objects.get(id=selected_unit_id)
                    except Unit.DoesNotExist:
                        unit_obj = default_unit

                # Delete if value empty
                if not value:
                    MonthlyIndicatorData.objects.filter(
                        plant=selected_plant,
                        indicator=q,
                        month=month_code
                    ).delete()
                    continue

                try:
                    # Convert input string to float first to handle decimals entered by user
                    raw_numeric_value = float(value.replace(",", ""))

                    # Apply conversion rate if the unit is not the base unit
                    # if unit_obj and unit_obj.base_unit != unit_obj.name:
                    #     raw_numeric_value = raw_numeric_value * float(unit_obj.conversion_rate)

                    if unit_obj and unit_obj.base_unit != unit_obj.name:
                        # Only convert if value is small (means user input, not stored value)
                        if raw_numeric_value < float(unit_obj.conversion_rate):
                            raw_numeric_value = raw_numeric_value * float(unit_obj.conversion_rate)
                    # ✅ Convert to Integer by rounding to the nearest whole number
                    # This ensures that 10.5 becomes 11 and 10.4 becomes 10
                    final_integer_value = int(round(raw_numeric_value))

                    obj, created = MonthlyIndicatorData.objects.update_or_create(
                        plant=selected_plant,
                        indicator=q,
                        month=month_code,
                        defaults={
                            "value": str(final_integer_value),  # Save as string integer
                            "unit": unit_obj,
                            "created_by": request.user,
                        }
                    )
                    saved_count += 1

                except (ValueError, TypeError):
                    messages.warning(request, f"Invalid value for {q.question_text} in {month_name}")
                    continue
                
        if saved_count > 0:
            NotificationService.notify(
                content_object=selected_plant,
                notification_type='ENV_DATA_SUBMITTED',
                module='ENV'
            )

        messages.success(request, f"✓ Data saved successfully! {saved_count} entries updated for {selected_plant.name}")
        return redirect(f"{request.path}?plant_id={selected_plant.id}&saved=1")



# =========================================================
# QUESTIONS MANAGER
# =========================================================

class EnvironmentalQuestionsManagerView(LoginRequiredMixin, View):
    template_name = "data_collection/questions_manager.html"

    def get(self, request, question_id=None):
        """
        Handles both displaying the list of questions and the form for adding/editing a question.
        If 'question_id' is provided in the URL, it populates the form for editing.
        """
        categories = UnitCategory.objects.filter(is_active=True)
        
        # Initialize an empty question instance for the "add" form
        editing_question = None

        # If a question_id is passed, it means we are editing
        if question_id:
            # Fetch the question object or return a 404 error if not found
            editing_question = get_object_or_404(EnvironmentalQuestion, id=question_id)

        return render(request, self.template_name, {
            "questions": self.load_questions(),
            "categories": categories,
            "editing_question": editing_question,  # Pass the question object to the template
        })

    def post(self, request, question_id=None):
        """
        Handles form submissions for adding, updating, and deleting questions.
        """
        action = request.POST.get("action")

        # Define a dictionary to map actions to handler methods
        actions = {
            "add": self.add_question,
            "update": self.update_question, # Naya action
            "delete": self.delete_question,
        }

        # Call the appropriate handler based on the action
        # If question_id is present, pass it to the handler
        if action in actions:
            if question_id:
                return actions[action](request, question_id)
            else:
                return actions[action](request)
        
        # Default redirect if no action matches
        return redirect("environmental:questions-manager")

    def load_questions(self):
        """Load questions with human-readable filter descriptions"""
        from apps.accidents.models import IncidentType
        
        questions_list = []
        for q in EnvironmentalQuestion.objects.filter(is_active=True).order_by("is_system", "order", "id"):
            selected_units = q.selected_units.all()
            
            filter_desc = ""
            if q.filter_field and q.filter_value:
                # Get human-readable filter description
                filter_field_name = q.get_filter_field_display() if hasattr(q, 'get_filter_field_display') else q.filter_field
                
                # ✅ Handle different field types
                if q.filter_field == 'incident_type':
                    try:
                        incident_type = IncidentType.objects.get(id=q.filter_value)
                        filter_value_display = f"{incident_type.code} - {incident_type.name}"
                    except IncidentType.DoesNotExist:
                        filter_value_display = q.filter_value
                
                elif q.filter_field == 'hazard_type':
                    try:
                        from apps.hazards.models import HazardType
                        hazard_type = HazardType.objects.get(id=q.filter_value)
                        filter_value_display = f"{hazard_type.code} - {hazard_type.name}"
                    except:
                        filter_value_display = q.filter_value
                
                # ========================================
                # ⬇️ ADD THIS NEW SECTION FOR INSPECTION
                # ========================================
                elif q.filter_field == 'template':
                    try:
                        from apps.inspections.models import InspectionTemplate
                        template = InspectionTemplate.objects.get(id=q.filter_value)
                        filter_value_display = f"{template.template_code} - {template.template_name}"
                    except:
                        filter_value_display = q.filter_value
                
                elif q.filter_field == 'inspection_type':
                    # Map inspection type codes to display names
                    from apps.inspections.models import InspectionTemplate
                    inspection_type_map = dict(InspectionTemplate.INSPECTION_TYPE_CHOICES)
                    filter_value_display = inspection_type_map.get(q.filter_value, q.filter_value)
                
                elif q.filter_field == 'assigned_to':
                    try:
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        user = User.objects.get(id=q.filter_value)
                        filter_value_display = user.get_full_name()
                    except:
                        filter_value_display = q.filter_value
                # ========================================
                # ⬆️ END OF INSPECTION SECTION
                # ========================================
                
                elif q.filter_field == 'status':
                    # Map status codes to display names
                    status_map = {
                        'REPORTED': 'Reported',
                        'UNDER_INVESTIGATION': 'Under Investigation',
                        'ACTION_IN_PROGRESS': 'Action In Progress',
                        'COMPLETED': 'Completed',
                        'CLOSED': 'Closed',
                        'OPEN': 'Open',
                        'IN_PROGRESS': 'In Progress',
                        'RESOLVED': 'Resolved',
                        'SCHEDULED': 'Scheduled',  # ⬅️ ADD THIS
                        'OVERDUE': 'Overdue',      # ⬅️ ADD THIS
                        'CANCELLED': 'Cancelled',  # ⬅️ ADD THIS
                    }
                    filter_value_display = status_map.get(q.filter_value, q.filter_value)
                
                elif q.filter_field == 'severity':
                    severity_map = {
                        'LOW': 'Low',
                        'MEDIUM': 'Medium',
                        'HIGH': 'High',
                        'CRITICAL': 'Critical',
                    }
                    filter_value_display = severity_map.get(q.filter_value, q.filter_value)
                
                elif q.filter_field == 'plant':
                    try:
                        plant = Plant.objects.get(id=q.filter_value)
                        filter_value_display = plant.name
                    except Plant.DoesNotExist:
                        filter_value_display = q.filter_value
                
                else:
                    filter_value_display = q.filter_value
                
                filter_desc = f"{filter_field_name} = {filter_value_display}"
                
                # ✅ Secondary filter (same logic)
                if q.filter_field_2 and q.filter_value_2:
                    filter_field_2_name = q.get_filter_field_2_display() if hasattr(q, 'get_filter_field_2_display') else q.filter_field_2
                    
                    if q.filter_field_2 == 'incident_type':
                        try:
                            incident_type_2 = IncidentType.objects.get(id=q.filter_value_2)
                            filter_value_2_display = f"{incident_type_2.code} - {incident_type_2.name}"
                        except IncidentType.DoesNotExist:
                            filter_value_2_display = q.filter_value_2
                    
                    elif q.filter_field_2 == 'hazard_type':
                        try:
                            from apps.hazards.models import HazardType
                            hazard_type_2 = HazardType.objects.get(id=q.filter_value_2)
                            filter_value_2_display = f"{hazard_type_2.code} - {hazard_type_2.name}"
                        except:
                            filter_value_2_display = q.filter_value_2
                    
                    # ========================================
                    # ⬇️ ADD THIS FOR SECONDARY INSPECTION FILTER
                    # ========================================
                    elif q.filter_field_2 == 'template':
                        try:
                            from apps.inspections.models import InspectionTemplate
                            template_2 = InspectionTemplate.objects.get(id=q.filter_value_2)
                            filter_value_2_display = f"{template_2.template_code} - {template_2.template_name}"
                        except:
                            filter_value_2_display = q.filter_value_2
                    
                    elif q.filter_field_2 == 'inspection_type':
                        from apps.inspections.models import InspectionTemplate
                        inspection_type_map = dict(InspectionTemplate.INSPECTION_TYPE_CHOICES)
                        filter_value_2_display = inspection_type_map.get(q.filter_value_2, q.filter_value_2)
                    
                    elif q.filter_field_2 == 'assigned_to':
                        try:
                            from django.contrib.auth import get_user_model
                            User = get_user_model()
                            user_2 = User.objects.get(id=q.filter_value_2)
                            filter_value_2_display = user_2.get_full_name()
                        except:
                            filter_value_2_display = q.filter_value_2
                    # ========================================
                    # ⬆️ END OF SECONDARY INSPECTION FILTER
                    # ========================================
                    
                    elif q.filter_field_2 == 'status':
                        status_map = {
                            'REPORTED': 'Reported',
                            'UNDER_INVESTIGATION': 'Under Investigation',
                            'ACTION_IN_PROGRESS': 'Action In Progress',
                            'COMPLETED': 'Completed',
                            'CLOSED': 'Closed',
                            'OPEN': 'Open',
                            'IN_PROGRESS': 'In Progress',
                            'RESOLVED': 'Resolved',
                            'SCHEDULED': 'Scheduled',
                            'OVERDUE': 'Overdue',
                            'CANCELLED': 'Cancelled',
                        }
                        filter_value_2_display = status_map.get(q.filter_value_2, q.filter_value_2)
                    
                    elif q.filter_field_2 == 'severity':
                        severity_map = {
                            'LOW': 'Low',
                            'MEDIUM': 'Medium',
                            'HIGH': 'High',
                            'CRITICAL': 'Critical',
                        }
                        filter_value_2_display = severity_map.get(q.filter_value_2, q.filter_value_2)
                    
                    elif q.filter_field_2 == 'plant':
                        try:
                            plant_2 = Plant.objects.get(id=q.filter_value_2)
                            filter_value_2_display = plant_2.name
                        except Plant.DoesNotExist:
                            filter_value_2_display = q.filter_value_2
                    
                    else:
                        filter_value_2_display = q.filter_value_2
                    
                    filter_desc += f" AND {filter_field_2_name} = {filter_value_2_display}"
            
            questions_list.append({
                "id": q.id,
                "question": q.question_text,
                "category_id": q.unit_category.id if q.unit_category else None,
                "category_name": q.unit_category.name if q.unit_category else "Not Set",
                "default_unit_id": q.default_unit.id if q.default_unit else None,
                "default_unit_name": q.default_unit.name if q.default_unit else "Count",
                "selected_unit_ids": [u.id for u in selected_units],
                "selected_unit_names": [u.name for u in selected_units],
                "order": q.order,
                "source_type": q.source_type,
                "filter_description": filter_desc,
            })
        return questions_list

    def add_question(self, request):
        # Yeh function aapke existing code jaisa hi rahega
        question_text = (request.POST.get("question_text") or "").strip()
        category_id = request.POST.get("category_id")
        default_unit_id = request.POST.get("default_unit_id")
        selected_unit_ids = request.POST.getlist("selected_unit_ids[]")
        source_type = request.POST.get("source_type", "MANUAL")
        
        # Dynamic filter fields
        filter_field = (request.POST.get("filter_field") or "").strip()
        filter_value = (request.POST.get("filter_value") or "").strip()
        filter_field_2 = (request.POST.get("filter_field_2") or "").strip()
        filter_value_2 = (request.POST.get("filter_value_2") or "").strip()
        
        # Validation
        if not question_text:
            messages.error(request, "Question text is required")
            return redirect("environmental:questions-manager")

        # Prevent duplicate questions
        if EnvironmentalQuestion.objects.filter(question_text__iexact=question_text, is_active=True).exists():
            messages.error(request, "This question already exists")
            return redirect("environmental:questions-manager")

        # For auto-calculated questions
        if source_type != 'MANUAL':
            if not filter_field or not filter_value:
                messages.error(request, "Primary filter field and value are required")
                return redirect("environmental:questions-manager")

            from apps.ENVdata.models import UnitCategory, Unit

            count_category = UnitCategory.objects.filter(name__iexact="Count").first()
            count_unit = Unit.objects.filter(name__iexact="Count").first()

            if not count_category or not count_unit:
                messages.error(request, "Count category or unit not configured.")
                return redirect("environmental:questions-manager")

            category_id = count_category.id
            default_unit_id = count_unit.id
            selected_unit_ids = [count_unit.id]

        else:
            # Manual entry requires units
            if not category_id or not default_unit_id or not selected_unit_ids:
                messages.error(request, "Category and units are required for manual entry questions")
                return redirect(f"environmental:questions-manager?category_id={category_id}")
            
            if default_unit_id not in selected_unit_ids:
                messages.error(request, "Default unit must be one of the selected units")
                return redirect(f"environmental:questions-manager?category_id={category_id}")

        # Create question
        max_order = EnvironmentalQuestion.objects.aggregate(
            max=models.Max("order")
        )["max"] or 0

        question = EnvironmentalQuestion.objects.create(
            question_text=question_text,
            unit_category_id=category_id if category_id else None,
            default_unit_id=default_unit_id if default_unit_id else None,
            source_type=source_type,
            filter_field=filter_field if filter_field else None,
            filter_value=filter_value if filter_value else None,
            filter_field_2=filter_field_2 if filter_field_2 else None,
            filter_value_2=filter_value_2 if filter_value_2 else None,
            order=max_order + 1,
            created_by=request.user,
            is_active=True,
            is_system=False,
        )
        
        selected_unit_ids = request.POST.getlist("selected_unit_ids[]")
        if selected_unit_ids:
            question.selected_units.set(selected_unit_ids)

        messages.success(request, f"✓ Question '{question_text}' added successfully!")
        return redirect("environmental:questions-manager")

    def update_question(self, request, question_id):
        """
        Handles the logic to update an existing question.
        """
        # Fetch the question to be updated
        question = get_object_or_404(EnvironmentalQuestion, id=question_id)

        # Non-editable for system-defined questions
        if question.is_system:
            messages.error(request, "Predefined questions cannot be edited.")
            return redirect("environmental:questions-manager")

        # Get data from the form
        question_text = (request.POST.get("question_text") or "").strip()
        category_id = request.POST.get("category_id")
        default_unit_id = request.POST.get("default_unit_id")
        selected_unit_ids = request.POST.getlist("selected_unit_ids[]")
        source_type = request.POST.get("source_type", "MANUAL")
        
        # Validation
        if not question_text:
            messages.error(request, "Question text cannot be empty.")
            return redirect("environmental:questions-manager-edit", question_id=question.id)

        # Check if another question with the same text already exists
        if EnvironmentalQuestion.objects.filter(question_text__iexact=question_text, is_active=True).exclude(id=question.id).exists():
            messages.error(request, "Another question with this text already exists.")
            return redirect("environmental:questions-manager-edit", question_id=question.id)

        # Update the question object with new values
        question.question_text = question_text
        question.unit_category_id = category_id if category_id else None
        question.default_unit_id = default_unit_id if default_unit_id else None
        question.source_type = source_type
        # ... (Update other fields like filter_field, etc. as needed)
        
        # Save the changes to the database
        question.save()

        # Update the many-to-many relationship for selected units
        if selected_unit_ids:
            question.selected_units.set(selected_unit_ids)
        else:
            # If no units are selected, clear the existing ones
            question.selected_units.clear()

        messages.success(request, f"✓ Question '{question.question_text}' updated successfully!")
        return redirect("environmental:questions-manager")

    def delete_question(self, request):
        """
        Handles the logic to PERMANENTLY delete a question from the database.
        """
        question_id = request.POST.get("question_id")
        
        # Use get_object_or_404 to safely retrieve the question
        question = get_object_or_404(EnvironmentalQuestion, id=question_id)

        # Prevent deletion of system-defined questions (this check is still important)
        if question.is_system:
            messages.error(request, "Predefined questions cannot be deleted.")
            return redirect("environmental:questions-manager")

        # --- THIS IS THE ONLY CHANGE ---
        # Instead of soft-deleting, we will now permanently delete.
        
        # Store the question text for the success message before deleting the object
        question_name = question.question_text
        
        # This command permanently removes the question from the database.
        question.delete()

        messages.success(request, f"✓ Question '{question_name}' has been permanently deleted.")
        return redirect("environmental:questions-manager")

# =========================================================
# API ENDPOINTS
# =========================================================

class GetCategoryUnitsAPIView(LoginRequiredMixin, View):
    """
    API endpoint to fetch units for a selected category
    """
    def get(self, request):
        category_id = request.GET.get('category_id')
        
        if not category_id:
            return JsonResponse({
                'success': False,
                'error': 'Category ID is required'
            }, status=400)
        
        try:
            units = Unit.objects.filter(
                category_id=category_id,
                is_active=True
            ).values('id', 'name', 'base_unit', 'conversion_rate').order_by('name')
            
            return JsonResponse({
                'success': True,
                'units': list(units)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


# class GetSourceFieldsAPIView(LoginRequiredMixin, View):
#     """
#     API to get available fields and their choices for a source type
#     """
#     def get(self, request):
#         source_type = request.GET.get('source_type')
        
#         if not source_type:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Source type is required'
#             }, status=400)
        
#         try:
#             from apps.accidents.models import Incident
#             from apps.hazards.models import Hazard
            
#             # Get model based on source type
#             if source_type == 'INCIDENT':
#                 model = Incident
#             elif source_type == 'HAZARD':
#                 model = Hazard
#             else:
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Invalid source type'
#                 }, status=400)
            
#             # Get fields with choices
#             fields_with_choices = []
            
#             for field in model._meta.get_fields():
#                 if hasattr(field, 'choices') and field.choices:
#                     choices = [{'value': choice[0], 'display': choice[1]} for choice in field.choices]
#                     fields_with_choices.append({
#                         'field_name': field.name,
#                         'field_verbose_name': field.verbose_name.title(),
#                         'choices': choices
#                     })
            
#             return JsonResponse({
#                 'success': True,
#                 'fields': fields_with_choices
#             })
            
#         except Exception as e:
#             return JsonResponse({
#                 'success': False,
#                 'error': str(e)
#             }, status=500)
        

# =========================================================
# VIEW SUBMITTED DATA - USER VIEW (Read-only)
# =========================================================
from decimal import Decimal

class PlantDataDisplayView(LoginRequiredMixin, View):
    template_name = "data_collection/data_display.html"

    def get_user_plants(self, request):
        """Get all plants assigned to the user"""
        user = request.user
        
        if user.is_superuser or user.is_staff or getattr(user, 'is_admin_user', False):
            return Plant.objects.filter(is_active=True)
        
        assigned = user.assigned_plants.filter(is_active=True)
        
        if not assigned.exists() and getattr(user, 'plant', None):
            return Plant.objects.filter(id=user.plant.id, is_active=True)
        
        return assigned

    def get(self, request):
        plant_id = request.GET.get('plant_id')
        user_plants = self.get_user_plants(request)
        
        plant = user_plants.filter(id=plant_id).first() if plant_id else user_plants.first()
        
        if not plant:
            return render(request, "no_plant_assigned.html")

        report_data = build_environmental_report([plant], include_attachments=True)
        questions_data = []
        for row in report_data["plants_data"][0]["questions_data"]:
            questions_data.append({
                "question": row["question"],
                "unit": row["unit"],
                "month_values": [row["month_data"][month["label"]] for month in report_data["months"]],
                "annual": row["annual"],
            })

        return render(request, self.template_name, {
            "plant": plant,
            "user_plants": user_plants,
            "questions_data": questions_data,
            "months": [(month["code"], month["label"]) for month in report_data["months"]],
        })

# =========================================================
# ADMIN VIEW - ALL PLANTS DATA
# =========================================================

from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator

class AdminAllPlantsDataView(LoginRequiredMixin, View):
    template_name = "data_collection/admin_all_plants.html"

    def get(self, request):
        if not (request.user.is_superuser or request.user.is_staff or getattr(request.user, 'is_admin_user', False)):
            messages.error(request, "You don't have permission to access this page")
            return redirect("environmental:plant-entry")

        all_plants = Plant.objects.filter(is_active=True).order_by("name")

        if not all_plants.exists():
            return render(request, self.template_name, {"no_plants": True})

        questions = get_environmental_questions()
        if not questions:
            return render(request, self.template_name, {"no_questions": True})

        selected_plant_ids = request.GET.getlist("plant_ids")
        selected_month = request.GET.get("month", "all")
        selected_fy = request.GET.get("financial_year") or get_financial_year_label(get_financial_year_start_year())
        all_months = get_financial_year_months(selected_fy)

        selected_plants = list(all_plants.filter(id__in=selected_plant_ids)) if selected_plant_ids else list(all_plants)
        if not selected_plants:
            selected_plants = list(all_plants)

        aggregate_view = len(selected_plants) != 1
        report_data = build_environmental_report(
            plants=selected_plants,
            fy_start_year=selected_fy,
            selected_month=selected_month,
            aggregate=aggregate_view,
            include_attachments=not aggregate_view,
        )

        return render(request, self.template_name, {
            "all_plants": all_plants,
            "selected_plant_ids": [str(plant.id) for plant in selected_plants],
            "selected_month": selected_month,
            "selected_financial_year": selected_fy,
            "financial_year_options": get_financial_year_options(),
            "all_months": all_months,
            "months": report_data["months"],
            "questions_data": report_data["questions_data"] if aggregate_view else report_data["plants_data"][0]["questions_data"],
            "display_title": "Combined Total" if aggregate_view else selected_plants[0].name,
            "selected_plants": selected_plants,
            "total_plants": all_plants.count(),
            "selected_plants_count": len(selected_plants),
            "total_questions": len(questions),
        })

    
class GetCategoryBaseUnitAPIView(LoginRequiredMixin, View):
    """
    API endpoint to fetch the established base unit for a category.
    """
    def get(self, request):
        category_id = request.GET.get('category_id')
        if not category_id:
            return JsonResponse({
                'success': False, 
                'error': 'Category ID is required'
            }, status=400)
        
        try:
            # Find the first unit in this category to determine the base unit
            first_unit = Unit.objects.filter(category_id=category_id, is_active=True).first()
            
            # If a unit exists, return its base unit. Otherwise, return an empty string.
            base_unit = first_unit.base_unit if first_unit else ""
            
            return JsonResponse({
                'success': True,
                'base_unit': base_unit
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


from calendar import month_name
class EnvironmentalDashboardView(LoginRequiredMixin, TemplateView):
    """
    Environmental Dashboard with strict access control and dynamic filtering.
    Admins see all data, while users see only assigned plant data.
    """
    template_name = 'data_collection/env_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # --- 1. USER ACCESS CONTROL (Plants logic) ---
        if user.is_superuser or user.is_staff or getattr(user, 'is_admin_user', False):
            # Admin can see everything
            accessible_plants = Plant.objects.filter(is_active=True).order_by('name')
        else:
            # HOD/Employee sees only assigned plants
            # Note: Using the same logic as your PlantMonthlyEntryView
            assigned = user.assigned_plants.filter(is_active=True)
            if not assigned.exists() and getattr(user, 'plant', None):
                accessible_plants = Plant.objects.filter(id=user.plant.id, is_active=True)
            else:
                accessible_plants = assigned.order_by('name')

        # --- 2. EXTRACT FILTERS ---
        selected_plant_id = self.request.GET.get('plant')
        selected_month_code = self.request.GET.get('month')
        if selected_plant_id:
            accessible_plants = accessible_plants.filter(id=selected_plant_id)        
        questions = EnvironmentalQuestion.objects.filter(is_active=True)

        # --- 3. BASE DATA QUERYSET (Filter by accessible plants first) ---
        # Optimization: select_related to avoid N+1 queries on SQLite
        data_qs = []
        current_year = datetime.now().year
        # month_choices = MonthlyIndicatorData.MONTH_CHOICES

        today = datetime.now()
        # FY start year
        if today.month < 4:
            fy_start_year = today.year - 1
        else:
            fy_start_year = today.year

        FY_MONTH_ORDER = [
            "APR", "MAY", "JUN", "JUL", "AUG", "SEP",
            "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"
        ]

        month_choices = []

        for m in FY_MONTH_ORDER:
            month_num = datetime.strptime(m, "%b").month

            # Jan–Mar → next year
            if m in ["JAN", "FEB", "MAR"]:
                year = fy_start_year + 1
            else:
                year = fy_start_year

            label = f"{month_name[month_num]} {year}"  
            month_choices.append((m, label))

        updated_at = None
        for plant in accessible_plants:
            for q in questions:
                for month_code, month_label in month_choices:

                    # Apply user-selected filters
                    if selected_month_code and month_code != selected_month_code:
                        continue
                    value = None
                    if q.source_type == "MANUAL":
                        manual_entry = MonthlyIndicatorData.objects.filter(
                            plant=plant,
                            indicator=q,
                            month=month_code
                        ).first()

                        if manual_entry:
                            value = manual_entry.value
                            updated_at = manual_entry.updated_at
                        else:
                            updated_at = None

                    else:
                        month_number = datetime.strptime(month_code, "%b").month

                        start_date = datetime(current_year, month_number, 1)

                        if month_number == 12:
                            end_date = datetime(current_year + 1, 1, 1)
                        else:
                            end_date = datetime(current_year, month_number + 1, 1)

                        model_map = {"INCIDENT": (Incident, "plant"),"HAZARD": (Hazard, "plant"),"INSPECTION": (InspectionSchedule, "plants")}

                        model_tuple = model_map.get(q.source_type)

                        if model_tuple:
                            model, plant_field = model_tuple
                            filters = {f"{plant_field}": plant,"created_at__gte": start_date,"created_at__lt": end_date,}

                            if q.filter_field and q.filter_value:
                                field = q.filter_field
                                if q.source_type == "INSPECTION":
                                    if field == "inspection_type":
                                        field = "template__inspection_type"
                                    elif field == "template":
                                        field = "template_id"
                                filters[field] = q.filter_value

                            if q.filter_field_2 and q.filter_value_2:
                                field = q.filter_field_2
                                if q.source_type == "INSPECTION":
                                    if field == "inspection_type":
                                        field = "template__inspection_type"
                                    elif field == "template":
                                        field = "template_id"
                                filters[field] = q.filter_value_2

                            value = model.objects.filter(**filters).count()

                    if value not in [None, "", 0]:
                        data_qs.append({"plant": plant,"indicator": q,"month": month_code,"value": value,"updated_at":updated_at,"category": q.unit_category.name if q.unit_category else "Other"})


        # --- 4. CALCULATE STATISTICS (Based on Filtered Data) ---
        context['total_indicators_count'] = questions.count()
        context['total_data_points'] = len(data_qs)
        context['plants_count'] = accessible_plants.count()
        
        # Sum of numeric values (Safe conversion for SQLite)
        total_vol = 0
        for entry in data_qs:
            try:
                total_vol += float(entry["value"])
            except (ValueError, TypeError):
                continue
        context['total_volume'] = total_vol

        # --- 5. PREPARE CHARTS (JSON format) ---
        # Category Chart
        cat_counter = Counter([e["category"] for e in data_qs])
        context['cat_labels_json'] = json.dumps(list(cat_counter.keys()))
        context['cat_data_json'] = json.dumps(list(cat_counter.values()))

        # --- 6. DATA TABLE (Show ALL filtered data) ---
        # context['data_entries'] = sorted(data_qs,key=lambda x: (x["plant"].name, x["indicator"].order))
        # month_order = [m[0] for m in month_choices]
        # trend_counter = Counter([e["month"] for e in data_qs])
        # context['trend_labels_json'] = json.dumps([dict(month_choices).get(m) for m in month_order])
        # context['trend_values_json'] = json.dumps([trend_counter.get(m, 0) for m in month_order])
        context['data_entries'] = sorted(data_qs,key=lambda x: (x["plant"].name, x["indicator"].order))
        # --- Trend Chart (FY Order) ---
        FY_MONTH_ORDER = [
            "APR", "MAY", "JUN", "JUL", "AUG", "SEP",
            "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"
        ]
        trend_counter = Counter([e["month"] for e in data_qs])
        context['trend_labels_json'] = json.dumps([dict(month_choices).get(m) for m in FY_MONTH_ORDER])
        context['trend_values_json'] = json.dumps([trend_counter.get(m, 0) for m in FY_MONTH_ORDER])

        # --- 7. FILTER OPTIONS ---
        # context['plants'] = Plant.objects.filter(is_active=True)
        context['plants'] = accessible_plants 
        context['month_choices'] = month_choices
        context['selected_plant'] = selected_plant_id
        context['selected_month'] = selected_month_code
        context['has_active_filters'] = bool(selected_plant_id or selected_month_code)
        print("context=========",context)
        return context
        
class ExportExcelView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user

        if user.is_superuser or user.is_staff or user.is_admin_user:
            plants = Plant.objects.filter(is_active=True)

        else:
            plants = user.get_all_plants()

            if not plants:
                messages.error(request, "No plant is assigned to your account")
                return redirect("environmental:plant-entry")

            plants = Plant.objects.filter(
                id__in=[p.id for p in plants],
                is_active=True
            )

        selected_plant_ids = request.GET.getlist("plant_ids")
        selected_month = request.GET.get("month", "all")
        selected_fy = request.GET.get("financial_year") or get_financial_year_label(get_financial_year_start_year())

        if selected_plant_ids:
            plants = plants.filter(id__in=selected_plant_ids)

        selected_plants = list(plants.order_by("name"))
        if not selected_plants:
            messages.error(request, "No matching plants found for export")
            return redirect("environmental:admin-all-plants")

        aggregate_view = len(selected_plants) != 1
        report_data = build_environmental_report(
            plants=selected_plants,
            fy_start_year=selected_fy,
            selected_month=selected_month,
            aggregate=aggregate_view,
            include_attachments=False,
        )

        if not aggregate_view:
            report_data = {
                "months": report_data["months"],
                "questions_data": report_data["plants_data"][0]["questions_data"],
            }

        title = (
            f"Environmental Data - {selected_plants[0].name}"
            if len(selected_plants) == 1 else
            f"Environmental Data - Combined Total ({len(selected_plants)} Plants)"
        )

        workbook = generate_environmental_excel(report_data, title=title)

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"Monthly_Indicators_Data_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        workbook.save(response)
        return response
    

import os 


class UploadAttachmentView(LoginRequiredMixin, View):
    """
    Handles file upload for a specific plant + indicator + month cell.
    If attachment already exists for that cell, it replaces it.
    """
    def post(self, request):
        plant_id     = request.POST.get('plant_id')
        indicator_id = request.POST.get('indicator_id')
        month        = request.POST.get('month')
        upload_file  = request.FILES.get('attachment_file')

        if not all([plant_id, indicator_id, month, upload_file]):
            messages.error(request, "Missing required fields for attachment upload.")
            return redirect(f"{request.META.get('HTTP_REFERER', '/')}") 

        try:
            plant     = Plant.objects.get(id=plant_id)
            indicator = EnvironmentalQuestion.objects.get(id=indicator_id)
        except (Plant.DoesNotExist, EnvironmentalQuestion.DoesNotExist):
            messages.error(request, "Invalid plant or indicator.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        # If attachment already exists for this cell, delete old file and replace
        existing = MonthlyIndicatorAttachment.objects.filter(
            plant=plant,
            indicator=indicator,
            month=month
        ).first()

        if existing:
            # Delete old file from storage
            if existing.file:
                if os.path.isfile(existing.file.path):
                    os.remove(existing.file.path)
            existing.delete()

        # Save new attachment
        original_name = upload_file.name
        attachment = MonthlyIndicatorAttachment.objects.create(
            plant=plant,
            indicator=indicator,
            month=month,
            file=upload_file,
            file_name=original_name,
            uploaded_by=request.user,
        )

        messages.success(request, f"✓ File '{original_name}' attached successfully!")
        return redirect(request.META.get('HTTP_REFERER', '/'))


class DownloadAttachmentView(LoginRequiredMixin, View):
    """
    Serves the attached file for download/view.
    """
    def get(self, request, attachment_id):
        try:
            attachment = MonthlyIndicatorAttachment.objects.get(id=attachment_id)
        except MonthlyIndicatorAttachment.DoesNotExist:
            raise Http404("Attachment not found.")

        if not attachment.file or not os.path.isfile(attachment.file.path):
            raise Http404("File not found on server.")

        response = FileResponse(
            open(attachment.file.path, 'rb'),
            as_attachment=False,  # Opens in browser if possible
            filename=attachment.file_name or os.path.basename(attachment.file.name)
        )
        return response


class DeleteAttachmentView(LoginRequiredMixin, View):
    """
    Deletes an attachment and removes the file from storage.
    """
    def get(self, request, attachment_id):
        try:
            attachment = MonthlyIndicatorAttachment.objects.get(id=attachment_id)
        except MonthlyIndicatorAttachment.DoesNotExist:
            messages.error(request, "Attachment not found.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        # Delete file from disk
        if attachment.file and os.path.isfile(attachment.file.path):
            os.remove(attachment.file.path)

        file_name = attachment.file_name
        attachment.delete()

        messages.success(request, f"✓ Attachment '{file_name}' removed successfully.")
        return redirect(request.META.get('HTTP_REFERER', '/'))


