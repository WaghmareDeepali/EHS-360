# apps/inspections/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Prefetch, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.core.paginator import EmptyPage, Paginator
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.views import View
from django.views.generic import TemplateView
from django.db.models import Count, Avg

from datetime import timedelta, datetime

from django.core.paginator import Paginator
import json
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import *
from .forms import *
from .utils import generate_inspection_pdf
from apps.notifications.services import NotificationService
from apps.organizations.models import Plant, Zone, Location, SubLocation, Department



# ====================================
# DASHBOARD
# ====================================


def _build_scope_queryset(schedule_queryset, user_queryset, primary_id=None, child_model=None, child_filter=None):
    if schedule_queryset.exists():
        return schedule_queryset
    if user_queryset.exists():
        return user_queryset
    if primary_id:
        return child_model.objects.filter(pk=primary_id)
    if child_model and child_filter:
        return child_model.objects.filter(**child_filter)
    return child_model.objects.none() if child_model else schedule_queryset.none()


def _get_inspection_scope(schedule, user=None):
    plants = schedule.plants.filter(is_active=True).order_by('name').distinct()
    user_plant_ids = []

    if user is not None:
        user_plant_ids = [plant.id for plant in user.get_all_plants() if getattr(plant, 'is_active', True)]
        if user_plant_ids:
            plants = plants.filter(id__in=user_plant_ids)

    zones = schedule.zones.filter(is_active=True)
    if not zones.exists() and plants.exists():
        zones = Zone.objects.filter(plant__in=plants, is_active=True)
    zones = zones.order_by('name').distinct()

    locations = schedule.locations.filter(is_active=True)
    if not locations.exists() and zones.exists():
        locations = Location.objects.filter(zone__in=zones, is_active=True)
    locations = locations.order_by('name').distinct()

    sublocations = schedule.sublocations.filter(is_active=True)
    if not sublocations.exists() and locations.exists():
        sublocations = SubLocation.objects.filter(location__in=locations, is_active=True)
    sublocations = sublocations.order_by('name').distinct()

    return {
        'plants': plants,
        'zones': zones,
        'locations': locations,
        'sublocations': sublocations,
    }


def _clone_schedule_as_scheduled(source_schedule, assignment_notes=None):
    """
    Create a fresh schedule record by copying the source schedule's data while
    resetting lifecycle fields so the new record stays scheduled.
    """
    plants = list(source_schedule.plants.all())
    zones = list(source_schedule.zones.all())
    locations = list(source_schedule.locations.all())
    sublocations = list(source_schedule.sublocations.all())
    assigned_users = list(source_schedule.assigned_users.all())

    new_schedule = InspectionSchedule.objects.get(pk=source_schedule.pk)
    new_schedule.pk = None
    new_schedule.id = None
    new_schedule.schedule_code = None
    new_schedule.status = 'SCHEDULED'
    new_schedule.started_at = None
    new_schedule.closed_at = None
    new_schedule.reminder_sent = False
    new_schedule.reminder_sent_at = None

    today = timezone.now().date()
    due_offset = max((source_schedule.due_date - source_schedule.scheduled_date).days, 0)
    new_schedule.scheduled_date = today
    new_schedule.due_date = today + timedelta(days=due_offset)

    if source_schedule.scheduled_end_date:
        end_offset = max(
            (source_schedule.scheduled_end_date - source_schedule.scheduled_date).days,
            due_offset,
        )
        new_schedule.scheduled_end_date = today + timedelta(days=end_offset)

    if assignment_notes is not None:
        new_schedule.assignment_notes = assignment_notes

    # Save first so M2M fields can be restored on the new schedule instance.
    new_schedule.save()

    if new_schedule.status != 'SCHEDULED':
        InspectionSchedule.objects.filter(pk=new_schedule.pk).update(status='SCHEDULED')
        new_schedule.status = 'SCHEDULED'

    new_schedule.plants.set(plants)
    new_schedule.zones.set(zones)
    new_schedule.locations.set(locations)
    new_schedule.sublocations.set(sublocations)
    new_schedule.assigned_users.set(assigned_users)
    return new_schedule

# @login_required
# def inspection_dashboard(request):
#     """Main inspection dashboard"""
    
#     context = {
#         'total_categories': InspectionCategory.objects.filter(is_active=True).count(),
#         'total_questions': InspectionQuestion.objects.filter(is_active=True).count(),
#         'total_templates': InspectionTemplate.objects.filter(is_active=True).count(),
#         'total_schedules': InspectionSchedule.objects.count(),
        
#         # Recent data
#         'recent_categories': InspectionCategory.objects.filter(is_active=True)[:5],
#         'recent_questions': InspectionQuestion.objects.filter(is_active=True)[:10],
#         'recent_schedules': InspectionSchedule.objects.select_related(
#             'template', 'assigned_to', 'plant'
#         )[:10],
#     }
    
#     # User-specific data
#     if request.user.can_access_inspection_module or request.user.is_superuser:
#         if request.user.has_permission('VIEW_INSPECTION'):
#             # HOD sees their assigned inspections
#             context['my_pending_inspections'] = InspectionSchedule.objects.filter(
#                 assigned_to=request.user,
#                 status__in=['SCHEDULED', 'IN_PROGRESS']
#             ).count()
#             context['my_overdue_inspections'] = InspectionSchedule.objects.filter(
#                 assigned_to=request.user,
#                 status='OVERDUE'
#             ).count()
        
#         elif request.user.can_access_inspection_module or request.user.is_superuser or request.user.is_admin:
#             # Safety manager sees all for their plant
#             context['pending_schedules'] = InspectionSchedule.objects.filter(
#                 status__in=['SCHEDULED', 'IN_PROGRESS']
#             ).count()
#             context['overdue_schedules'] = InspectionSchedule.objects.filter(
#                 status='OVERDUE'
#             ).count()
    
#     return render(request, 'inspections/dashboard.html', context)


# ====================================
# CATEGORY VIEWS
# ====================================

@login_required
def category_list(request):
    """List all inspection categories"""
    
    categories = InspectionCategory.objects.annotate(
        questions_count=Count('questions', filter=Q(questions__is_active=True))
    ).order_by('category_name') #removed 'display_order',
    
    # Filter
    search = request.GET.get('search')
    if search:
        categories = categories.filter(
            Q(category_name__icontains=search) |
            Q(category_code__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(categories, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search
    }
    return render(request, 'inspections/category_list.html', context)


@login_required
def category_create(request):
    """Create new inspection category"""
    
    if request.method == 'POST':
        form = InspectionCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.created_by = request.user
            category.save()
            messages.success(request, f'Category "{category.category_name}" created successfully!')
            return redirect('inspections:category_list')
    else:
        form = InspectionCategoryForm()
    
    context = {
        'form': form,
        'action': 'Create',
        'title': 'Create New Category'
    }
    return render(request, 'inspections/category_form.html', context)


@login_required
def category_edit(request, pk):
    """Edit existing category"""
    
    category = get_object_or_404(InspectionCategory, pk=pk)
    
    if request.method == 'POST':
        form = InspectionCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.category_name}" updated successfully!')
            return redirect('inspections:category_list')
    else:
        form = InspectionCategoryForm(instance=category)
    
    context = {
        'form': form,
        'action': 'Edit',
        'title': f'Edit Category: {category.category_name}',
        'category': category
    }
    return render(request, 'inspections/category_form.html', context)


@login_required
def category_delete(request, pk):
    """Permanently delete category"""
    category = get_object_or_404(InspectionCategory, pk=pk)
    
    if request.method == 'POST':
        category.delete()
        messages.success(request, f'Category "{category.category_name}" deleted successfully!')
        return redirect('inspections:category_list')
    
    context = {
        'category': category,
        'questions_count': category.questions.filter(is_active=True).count()
    }
    return render(request, 'inspections/category_confirm_delete.html', context)


# ====================================
# QUESTION VIEWS
# ====================================

@login_required
def question_list(request):
    """List all inspection questions with filters"""
    
    questions = InspectionQuestion.objects.select_related('category').filter(is_active=True)
    
    # Apply filters
    filter_form = QuestionFilterForm(request.GET)
    
    if filter_form.is_valid():
        category = filter_form.cleaned_data.get('category')
        question_type = filter_form.cleaned_data.get('question_type')
        is_critical = filter_form.cleaned_data.get('is_critical')
        search = filter_form.cleaned_data.get('search')
        
        if category:
            questions = questions.filter(category=category)
        
        if question_type:
            questions = questions.filter(question_type=question_type)
        
        if is_critical is not None:
            questions = questions.filter(is_critical=is_critical)
        
        if search:
            questions = questions.filter(
                Q(question_text__icontains=search) |
                Q(question_code__icontains=search) |
                Q(reference_standard__icontains=search)
            )
    
    questions = questions.order_by('category') #removed , 'display_order'
    
    # Pagination
    paginator = Paginator(questions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_questions': questions.count()
    }
    return render(request, 'inspections/question_list.html', context)


@login_required
def question_create(request):
    """Create new inspection question"""
    
    if request.method == 'POST':
        form = InspectionQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.created_by = request.user
            question.save()
            messages.success(request, f'Question "{question.question_code}" created successfully!')
            
            # Redirect based on action
            if request.POST.get('action_type') == 'save_and_add':
                return redirect('inspections:question_create')
            return redirect('inspections:question_list')
    else:
        form = InspectionQuestionForm()
        
        # Pre-select category if provided
        category_id = request.GET.get('category')
        if category_id:
            form.initial['category'] = category_id
    
    context = {
        'form': form,
        'action': 'Create',
        'title': 'Create New Question'
    }
    return render(request, 'inspections/question_form.html', context)


@login_required
def question_edit(request, pk):
    """Edit existing question"""
    
    question = get_object_or_404(InspectionQuestion, pk=pk)
    
    if request.method == 'POST':
        form = InspectionQuestionForm(request.POST, instance=question)
        if form.is_valid():
            question = form.save(commit=False)
            question.updated_by = request.user
            question.save()
            messages.success(request, f'Question "{question.question_code}" updated successfully!')
            return redirect('inspections:question_list')
    else:
        form = InspectionQuestionForm(instance=question)
    
    context = {
        'form': form,
        'action': 'Edit',
        'title': f'Edit Question: {question.question_code}',
        'question': question
    }
    return render(request, 'inspections/question_form.html', context)


@login_required
def question_detail(request, pk):
    """View question details"""
    
    question = get_object_or_404(
        InspectionQuestion.objects.select_related('category', 'created_by'),
        pk=pk
    )
    
    # Get templates using this question
    templates = InspectionTemplate.objects.filter(
        template_questions__question=question,
        is_active=True
    ).distinct()
    
    context = {
        'question': question,
        'templates': templates
    }
    return render(request, 'inspections/question_detail.html', context)


@login_required
def question_delete(request, pk):
    """Soft delete question"""
    
    question = get_object_or_404(InspectionQuestion, pk=pk)
    
    if request.method == 'POST':
        question.is_active = False
        question.save()
        messages.success(request, f'Question "{question.question_code}" deleted successfully!')
        return redirect('inspections:question_list')
    
    context = {
        'question': question,
        'templates_count': InspectionTemplate.objects.filter(
            template_questions__question=question
        ).distinct().count()
    }
    return render(request, 'inspections/question_confirm_delete.html', context)


# apps/inspections/views.py (continued)

# ====================================
# TEMPLATE VIEWS
# ====================================

@login_required
def template_list(request):
    """List all inspection templates"""
    
    templates = InspectionTemplate.objects.annotate(
        questions_count=Count('template_questions', filter=Q(template_questions__question__is_active=True))
    ).prefetch_related('applicable_plants', 'applicable_departments')
    
    # Filters
    inspection_type = request.GET.get('inspection_type')
    plant_id = request.GET.get('plant')
    search = request.GET.get('search')
    
    if inspection_type:
        templates = templates.filter(inspection_type=inspection_type)
    
    if plant_id:
        templates = templates.filter(
            Q(applicable_plants__id=plant_id) | Q(applicable_plants__isnull=True)
        )
    
    if search:
        templates = templates.filter(
            Q(template_name__icontains=search) |
            Q(template_code__icontains=search) |
            Q(description__icontains=search)
        )
     
    templates = templates.distinct().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(templates, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # For filters
    from apps.organizations.models import Plant
    plants = Plant.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'inspection_types': InspectionTemplate.INSPECTION_TYPE_CHOICES,
        'plants': plants,
        'selected_type': inspection_type,
        'selected_plant': plant_id,
        'search': search
    }
    return render(request, 'inspections/template_list.html', context)


@login_required
def template_create(request):
    """Create new inspection template"""
    
    if request.method == 'POST':
        form = InspectionTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            template.save()
            form.save_m2m()  # Save many-to-many relationships
            messages.success(request, f'Template "{template.template_name}" created successfully!')
            return redirect('inspections:template_detail', pk=template.pk)
    else:
        form = InspectionTemplateForm()
    
    context = {
        'form': form,
        'action': 'Create',
        'title': 'Create New Inspection Template'
    }
    return render(request, 'inspections/template_form.html', context)


@login_required
def template_edit(request, pk):
    """Edit existing template"""
    
    template = get_object_or_404(InspectionTemplate, pk=pk)
    
    if request.method == 'POST':
        form = InspectionTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, f'Template "{template.template_name}" updated successfully!')
            return redirect('inspections:template_detail', pk=template.pk)
    else:
        form = InspectionTemplateForm(instance=template)
    
    context = {
        'form': form,
        'action': 'Edit',
        'title': f'Edit Template: {template.template_name}',
        'template': template
    }
    return render(request, 'inspections/template_form.html', context)

from collections import defaultdict

# apps/inspections/views.py

@login_required
def template_detail(request, pk):
    """View template details with all questions"""
    from collections import defaultdict
    
    template = get_object_or_404(InspectionTemplate, pk=pk)
    
    # Get all template questions with related data
    template_questions = TemplateQuestion.objects.filter(
        template=template
    ).select_related(
        'question',
        'question__category'
    ) #removed .order_by('display_order')
    
    # Group questions by category
    questions_by_category = defaultdict(list)
    for tq in template_questions:
        questions_by_category[tq.question.category].append(tq)
    
    # Convert to regular dict and sort by category display_order
    questions_by_category = dict(questions_by_category.items()) #removed sorted(,key=lambda x: x[0].display_order)
    
    # Get unique categories - FIXED VERSION
    # Extract category IDs from template questions
    category_ids = template_questions.values_list(
        'question__category_id', 
        flat=True
    ).distinct()
    
    # Get categories by IDs
    categories = InspectionCategory.objects.filter(
        id__in=category_ids
    ) #removed .order_by('display_order')
    
    # Count total questions
    total_questions = template_questions.count()
    
    context = {
        'template': template,
        'questions_by_category': questions_by_category,
        'categories': categories,
        'total_questions': total_questions,
        'auto_configs': TemplateAutoScheduleConfig.objects.filter(template=template).prefetch_related('plants', 'assigned_users'),
    }
    return render(request, 'inspections/template_detail.html', context)

@login_required
def template_delete(request, pk):
    """ Permanently delete template"""
    
    template = get_object_or_404(InspectionTemplate, pk=pk)
    
    if request.method == 'POST':
        template.delete()
        messages.success(request, f'Template "{template.template_name}" deleted successfully!')
        return redirect('inspections:template_list')
    
    context = {
        'template': template,
        'questions_count': template.get_total_questions(),
        'schedules_count': template.schedules.count()
    }
    return render(request, 'inspections/template_confirm_delete.html', context)


@login_required
def template_add_question(request, pk):
    """Add single question to template"""
    
    template = get_object_or_404(InspectionTemplate, pk=pk)
    
    if request.method == 'POST':
        form = TemplateQuestionForm(request.POST)
        if form.is_valid():
            template_question = form.save(commit=False)
            template_question.template = template
            
            # Check if question already exists
            if TemplateQuestion.objects.filter(
                template=template,
                question=template_question.question
            ).exists():
                messages.error(request, 'This question is already in the template!')
            else:
                template_question.save()
                messages.success(request, 'Question added to template successfully!')
            
            return redirect('inspections:template_detail', pk=template.pk)
    else:
        form = TemplateQuestionForm()
        
        # Exclude questions already in template
        existing_question_ids = template.template_questions.values_list('question_id', flat=True)
        form.fields['question'].queryset = InspectionQuestion.objects.filter(
            is_active=True
        ).exclude(id__in=existing_question_ids)
    
    context = {
        'form': form,
        'template': template,
        'title': f'Add Question to {template.template_name}'
    }
    return render(request, 'inspections/template_add_question.html', context)


@login_required
def template_bulk_add_questions(request, pk):
    """Bulk add questions to template"""
    
    template = get_object_or_404(InspectionTemplate, pk=pk)
    
    if request.method == 'POST':
        # Get selected question IDs from form
        question_ids = request.POST.getlist('questions')
        section_name = request.POST.get('section_name', '').strip()
        is_mandatory = request.POST.get('is_mandatory') == 'on'
        
        if not question_ids:
            messages.error(request, 'Please select at least one question!')
            return redirect('inspections:template_bulk_add_questions', pk=pk)
        
        # Get current max display order
        max_order = TemplateQuestion.objects.filter(
            template=template
        ) #.aggregate(max_order=models.Max('display_order'))['max_order'] or 0
        
        # Add selected questions
        added_count = 0
        for question_id in question_ids:
            try:
                question = InspectionQuestion.objects.get(pk=question_id, is_active=True)
                
                # Check if question already exists in template
                if TemplateQuestion.objects.filter(
                    template=template,
                    question=question
                ).exists():
                    continue
                
                # Create new template question
                # max_order += 1
                TemplateQuestion.objects.create(
                    template=template,
                    question=question,
                    # display_order=max_order,
                    section_name=section_name if section_name else None,
                    is_mandatory=is_mandatory
                )
                added_count += 1
                
            except InspectionQuestion.DoesNotExist:
                continue
        
        if added_count > 0:
            messages.success(
                request,
                f'{added_count} question(s) added to template successfully!'
            )
        else:
            messages.warning(request, 'No new questions were added. They may already be in the template.')
        
        return redirect('inspections:template_detail', pk=template.pk)
    
    # GET request - show selection form
    
    # Get questions NOT already in this template
    existing_question_ids = TemplateQuestion.objects.filter(
        template=template
    ).values_list('question_id', flat=True)
    
    # Get all active categories
    categories = InspectionCategory.objects.filter(
        is_active=True
    ) #.order_by('display_order')
    
    # Filter by category if selected
    selected_category = request.GET.get('category')
    
    available_questions = InspectionQuestion.objects.filter(
        is_active=True
    ).exclude(
        id__in=existing_question_ids
    ).select_related('category') #.order_by('category__display_order', 'display_order')
    
    if selected_category:
        available_questions = available_questions.filter(category_id=selected_category)
    
    context = {
        'template': template,
        'categories': categories,
        'available_questions': available_questions,
        'selected_category': selected_category,
        'title': f'Bulk Add Questions to {template.template_name}'
    }
    return render(request, 'inspections/template_bulk_add_questions.html', context)



@login_required
def template_remove_question(request, template_pk, question_pk):
    """Remove question from template"""
    
    template = get_object_or_404(InspectionTemplate, pk=template_pk)
    template_question = get_object_or_404(
        TemplateQuestion,
        template=template,
        question_id=question_pk
    )
    
    if request.method == 'POST':
        question_code = template_question.question.question_code
        template_question.delete()
        messages.success(request, f'Question {question_code} removed from template!')
        return redirect('inspections:template_detail', pk=template.pk)
    
    context = {
        'template': template,
        'template_question': template_question
    }
    return render(request, 'inspections/question_confirm_delete.html', context)


@login_required
def template_reorder_questions(request, pk):
    """AJAX endpoint to reorder questions in template"""
    
    if request.method == 'POST':
        import json
        
        template = get_object_or_404(InspectionTemplate, pk=pk)
        data = json.loads(request.body)
        
        for item in data:
            template_question = TemplateQuestion.objects.get(
                template=template,
                id=item['id']
            )
            # template_question.display_order = item['order']
            template_question.save()
        
        return JsonResponse({'status': 'success', 'message': 'Questions reordered successfully'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def template_clone(request, pk):
    """Clone/duplicate a template"""
    
    original_template = get_object_or_404(InspectionTemplate, pk=pk)
    
    if request.method == 'POST':
        # Create new template
        new_template = InspectionTemplate.objects.create(
            template_name=f"{original_template.template_name} (Copy)",
            template_code=f"{original_template.template_code}-COPY",
            inspection_type=original_template.inspection_type,
            description=original_template.description,
            # requires_approval=original_template.requires_approval,
            min_compliance_score=original_template.min_compliance_score,
            created_by=request.user
        )
        
        # Copy applicable plants and departments
        new_template.applicable_plants.set(original_template.applicable_plants.all())
        new_template.applicable_departments.set(original_template.applicable_departments.all())
        
        # Copy all questions
        for tq in original_template.template_questions.all():
            TemplateQuestion.objects.create(
                template=new_template,
                question=tq.question,
                is_mandatory=tq.is_mandatory,
                # display_order=tq.display_order,
                section_name=tq.section_name
            )
        
        messages.success(request, f'Template cloned successfully as "{new_template.template_name}"!')
        return redirect('inspections:template_detail', pk=new_template.pk)
    
    context = {
        'template': original_template
    }
    return render(request, 'inspections/template_clone.html', context)


# ====================================
# SCHEDULE VIEWS
# ====================================

@login_required
def schedule_list(request):
    """List all inspection schedules"""
    
    schedules = InspectionSchedule.objects.select_related(
        'template',
        'assigned_to',
        'assigned_by',
        'department'
    )
    
    # User-based filtering
    if request.user.is_superuser or request.user.is_admin_user:
        pass
    # elif request.user.has_permission('CONDUCT_INSPECTION') or request.user.can_access_inspection_module:
    #     user_plants = request.user.get_all_plants()
    #     schedules = schedules.filter(plants__in=user_plants).distinct()
    elif request.user.has_permission('CONDUCT_INSPECTION'):
        schedules = schedules.filter(assigned_to=request.user)
    elif request.user.can_access_inspection_module:
        user_plants = request.user.get_all_plants()
        schedules = schedules.filter(plants__in=user_plants).distinct()
    else:
        schedules = schedules.none()
    
    # Filters
    status = request.GET.get('status')
    plant_id = request.GET.get('plant')
    assigned_to_id = request.GET.get('assigned_to')
    search = request.GET.get('search')
    
    if status:
        schedules = schedules.filter(status=status)
    
    if plant_id:
        schedules = schedules.filter(plants__id=plant_id)
    
    if assigned_to_id:
        schedules = schedules.filter(assigned_users__id=assigned_to_id)
    
    if search:
        schedules = schedules.filter(
            Q(schedule_code__icontains=search) |
            Q(template__template_name__icontains=search) |
            Q(assigned_users__first_name__icontains=search) |
            Q(assigned_users__last_name__icontains=search)
        )
    
    schedules = schedules.distinct().order_by('-created_at')
    
    paginator = Paginator(schedules, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    querydict = request.GET.copy()
    querydict.pop('page', None)

    from apps.organizations.models import Plant
    plants = Plant.objects.filter(is_active=True)
    
    hods = User.objects.filter(
        role__name__in=['HOD', 'SAFETY MANAGER'],
        is_active_employee=True
    ).order_by('first_name', 'last_name')
    
    context = {
        'page_obj': page_obj,
        'status_choices': InspectionSchedule.STATUS_CHOICES,
        'plants': plants,
        'hods': hods,
        'selected_status': status,
        'selected_plant': plant_id,
        'selected_hod': assigned_to_id,
        'search': search,
        'querystring': querydict.urlencode(),
    }
    return render(request, 'inspections/schedule_list.html', context)

@login_required
def schedule_create(request):
    """
    Create inspection schedule.
    Plants/zones/locations/sublocations/assigned_users
    come from checkboxes in the template (not form fields).
    On submit:
    - Creates one InspectionSchedule per assigned user
    - If enable_auto_schedule → also saves TemplateAutoScheduleConfig
    """
    if request.method == 'POST':
        form = InspectionScheduleForm(request.POST, user=request.user)

        # Get checkbox data from POST
        selected_plant_ids = request.POST.getlist('selected_plants')
        selected_zone_ids = request.POST.getlist('selected_zones')
        selected_location_ids = request.POST.getlist('selected_locations')
        selected_sublocation_ids = request.POST.getlist('selected_sublocations')
        selected_user_ids = request.POST.getlist('selected_users')

        # Validate selections
        if not selected_plant_ids:
            messages.error(request, 'Please select at least one plant.')
            return render(request, 'inspections/schedule_form.html', {
                'form': form, 'action': 'Create', 'title': 'Schedule New Inspection'
            })

        if not selected_user_ids:
            messages.error(request, 'Please select at least one HOD or Safety Manager.')
            return render(request, 'inspections/schedule_form.html', {
                'form': form, 'action': 'Create', 'title': 'Schedule New Inspection'
            })

        if form.is_valid():
            enable_auto = form.cleaned_data.get('enable_auto_schedule')

            try:
                with transaction.atomic():
                    # Fetch selected objects
                    from apps.organizations.models import Plant, Zone, Location, SubLocation
                    plants = Plant.objects.filter(id__in=selected_plant_ids)
                    zones = Zone.objects.filter(id__in=selected_zone_ids)
                    locations = Location.objects.filter(id__in=selected_location_ids)
                    sublocations = SubLocation.objects.filter(id__in=selected_sublocation_ids)
                    assigned_users = User.objects.filter(
                        id__in=selected_user_ids,
                        role__name__in=['HOD', 'SAFETY MANAGER'],
                        is_active_employee=True
                    )

                    created_schedules = []

                    # Create one schedule per assigned user
                    for user in assigned_users:
                        schedule = InspectionSchedule(
                            template=form.cleaned_data['template'],
                            assigned_to=user,
                            assigned_by=request.user,
                            department=form.cleaned_data.get('department'),
                            scheduled_date=form.cleaned_data.get('scheduled_date'),
                            due_date=form.cleaned_data.get('due_date'),
                            scheduled_end_date=form.cleaned_data.get('scheduled_end_date'),
                            assignment_notes=form.cleaned_data.get('assignment_notes', ''),
                            status='SCHEDULED'
                        )
                        schedule.save()

                        # Set M2M
                        schedule.plants.set(plants)
                        schedule.zones.set(zones)
                        schedule.locations.set(locations)
                        schedule.sublocations.set(sublocations)
                        schedule.assigned_users.set(assigned_users)

                        created_schedules.append(schedule)

                        # Notify each user
                        try:
                            NotificationService.notify(
                                content_object=schedule,
                                notification_type='INSPECTION_SCHEDULE',
                                module='INSPECTION'
                            )
                        except Exception as e:
                            print(f"Notification error: {e}")

                    # If auto-schedule enabled → save config
                    if enable_auto:
                        due_offset = form.cleaned_data.get('due_date_offset_days') or 7

                        # ✅ Prevent duplicate configs for same template
                        config, created = TemplateAutoScheduleConfig.objects.get_or_create(
                            template=form.cleaned_data['template'],
                            defaults={
                                'due_date_offset_days': due_offset,
                                'is_active': True,
                                'is_paused': False,
                                'created_by': request.user
                            }
                        )

                        # ✅ If already exists → update it
                        if not created:
                            config.due_date_offset_days = due_offset
                            config.is_active = True
                            config.is_paused = False
                            config.save()

                        # ✅ Set relations
                        config.plants.set(plants)
                        config.zones.set(zones)
                        config.locations.set(locations)
                        config.sublocations.set(sublocations)
                        config.assigned_users.set(assigned_users)

                        # ✅ LINK schedules to config
                        for schedule in created_schedules:
                            schedule.auto_schedule_config = config
                            schedule.save()

                    messages.success(
                        request,
                        f'{len(created_schedules)} inspection schedule(s) created successfully!'
                        + (' Auto-monthly schedule enabled.' if enable_auto else '')
                    )
                    return redirect('inspections:schedule_list')

            except Exception as e:
                messages.error(request, f'Error creating schedule: {str(e)}')

    else:
        form = InspectionScheduleForm(user=request.user)

    context = {
        'form': form,
        'action': 'Create',
        'title': 'Schedule New Inspection'
    }
    return render(request, 'inspections/schedule_form.html', context)

@login_required
def schedule_edit(request, pk):
    """Edit inspection schedule"""
    
    schedule = get_object_or_404(InspectionSchedule, pk=pk)
    
    # Check permissions
    if not request.user.is_superuser and not request.user.is_admin_user:
        if schedule.status in ['CLOSED', 'LATE_CLOSE', 'CANCELLED']:
            messages.error(request, 'Cannot edit CLOSED or cancelled inspections!')
            return redirect('inspections:schedule_detail', pk=pk)
    
    if request.method == 'POST':
        form = InspectionScheduleForm(request.POST, instance=schedule, user=request.user)
        # if form.is_valid():
        #     schedule = form.save(commit=False)
        #     schedule.save()

        #     selected_plant_ids = request.POST.getlist('selected_plants')
        #     selected_zone_ids = request.POST.getlist('selected_zones')
        #     selected_location_ids = request.POST.getlist('selected_locations')
        #     selected_sublocation_ids = request.POST.getlist('selected_sublocations')
        #     selected_user_ids = request.POST.getlist('selected_users')

        #     schedule.plants.set(Plant.objects.filter(id__in=selected_plant_ids))
        #     schedule.zones.set(Zone.objects.filter(id__in=selected_zone_ids))
        #     schedule.locations.set(Location.objects.filter(id__in=selected_location_ids))
        #     schedule.sublocations.set(SubLocation.objects.filter(id__in=selected_sublocation_ids))
        #     schedule.assigned_users.set(User.objects.filter(id__in=selected_user_ids))
        #     enable_auto = form.cleaned_data.get('enable_auto_schedule')
        #     due_offset = form.cleaned_data.get('due_date_offset_days') or 7

        #     messages.success(request, 'Inspection schedule updated successfully!')
        #     return redirect('inspections:schedule_detail', pk=pk)

        if form.is_valid():

            schedule = form.save(commit=False)
            schedule.save()

            selected_plant_ids = request.POST.getlist('selected_plants')
            selected_zone_ids = request.POST.getlist('selected_zones')
            selected_location_ids = request.POST.getlist('selected_locations')
            selected_sublocation_ids = request.POST.getlist('selected_sublocations')
            selected_user_ids = request.POST.getlist('selected_users')

            # Update M2M fields
            schedule.plants.set(
                Plant.objects.filter(id__in=selected_plant_ids)
            )

            schedule.zones.set(
                Zone.objects.filter(id__in=selected_zone_ids)
            )

            schedule.locations.set(
                Location.objects.filter(id__in=selected_location_ids)
            )

            schedule.sublocations.set(
                SubLocation.objects.filter(id__in=selected_sublocation_ids)
            )

            schedule.assigned_users.set(
                User.objects.filter(id__in=selected_user_ids)
            )

            # AUTO SCHEDULE LOGIC
            enable_auto = form.cleaned_data.get('enable_auto_schedule')
            due_offset = form.cleaned_data.get('due_date_offset_days') or 7

            if enable_auto:

                config, created = TemplateAutoScheduleConfig.objects.get_or_create(
                    template=schedule.template,
                    defaults={
                        'due_date_offset_days': due_offset,
                        'is_active': True,
                        'is_paused': False,
                        'created_by': request.user
                    }
                )

                config.due_date_offset_days = due_offset
                config.is_active = True
                config.is_paused = False
                config.save()

                config.plants.set(schedule.plants.all())
                config.zones.set(schedule.zones.all())
                config.locations.set(schedule.locations.all())
                config.sublocations.set(schedule.sublocations.all())
                config.assigned_users.set(schedule.assigned_users.all())

                schedule.auto_schedule_config = config
                schedule.save()
            else:
                schedule.auto_schedule_config = None
                schedule.save()

            messages.success(request, 'Inspection schedule updated successfully!')
            return redirect('inspections:schedule_detail', pk=pk)
    else:
        # form = InspectionScheduleForm(instance=schedule, user=request.user)
        initial_data = {
            'enable_auto_schedule': bool(schedule.auto_schedule_config),
            'due_date_offset_days': (
                schedule.auto_schedule_config.due_date_offset_days
                if schedule.auto_schedule_config else 7
            )
        }

        form = InspectionScheduleForm(instance=schedule,user=request.user,initial=initial_data)
    
    context = {
        'form': form,
        'action': 'Edit',
        'title': f'Edit Schedule: {schedule.schedule_code}',
        'schedule': schedule,

        'selected_plants': list(schedule.plants.values_list('id', flat=True)),
        'selected_zones': list(schedule.zones.values_list('id', flat=True)),
        'selected_locations': list(schedule.locations.values_list('id', flat=True)),
        'selected_sublocations': list(schedule.sublocations.values_list('id', flat=True)),
        'selected_users': [schedule.assigned_to.id] if schedule.assigned_to else [],

    }
    return render(request, 'inspections/schedule_form.html', context)


@login_required
def schedule_detail(request, pk):
    """View schedule details"""
    
    schedule = get_object_or_404(
        InspectionSchedule.objects.select_related(
            'template',
            'assigned_to',
            'assigned_by',
            'department'
        ).prefetch_related(
            'plants', 'zones', 'locations', 'sublocations', 'assigned_users'
        ),
        pk=pk
    )
    
    # Check access
    if not request.user.is_superuser and not request.user.is_admin_user:
        if request.user.has_permission('VIEW_INSPECTION') and schedule.assigned_to != request.user:
            messages.error(request, 'You do not have permission to view this inspection!')
            return redirect('inspections:schedule_list')
    
    context = {
        'schedule': schedule,
        'can_edit': schedule.status not in ['CLOSED', 'LATE_CLOSE', 'CANCELLED'],
        'can_start': schedule.status == 'SCHEDULED' and schedule.assigned_to == request.user,
        'can_cancel': schedule.status not in ['CLOSED', 'LATE_CLOSE', 'CANCELLED'],
        'can_restart': (
            schedule.status == 'OVERDUE' and (
                request.user == schedule.assigned_to or
                request.user.is_superuser or
                request.user.is_admin_user
            )
        ),
    }
    return render(request, 'inspections/schedule_detail.html', context)


class InspectionPDFDownloadView(LoginRequiredMixin, View):
    """Generate PDF report for an inspection schedule."""

    def get(self, request, pk):
        schedule = get_object_or_404(
            InspectionSchedule.objects.select_related(
                'template',
                'assigned_to',
                'assigned_by',
                'department'
            ).prefetch_related(
                'plants', 'zones', 'locations', 'sublocations', 'assigned_users'
            ),
            pk=pk
        )

        if not (
            request.user.is_superuser or
            request.user.is_admin_user or
            request.user.has_permission('EXPORT_INSPECTION_PDF') or
            request.user.has_permission('VIEW_INSPECTION')
        ):
            messages.error(request, "You don't have permission to download this report")
            return redirect('inspections:schedule_list')

        return generate_inspection_pdf(schedule)


@login_required
def get_users_by_plants(request):
    """
    AJAX: Get HODs and Safety Managers for selected plants.
    Used in schedule create form checkbox section.
    """
    plant_ids = request.GET.get('plant_ids', '')

    if not plant_ids:
        return JsonResponse({'users': []})

    ids = [pid.strip() for pid in plant_ids.split(',') if pid.strip()]

    users = User.objects.filter(
        plant__id__in=ids,
        role__name__in=['HOD', 'SAFETY MANAGER'],
        is_active_employee=True,
        is_active=True
    ).select_related('plant', 'role', 'department').order_by('plant__name', 'first_name')

    users_data = []
    for u in users:
        users_data.append({
            'id': u.id,
            'full_name': u.get_full_name(),
            'role': u.role.name if u.role else '',
            'department': u.department.name if u.department else '',
            'plant_name': u.plant.name if u.plant else '',
            'plant_id': u.plant.id if u.plant else None,
        })

    return JsonResponse({'users': users_data})


@login_required
def autoschedule_toggle(request, config_id):
    """
    Stop / Pause / Resume auto-schedule config.
    Called from template detail page buttons.
    """
    config = get_object_or_404(TemplateAutoScheduleConfig, pk=config_id)

    action = request.POST.get('action')

    if action == 'stop':
        config.is_active = False
        config.is_paused = False
        config.save()
        messages.success(request, 'Auto-schedule stopped. Existing schedules are kept.')

    elif action == 'pause':
        config.is_paused = True
        config.save()
        messages.success(request, 'Auto-schedule paused.')

    elif action == 'resume':
        config.is_active = True
        config.is_paused = False
        config.save()
        messages.success(request, 'Auto-schedule resumed.')

    return redirect('inspections:template_detail', pk=config.template.pk)
@login_required
def schedule_cancel(request, pk):
    """Cancel inspection schedule"""
    
    schedule = get_object_or_404(InspectionSchedule, pk=pk)
    
    if schedule.status in ['CLOSED', 'LATE_CLOSE', 'CANCELLED']:
        messages.error(request, 'Cannot cancel CLOSED or already cancelled inspections!')
        return redirect('inspections:schedule_detail', pk=pk)
    
    if request.method == 'POST':
        schedule.status = 'CANCELLED'
        schedule.save()
        
        messages.success(request, f'Inspection {schedule.schedule_code} cancelled successfully!')
        return redirect('inspections:schedule_list')
    
    context = {
        'schedule': schedule
    }
    return render(request, 'inspections/schedule_cancel.html', context)


@login_required
def schedule_send_reminder(request, pk):
    """Send reminder for scheduled inspection"""
    
    schedule = get_object_or_404(InspectionSchedule, pk=pk)
    
    if schedule.status not in ['SCHEDULED', 'IN_PROGRESS', 'OVERDUE']:
        messages.error(request, 'Can only send reminders for scheduled or in-progress inspections!')
        return redirect('inspections:schedule_detail', pk=pk)
    
    # Send reminder email
    # send_inspection_reminder_email(schedule)
    
    schedule.reminder_sent = True
    schedule.reminder_sent_at = timezone.now()
    schedule.save()

    NotificationService.notify(
        content_object=schedule,
        notification_type='NOTIFY_INSPECTION',
        module='INSPECTION'
    )
    
    messages.success(request, f'Reminder sent to {schedule.assigned_to.get_full_name()}!')
    return redirect('inspections:schedule_detail', pk=pk)


@login_required
def schedule_delete(request, pk):
    """Delete an inspection schedule."""
    schedule = get_object_or_404(InspectionSchedule, pk=pk)

    if not (
        request.user.is_superuser or
        request.user.is_admin_user or
        request.user.has_permission('DELETE_INSPECTION')
    ):
        messages.error(request, 'You are not authorized to delete this inspection.')
        return redirect('inspections:schedule_list')

    if request.method == 'POST':
        schedule_code = schedule.schedule_code
        schedule.delete()
        messages.success(request, f'Inspection "{schedule_code}" deleted successfully.')
        return redirect('inspections:schedule_list')

    return redirect('inspections:schedule_list')


@login_required
def my_inspections(request):
    """View for HOD to see their assigned inspections"""
    
    if not request.user.has_permission('VIEW_INSPECTION'):
        messages.error(request, 'This page is only for HODs!')
        return redirect('inspections:inspection_dashboard')
    
    schedules = InspectionSchedule.objects.filter(
        assigned_to=request.user
    ).select_related('template', 'department').order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    if status:
        schedules = schedules.filter(status=status)
    
    schedules = schedules.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(schedules, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Stats
    stats = {
        'scheduled': InspectionSchedule.objects.filter(
            assigned_to=request.user,
            status='SCHEDULED'
        ).count(),
        'in_progress': InspectionSchedule.objects.filter(
            assigned_to=request.user,
            status='IN_PROGRESS'
        ).count(),
        'CLOSED': InspectionSchedule.objects.filter(
            assigned_to=request.user,
            status__in=['CLOSED', 'LATE_CLOSE']
        ).count(),
        'overdue': InspectionSchedule.objects.filter(
            assigned_to=request.user,
            status='OVERDUE'
        ).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'selected_status': status,
        'status_choices': InspectionSchedule.STATUS_CHOICES
    }
    return render(request, 'inspections/my_inspections.html', context)


########################inspection start ###################################
@login_required
def inspection_start(request, schedule_id):
    """HOD starts filling the inspection"""
    
    schedule = get_object_or_404(InspectionSchedule, pk=schedule_id)
    
    # Check permission - only assigned HOD can start
    if schedule.assigned_to != request.user:
        messages.error(request, 'You are not authorized to access this inspection!')
        return redirect('inspections:my_inspections')
    
    # Check if already CLOSED
    if schedule.status in ['CLOSED', 'LATE_CLOSE']:
        messages.warning(request, 'This inspection is already CLOSED!')
        return redirect('inspections:schedule_detail', pk=schedule.pk)
    
    # Update status to IN_PROGRESS
    if schedule.status == 'SCHEDULED':
        schedule.status = 'IN_PROGRESS'
        schedule.started_at = timezone.now()
        schedule.save()
    
    context = _build_inspection_form_context(schedule, request.user)
    return render(request, 'inspections/inspection_form.html', context)



def generate_finding_code(submission):
    """Generate unique finding code"""
    from datetime import datetime
    date_str = datetime.now().strftime('%Y%m')
    
    last_finding = InspectionFinding.objects.filter(
        finding_code__startswith=f"FIND-{date_str}"
    ).order_by('-finding_code').first()
    
    if last_finding:
        try:
            last_num = int(last_finding.finding_code.split('-')[-1])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1
    
    return f"FIND-{date_str}-{new_num:04d}"


def _get_selected_scope_ids(source_data, inspection_scope):
    def _clean_ids(values, available_qs):
        allowed_ids = set(available_qs.values_list('id', flat=True))
        resolved = []
        for raw_id in values or []:
            try:
                parsed_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if parsed_id in allowed_ids and parsed_id not in resolved:
                resolved.append(parsed_id)
        return resolved

    selected_plant_ids = _clean_ids(source_data.get('selected_plants', []), inspection_scope['plants'])
    selected_zone_ids = _clean_ids(
        source_data.get('selected_zones', []),
        inspection_scope['zones'].filter(plant_id__in=selected_plant_ids).distinct()
    )
    selected_location_ids = _clean_ids(
        source_data.get('selected_locations', []),
        inspection_scope['locations'].filter(zone_id__in=selected_zone_ids).distinct()
    )
    selected_sublocation_ids = _clean_ids(
        source_data.get('selected_sublocations', []),
        inspection_scope['sublocations'].filter(location_id__in=selected_location_ids).distinct()
    )

    return {
        'selected_plant_ids': selected_plant_ids,
        'selected_zone_ids': selected_zone_ids,
        'selected_location_ids': selected_location_ids,
        'selected_sublocation_ids': selected_sublocation_ids,
    }


def _build_inspection_form_context(
    schedule,
    user,
    *,
    source_data=None,
    field_errors=None,
    scope_errors=None,
    non_field_errors=None
):
    from collections import defaultdict

    template_questions = TemplateQuestion.objects.filter(
        template=schedule.template
    ).select_related(
        'question',
        'question__category'
    ) #removed .order_by('display_order')

    inspection_scope = _get_inspection_scope(schedule, user)
    available_plants = inspection_scope['plants']
    available_zones = inspection_scope['zones']
    available_locations = inspection_scope['locations']
    available_sublocations = inspection_scope['sublocations']

    draft = getattr(schedule, 'draft', None)
    draft_data = draft.data if draft else {}
    active_source = source_data if source_data is not None else draft_data
    draft_photo_map = {}

    if draft:
        draft_photo_map = {
            photo.question_id: photo
            for photo in draft.photos.select_related('question').all()
        }

    selected_scope = _get_selected_scope_ids(active_source or {}, inspection_scope)
    answers_by_question = (active_source or {}).get('answers', {})
    remarks_by_question = (active_source or {}).get('remarks', {})

    questions_by_category = defaultdict(list)
    for tq in template_questions:
        question_key = str(tq.question.id)
        tq.prefill_answer = answers_by_question.get(question_key, '')
        tq.prefill_remarks = remarks_by_question.get(question_key, '')
        tq.answer_error = (field_errors or {}).get(f'question_{tq.question.id}', '')
        tq.remarks_error = (field_errors or {}).get(f'remarks_{tq.question.id}', '')
        tq.photo_error = (field_errors or {}).get(f'photo_{tq.question.id}', '')
        tq.draft_photo = draft_photo_map.get(tq.question.id)
        questions_by_category[tq.question.category].append(tq)

    header_plants = available_plants if available_plants.exists() else schedule.plants.filter(is_active=True)

    return {
        'schedule': schedule,
        'questions_by_category': dict(questions_by_category.items()),
        'total_questions': template_questions.count(),
        'available_plants': available_plants,
        'available_zones': available_zones,
        'available_locations': available_locations,
        'available_sublocations': available_sublocations,
        'header_plants': header_plants,
        'selected_plant_ids': selected_scope['selected_plant_ids'],
        'selected_zone_ids': selected_scope['selected_zone_ids'],
        'selected_location_ids': selected_scope['selected_location_ids'],
        'selected_sublocation_ids': selected_scope['selected_sublocation_ids'],
        'allowed_plant_ids': list(available_plants.values_list('id', flat=True)),
        'allowed_zone_ids': list(available_zones.values_list('id', flat=True)),
        'allowed_location_ids': list(available_locations.values_list('id', flat=True)),
        'allowed_sublocation_ids': list(available_sublocations.values_list('id', flat=True)),
        'scope_errors': scope_errors or {},
        'non_field_errors': non_field_errors or [],
        'draft_exists': bool(draft),
    }


@login_required
def inspection_submit(request, schedule_id):
    """HOD submits the CLOSED inspection"""
    
    schedule = get_object_or_404(
        InspectionSchedule.objects.select_related('template', 'assigned_to', 'assigned_by').prefetch_related(
            'plants', 'zones', 'locations', 'sublocations'
        ),
        pk=schedule_id
    )

    # Check permission
    if schedule.assigned_to != request.user:
        messages.error(request, 'Unauthorized access!')
        return redirect('inspections:my_inspections')
    

    if request.method != 'POST':
        return redirect('inspections:inspection_start', schedule_id=schedule_id)
    try:
        inspection_scope = _get_inspection_scope(schedule, request.user)
        available_plants = inspection_scope['plants']
        available_zones = inspection_scope['zones']
        available_locations = inspection_scope['locations']
        available_sublocations = inspection_scope['sublocations']

        source_data = {
            'selected_plants': request.POST.getlist('selected_plants'),
            'selected_zones': request.POST.getlist('selected_zones'),
            'selected_locations': request.POST.getlist('selected_locations'),
            'selected_sublocations': request.POST.getlist('selected_sublocations'),
            'answers': {},
            'remarks': {},
        }

        template_questions = TemplateQuestion.objects.filter(
            template=schedule.template
        ).select_related('question')

        for tq in template_questions:
            question_id = str(tq.question.id)
            source_data['answers'][question_id] = request.POST.get(f'question_{question_id}', '')
            source_data['remarks'][question_id] = request.POST.get(f'remarks_{question_id}', '').strip()

        selected_scope = _get_selected_scope_ids(source_data, inspection_scope)
        selected_plant_ids = selected_scope['selected_plant_ids']
        selected_zone_ids = selected_scope['selected_zone_ids']
        selected_location_ids = selected_scope['selected_location_ids']
        selected_sublocation_ids = selected_scope['selected_sublocation_ids']

        action = request.POST.get('form_action', 'submit')

        if action == 'draft':
            draft, _ = InspectionDraft.objects.update_or_create(
                schedule=schedule,
                defaults={
                    'saved_by': request.user,
                    'data': {
                        'selected_plants': selected_plant_ids,
                        'selected_zones': selected_zone_ids,
                        'selected_locations': selected_location_ids,
                        'selected_sublocations': selected_sublocation_ids,
                        'answers': source_data['answers'],
                        'remarks': source_data['remarks'],
                    }
                }
            )

            for tq in template_questions:
                photo = request.FILES.get(f'photo_{tq.question.id}')
                if photo:
                    InspectionDraftPhoto.objects.update_or_create(
                        draft=draft,
                        question=tq.question,
                        defaults={'photo': photo}
                    )

            messages.success(request, f'Draft saved for inspection {schedule.schedule_code}.')
            return redirect('inspections:inspection_start', schedule_id=schedule_id)

        field_errors = {}
        scope_errors = {}
        non_field_errors = []

        if available_plants.exists() and not selected_plant_ids:
            scope_errors['selected_plants'] = 'Please select at least one plant.'
        if available_zones.filter(plant_id__in=selected_plant_ids).exists() and not selected_zone_ids:
            scope_errors['selected_zones'] = 'Please select at least one zone.'
        if available_locations.filter(zone_id__in=selected_zone_ids).exists() and not selected_location_ids:
            scope_errors['selected_locations'] = 'Please select at least one location.'
        if available_sublocations.filter(location_id__in=selected_location_ids).exists() and not selected_sublocation_ids:
            scope_errors['selected_sublocations'] = 'Please select at least one sub-location.'

        draft = getattr(schedule, 'draft', None)
        draft_photo_map = {}
        if draft:
            draft_photo_map = {
                photo.question_id: photo
                for photo in draft.photos.select_related('question').all()
            }

        for tq in template_questions:
            question = tq.question
            question_id = question.id
            answer = source_data['answers'].get(str(question_id), '').strip()
            remarks = source_data['remarks'].get(str(question_id), '').strip()
            photo = request.FILES.get(f'photo_{question_id}')
            draft_photo = draft_photo_map.get(question_id)

            if tq.is_mandatory and not answer:
                field_errors[f'question_{question_id}'] = 'This answer is required.'
            if question.is_remarks_mandatory and not remarks:
                field_errors[f'remarks_{question_id}'] = 'Remarks are required.'
            if question.is_photo_required and not photo and not draft_photo:
                field_errors[f'photo_{question_id}'] = 'Photo evidence is required.'

        if scope_errors or field_errors:
            non_field_errors.append('Please correct the highlighted fields and submit again.')
            context = _build_inspection_form_context(
                schedule,
                request.user,
                source_data=source_data,
                field_errors=field_errors,
                scope_errors=scope_errors,
                non_field_errors=non_field_errors
            )
            return render(request, 'inspections/inspection_form.html', context)

        with transaction.atomic():
            submission = InspectionSubmission.objects.create(
                schedule=schedule,
                submitted_by=request.user,
                remarks=request.POST.get('overall_remarks', '').strip()
            )
            no_answers = []
            for tq in template_questions:
                question = tq.question
                question_id = str(question.id)
                answer = source_data['answers'].get(question_id, '').strip()
                remarks = source_data['remarks'].get(question_id, '').strip()
                uploaded_photo = request.FILES.get(f'photo_{question.id}')
                draft_photo = draft_photo_map.get(question.id)
                photo = uploaded_photo or (draft_photo.photo if draft_photo else None)

                if not answer:
                    continue

                response = InspectionResponse.objects.create(
                    submission=submission,
                    question=question,
                    answer=answer,
                    remarks=remarks,
                    photo=photo
                )
                if answer == 'No':
                    no_answers.append({'question': question, 'response': response})
                    if question.auto_generate_finding:
                        InspectionFinding.objects.create(
                            submission=submission,
                            question=question,
                            finding_code=generate_finding_code(submission),
                            description=f"Non-compliance found: {question.question_text}",
                            priority='HIGH' if question.is_critical else 'MEDIUM',
                            status='OPEN'
                        )
            submission.compliance_score = submission.calculate_compliance_score()
            submission.save()
            schedule.plants.set(Plant.objects.filter(id__in=selected_plant_ids, is_active=True))
            schedule.zones.set(Zone.objects.filter(id__in=selected_zone_ids, is_active=True))
            schedule.locations.set(Location.objects.filter(id__in=selected_location_ids, is_active=True))
            schedule.sublocations.set(SubLocation.objects.filter(id__in=selected_sublocation_ids, is_active=True))

            schedule.status = 'LATE_CLOSE' if '[RESTARTED_FROM:' in (schedule.assignment_notes or '') else 'CLOSED'
            schedule.closed_at = timezone.now()
            schedule.save(update_fields=['status', 'closed_at'])

            InspectionDraft.objects.filter(schedule=schedule).delete()

            NotificationService.notify(
                content_object=submission,
                notification_type='INSPECTION_SUBMITTED',
                module='INSPECTION'
            )
            messages.success(
                request,
                f'Inspection {schedule.schedule_code} submitted successfully! Compliance Score: {submission.compliance_score}%'
            )
            return redirect('inspections:inspection_review', submission_id=submission.id)
    except Exception as e:
        messages.error(request, f'Inspection submission failed: {str(e)}')
        return redirect('inspections:inspection_start', schedule_id=schedule_id)


@login_required
def inspection_review(request, submission_id):
    """Review CLOSED inspection showing ALL answers and details."""
    
    submission = get_object_or_404(
        InspectionSubmission.objects
        .select_related('schedule', 'schedule__template', 'submitted_by')
        .prefetch_related('schedule__plants'),
        pk=submission_id
    )
    
    # Check permission (No changes here)
    if not (request.user.is_superuser or 
            request.user == submission.submitted_by or
            request.user.can_access_inspection_module):
        messages.error(request, 'Unauthorized access!')
        return redirect('inspections:inspection_dashboard')

    # ===================================================================
    # START OF THE FIX
    # ===================================================================

    # Get ALL responses for this submission, not just "No" answers.
    # Pre-fetch related question and category data for efficiency.
    all_responses = submission.responses.select_related(
        'question',
        'question__category',
        'assigned_to',
        'assigned_by',
        'converted_to_hazard'
    ).order_by('question__category__category_name') # Order for consistent display

    # Group all responses by category for structured display in the template.
    from collections import defaultdict
    responses_by_category = defaultdict(list)
    
    for response in all_responses:
        responses_by_category[response.question.category].append(response)

    # ===================================================================
    # END OF THE FIX
    # ===================================================================
    
    # Get all findings for this submission (No changes here)
    findings = InspectionFinding.objects.filter(
        submission=submission
    ).select_related('question', 'assigned_to')

    template_questions_count = TemplateQuestion.objects.filter(
        template=submission.schedule.template
    ).count()
    
    # Get all responses for statistics (This was already correct)
    total_questions = all_responses.count()
    yes_count = all_responses.filter(answer='Yes').count()
    no_count = all_responses.filter(answer='No').count()
    na_count = all_responses.filter(answer='N/A').count()

    finding_response_map = {
        response.question_id: response
        for response in all_responses
    }

    for finding in findings:
        finding.review_response = finding_response_map.get(finding.question_id)
    
    context = {
        'submission': submission,
        'schedule': submission.schedule,
        'plants': submission.schedule.plants.all().order_by('name'),
        'zones': submission.schedule.zones.select_related('plant').all().order_by('plant__name', 'name'),
        'locations': submission.schedule.locations.select_related('zone', 'zone__plant').all().order_by('zone__plant__name', 'zone__name', 'name'),
        'sublocations': submission.schedule.sublocations.select_related('location', 'location__zone', 'location__zone__plant').all().order_by('location__zone__plant__name', 'location__zone__name', 'location__name', 'name'),
        # Pass the new dictionary with ALL responses to the template
        'responses_by_category': dict(responses_by_category),
        'findings': findings,
        'total_questions': total_questions,
        'template_questions_count': template_questions_count,
        'unanswered_count': max(template_questions_count - total_questions, 0),
        'yes_count': yes_count,
        'no_count': no_count,
        'na_count': na_count,
        'compliance_score': submission.compliance_score,
    }
    
    return render(request, 'inspections/inspection_review.html', context)

# ====================================
# AJAX/API ENDPOINTS
# ====================================

@login_required
def get_zones_by_plant(request):
    """AJAX: Get zones for selected plant"""
    
    plant_id = request.GET.get('plant_id')
    
    if not plant_id:
        return JsonResponse({'zones': []})
    
    from apps.organizations.models import Zone
    zones = Zone.objects.filter(plant_id=plant_id, is_active=True).values('id', 'name')
    
    return JsonResponse({'zones': list(zones)})


@login_required
def get_locations_by_zone(request):
    """AJAX: Get locations for selected zone"""
    
    zone_id = request.GET.get('zone_id')
    
    if not zone_id:
        return JsonResponse({'locations': []})
    
    from apps.organizations.models import Location
    locations = Location.objects.filter(zone_id=zone_id, is_active=True).values('id', 'name')
    
    return JsonResponse({'locations': list(locations)})


@login_required
def get_sublocations_by_location(request):
    """AJAX: Get sublocations for selected location"""
    
    location_id = request.GET.get('location_id')
    
    if not location_id:
        return JsonResponse({'sublocations': []})
    
    from apps.organizations.models import SubLocation
    sublocations = SubLocation.objects.filter(
        location_id=location_id,
        is_active=True
    ).values('id', 'name')
    
    return JsonResponse({'sublocations': list(sublocations)})


@login_required
def get_questions_by_category(request):
    """AJAX: Get questions for selected category"""
    
    category_id = request.GET.get('category_id')
    template_id = request.GET.get('template_id')
    
    if not category_id:
        return JsonResponse({'questions': []})
    
    questions = InspectionQuestion.objects.filter(
        category_id=category_id,
        is_active=True
    )
    
    # Exclude questions already in template
    if template_id:
        existing_question_ids = TemplateQuestion.objects.filter(
            template_id=template_id
        ).values_list('question_id', flat=True)
        questions = questions.exclude(id__in=existing_question_ids)
    
    questions_data = questions.values('id', 'question_code', 'question_text')
    
    return JsonResponse({'questions': list(questions_data)})



@login_required
def get_template_inspection_type(request):

    template_id = request.GET.get('template_id')

    if not template_id:
        return JsonResponse({'success': False})

    try:
        template = InspectionTemplate.objects.get(id=template_id)

        return JsonResponse({
            'success': True,
            'inspection_type': template.inspection_type
        })

    except InspectionTemplate.DoesNotExist:
        return JsonResponse({'success': False})
    

@login_required
def no_answers_list(request):
    """
    Separate page showing all questions answered 'No'
    across all inspections with filters
    """

    # Handle POST request for assignment
    if request.method == 'POST' and request.POST.get('action') == 'assign_responses':
        return handle_response_assignment(request)

    # Base queryset - all "No" responses
    no_responses = InspectionResponse.objects.filter(
        answer='No'
    ).select_related(
        'submission',
        'submission__schedule',
        'submission__schedule__assigned_to',
        'submission__submitted_by',
        'question',
        'question__category',
        'assigned_to',
        'assigned_by',
        'converted_to_hazard'
    ).prefetch_related('submission__schedule__plants')

    # ---------------------------------------------------------------
    # USER-BASED FILTERING — FIXED LOGIC
    # ---------------------------------------------------------------
    user_plants = request.user.get_all_plants()
    if user_plants:
        no_responses = no_responses.filter(
            Q(submission__schedule__plants__in=user_plants) |
            Q(submission__schedule__plants__isnull=True)
        ).distinct()
    else:
        no_responses = no_responses.none()
    is_admin = request.user.is_superuser or getattr(request.user, 'can_access_inspection_module', False)

    if not is_admin:
        # Responsible person (HOD or any assigned user):
        # Show ONLY items that are assigned to them
        no_responses = no_responses.filter(assigned_to=request.user)

    # ---------------------------------------------------------------
    # FILTERS (from GET params)
    # ---------------------------------------------------------------
    plant_id = request.GET.get('plant')
    category_id = request.GET.get('category')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    priority = request.GET.get('priority')
    search = request.GET.get('search')

    if plant_id:
        no_responses = no_responses.filter(
            submission__schedule__plants__id=plant_id
        )
    else:
        no_responses = no_responses.filter(
            Q(submission__schedule__plants__in=user_plants) |
            Q(submission__schedule__plants__isnull=True)
        ).distinct()

    if category_id:
        no_responses = no_responses.filter(
            question__category_id=category_id
        )

    if date_from:
        no_responses = no_responses.filter(
            answered_at__gte=date_from
        )

    if date_to:
        no_responses = no_responses.filter(
            answered_at__lte=date_to
        )

    if priority == 'critical':
        no_responses = no_responses.filter(
            question__is_critical=True
        )

    if search:
        no_responses = no_responses.filter(
            Q(submission__schedule__schedule_code__icontains=search) |
            Q(submission__submitted_by__first_name__icontains=search) |
            Q(submission__submitted_by__last_name__icontains=search) |
            Q(question__question_text__icontains=search) |
            Q(question__question_code__icontains=search) |
            Q(remarks__icontains=search)
        )

    no_responses = no_responses.order_by('-answered_at')

    # ---------------------------------------------------------------
    # STATISTICS
    # ---------------------------------------------------------------
    total_no_answers = no_responses.count()
    critical_no_answers = no_responses.filter(question__is_critical=True).count()
    converted_hazards_count = no_responses.filter(converted_to_hazard__isnull=False).count()

    # Group by category for summary
    from django.db.models import Count
    category_summary = no_responses.values(
        'question__category__category_name',
        'question__category__id'
    ).annotate(
        count=Count('id')
    ).order_by('-count')

    # ---------------------------------------------------------------
    # PAGINATION
    # ---------------------------------------------------------------
    paginator = Paginator(no_responses, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ---------------------------------------------------------------
    # AVAILABLE USERS (for assignment dropdown — admin only)
    # ---------------------------------------------------------------
    available_users = User.objects.none()
    if is_admin:
        # Get unique plant IDs from the filtered no_responses queryset
        response_plants_qs = no_responses.filter(
            submission__schedule__plants__isnull=False
        ).values_list(
            'submission__schedule__plants__id',
            flat=True
        ).distinct()

        # If a specific plant is selected, use only that
        if plant_id:
            response_plants_qs = [int(plant_id)]

        # Only include active users who belong to the inspection plants
        available_users = User.objects.filter(
            is_active=True,
            is_superuser=False,
            plant__id__in=response_plants_qs
        ).select_related('department', 'role', 'plant'
        ).order_by('first_name', 'last_name')

    # For filters
    user_plants = request.user.get_all_plants()
    if request.user.is_superuser:
        plants = Plant.objects.filter(is_active=True)
    else:
        plants = Plant.objects.filter(id__in=[p.id for p in user_plants],is_active=True)
    categories = InspectionCategory.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'total_no_answers': total_no_answers,
        'critical_no_answers': critical_no_answers,
        'converted_hazards_count': converted_hazards_count,
        'category_summary': category_summary,
        'plants': plants,
        'categories': categories,
        'selected_plant': plant_id,
        'selected_category': category_id,
        'date_from': date_from,
        'date_to': date_to,
        'selected_priority': priority,
        'search': search,
        'available_users': available_users,
        'is_admin': is_admin,                  # Controls which view to show in template
        'current_user': request.user,
    }

    return render(request, 'inspections/no_answers_list.html', context)


def handle_response_assignment(request):
    """Helper function to handle the assignment logic"""
    
    # Check permission
    if not (request.user.is_superuser or request.user.can_access_inspection_module):
        messages.error(request, 'Only safety managers can assign non-compliances!')
        return redirect('inspections:no_answers_list')
    
    try:
        # Get form data
        selected_responses = request.POST.get('selected_responses', '')
        assigned_to_id = request.POST.get('assigned_to')
        assignment_remarks = request.POST.get('assignment_remarks', '').strip()
        
        # Validate
        if not selected_responses:
            messages.error(request, 'Please select at least one non-compliant item!')
            return redirect('inspections:no_answers_list')
        
        if not assigned_to_id:
            messages.error(request, 'Please select a person to assign these items to!')
            return redirect('inspections:no_answers_list')
        
        # Parse selected IDs
        response_ids = [int(id.strip()) for id in selected_responses.split(',') if id.strip()]
        
        if not response_ids:
            messages.error(request, 'No valid items selected!')
            return redirect('inspections:no_answers_list')
        
        # Get assigned user - verify they are from allowed plants
        assigned_to = get_object_or_404(User, pk=assigned_to_id, is_active=True)
        
        # For non-admin users, verify the assigned user belongs to their plant
        if not request.user.is_superuser and not request.user.can_access_inspection_module:
            user_plants = request.user.get_all_plants()
            if assigned_to.plant and assigned_to.plant not in user_plants:
                messages.error(request, 'You can only assign to users from your plants!')
                return redirect('inspections:no_answers_list')
        
        # Get responses
        responses = InspectionResponse.objects.filter(
            id__in=response_ids,
            answer='No'
        )
        
        # Filter only unassigned, unconverted responses
        valid_responses = responses.filter(
            assigned_to__isnull=True,
            converted_to_hazard__isnull=True
        )
        response_list = list(valid_responses)
        
        if not response_list:
            messages.error(request, 'All selected items are already assigned or converted!')
            return redirect('inspections:no_answers_list')
        
        assigned_count = len(response_list)
        
        # Bulk assign using transaction
        from django.db import transaction
        with transaction.atomic():
            for response in response_list:
                response.assigned_to = assigned_to
                response.assigned_by = request.user
                response.assigned_at = timezone.now()
                response.assignment_remarks = assignment_remarks
                response.save()

        # Send notification (use first response or loop)
        
        
        # Send notification
        try:
            from apps.notifications.services import NotificationService
            first_response = response_list[0]
            NotificationService.notify(
                content_object=first_response,
                notification_type='INSPECTION_NONCOMPLIANCE_ASSIGNED',
                module='INSPECTION_NONCOMPLIANCE',
                extra_recipients=[assigned_to]
            )
        except Exception as e:
            print(f"Notification error: {e}")
        
        from django.utils.safestring import mark_safe
        messages.success(
            request,
            mark_safe(
                f'<strong>✅ Assignment Successful!</strong><br>'
                f'<strong>{assigned_count}</strong> non-compliant item(s) assigned to '
                f'<strong>{assigned_to.get_full_name()}</strong>'
            )
        )
        
    except Exception as e:
        # print(f"Error in assignment: {e}")
        messages.error(request, f'Error assigning items: {str(e)}')
    
    return redirect('inspections:no_answers_list')

@login_required
def no_answers_by_question(request):
    """
    Show aggregated view: which questions get 'No' most frequently
    """
    
    # Get all "No" responses grouped by question
    from django.db.models import Count
    
    question_stats = InspectionResponse.objects.filter(
        answer='No'
    ).values(
        'question__id',
        'question__question_code',
        'question__question_text',
        'question__category__category_name',
        'question__is_critical'
    ).annotate(
        no_count=Count('id')
    ).order_by('-no_count')
    
    # Apply filters if needed
    category_id = request.GET.get('category')
    if category_id:
        question_stats = question_stats.filter(
            question__category_id=category_id
        )
    
    # Pagination
    paginator = Paginator(question_stats, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = InspectionCategory.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category_id,
    }
    
    return render(request, 'inspections/no_answers_by_question.html', context)



@login_required
def convert_no_answer_to_hazard(request, response_id):
    """
    Convert an inspection 'No' answer into a hazard report via AJAX modal.
    Only the assigned person can convert.
    """
    from apps.hazards.models import Hazard, HazardPhoto
    import json

    response = InspectionResponse.objects.select_related(
    'submission',
    'submission__schedule',
    'question',
    'question__category',
    'assigned_to',
    'assigned_by'
    ).prefetch_related(
        'submission__schedule__plants',
        'submission__schedule__zones',
        'submission__schedule__locations',
        'submission__schedule__sublocations'
    ).get(pk=response_id, answer='No')

    # Only assigned person can convert
    if request.user != response.assigned_to:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Only the assigned person can convert this item!'}, status=403)
        messages.error(request, 'Only the assigned person can convert this item!')
        return redirect('inspections:no_answers_list')

    # Already converted
    if response.converted_to_hazard:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'already_converted': True,
                'hazard_number': response.converted_to_hazard.report_number,
                'hazard_id': response.converted_to_hazard.id
            })
        return redirect('hazards:hazard_detail', pk=response.converted_to_hazard.id)

    # Not assigned yet
    if not response.assigned_to:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'This item must be assigned before converting!'}, status=400)
        messages.error(request, 'This item must be assigned before converting!')
        return redirect('inspections:no_answers_list')

    if request.method == 'POST':
        try:
            schedule = response.submission.schedule

            hazard = Hazard()

            # Reporter
            hazard.reported_by = request.user
            hazard.reporter_name = request.user.get_full_name()
            hazard.reporter_email = request.user.email
            hazard.reporter_phone = getattr(request.user, 'phone', '') or ''

            # Hazard fields from POST
            hazard.hazard_type = request.POST.get('hazard_type', 'UC')
            hazard.hazard_category = request.POST.get('hazard_category', 'other')
            hazard.severity = request.POST.get('severity', 'high' if response.question.is_critical else 'medium')

            # Location from schedule
            hazard.plant = schedule.plants.first()
            hazard.zone = schedule.zones.first()
            hazard.location = schedule.locations.first()
            hazard.sublocation = schedule.sublocations.first()
            specific_location = request.POST.get('specific_location', '').strip()
            if specific_location:
                response.specific_location = specific_location
                response.save(update_fields=['specific_location'])

            # Title
            category_name = response.question.category.category_name
            hazard.hazard_title = f"Inspection Non-Compliance: {category_name} - {response.question.question_code}"

            # Description
            description_parts = [
                f"Source: Inspection {schedule.schedule_code}",
                f"Inspection Date: {schedule.scheduled_date.strftime('%d %B %Y')}",
                f"Inspector: {response.submission.submitted_by.get_full_name()}",
                f"Question Code: {response.question.question_code}",
                f"Question: {response.question.question_text}",
                f"Category: {category_name}",
            ]
            if response.specific_location:
                description_parts.append(f"Specific Location: {response.specific_location}")
            if response.question.reference_standard:
                description_parts.append(f"Reference Standard: {response.question.reference_standard}")
            if response.remarks:
                description_parts.append(f"Inspector Remarks: {response.remarks}")
            if response.assignment_remarks:
                description_parts.append(f"Assignment Notes: {response.assignment_remarks}")

            hazard.hazard_description = "\n\n".join(description_parts)
            hazard.immediate_action = request.POST.get('immediate_action', '')

            # Dates
            hazard.incident_datetime = response.answered_at or schedule.closed_at or timezone.now()
            hazard.status = 'REPORTED'
            hazard.approval_status = 'PENDING'

            # Deadline
            severity_days = {'low': 30, 'medium': 15, 'high': 7, 'critical': 1}
            hazard.action_deadline = timezone.now().date() + timezone.timedelta(
                days=severity_days.get(hazard.severity, 15)
            )

            hazard.save()

            # Copy photo
            if response.photo:
                try:
                    HazardPhoto.objects.create(
                        hazard=hazard,
                        photo=response.photo,
                        photo_type='evidence',
                        description=f'Photo from inspection {schedule.schedule_code} - {response.question.question_code}',
                        uploaded_by=request.user
                    )
                except Exception as e:
                    print(f"Photo copy error: {e}")

            # Link response → hazard
            response.converted_to_hazard = hazard
            response.save(update_fields=['converted_to_hazard'])

            # Notification
            try:
                NotificationService.notify(
                    content_object=hazard,
                    notification_type='HAZARD_REPORTED',
                    module='HAZARD'
                )
            except Exception as e:
                print(f"Notification error: {e}")

            # Always return JSON — this view is called via AJAX only
            from django.urls import reverse
            try:
                hazard_url = reverse('hazards:hazard_detail', kwargs={'pk': hazard.pk})
            except Exception:
                hazard_url = f"/hazards/{hazard.id}/"

            return JsonResponse({
                'success': True,
                'hazard_number': hazard.report_number,
                'hazard_id': hazard.id,
                'hazard_url': hazard_url,
                'message': f'Hazard {hazard.report_number} created successfully!'
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            # print(f"[convert_no_answer_to_hazard] ERROR: {error_msg}")
            # Always return JSON for AJAX calls
            return JsonResponse({
                'success': False,
                'error': f'Server error: {error_msg}'
            }, status=500)

    # GET - not used anymore, redirect back
    return redirect('inspections:no_answers_list')



class InspectionDashboardView(LoginRequiredMixin, TemplateView):
    """
    Advanced dashboard with actionable insights, including overdue alerts,
    top non-compliances chart, and paginated results. Data is filtered
    based on user's assigned plants.
    """
    template_name = 'inspections/pre_inspection_dashboard.html'

    def get_context_data(self, **kwargs):
        """
        Fetches and prepares all the data needed for the advanced dashboard,
        respecting user's plant assignments.
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()

        selected_plant = self.request.GET.get('plant', '')
        selected_zone = self.request.GET.get('zone', '')
        selected_location = self.request.GET.get('location', '')
        selected_sublocation = self.request.GET.get('sublocation', '')
        selected_department = self.request.GET.get('department', '')
        selected_templates = [value for value in self.request.GET.getlist('template') if value]
        selected_template = selected_templates[0] if len(selected_templates) == 1 else ''
        selected_month = self.request.GET.get('month', '')

        # --- 1. USER ACCESS CONTROL (Determine accessible plants) ---
        # This logic is adapted from your EnvironmentalDashboardView
        if user.is_superuser or user.is_staff or getattr(user, 'is_admin_user', False):
            # Admin, staff, or superuser can see data from all active plants
            accessible_plants = Plant.objects.filter(is_active=True)
        else:
            # Standard users see data only from their assigned plants
            assigned = user.assigned_plants.filter(is_active=True)
            if not assigned.exists() and getattr(user, 'plant', None):
                # Fallback to the user's primary plant if no many-to-many assignment
                accessible_plants = Plant.objects.filter(id=user.plant.id, is_active=True)
            else:
                accessible_plants = assigned

        is_admin_user = user.is_superuser or user.is_staff or getattr(user, 'is_admin_user', False)

        # --- 2. Build a filtered base schedule queryset for the whole dashboard ---
        schedules_qs = InspectionSchedule.objects.select_related(
            'template', 'assigned_to', 'department'
        ).prefetch_related(
            'plants', 'zones', 'locations', 'sublocations'
        )

        if not is_admin_user:
            schedules_qs = schedules_qs.filter(
                Q(plants__in=accessible_plants) | Q(plants__isnull=True)
            )

        schedules_qs = schedules_qs.distinct()

        if selected_month:
            try:
                year, month = map(int, selected_month.split('-'))
                schedules_qs = schedules_qs.filter(
                    scheduled_date__year=year,
                    scheduled_date__month=month
                )
                context['selected_month_label'] = datetime(year, month, 1).strftime('%B %Y')
            except (ValueError, TypeError):
                selected_month = ''

        if selected_plant:
            schedules_qs = schedules_qs.filter(plants__id=selected_plant)
        if selected_zone:
            schedules_qs = schedules_qs.filter(zones__id=selected_zone)
        if selected_location:
            schedules_qs = schedules_qs.filter(locations__id=selected_location)
        if selected_sublocation:
            schedules_qs = schedules_qs.filter(sublocations__id=selected_sublocation)
        if selected_department:
            schedules_qs = schedules_qs.filter(department_id=selected_department)
        template_filter_qs = schedules_qs.distinct()
        if selected_templates:
            schedules_qs = schedules_qs.filter(template_id__in=selected_templates)

        schedules_qs = schedules_qs.distinct()

        submissions = (
            InspectionSubmission.objects
            .select_related('schedule', 'schedule__template', 'submitted_by')
            .prefetch_related('schedule__plants')
            .filter(schedule__in=schedules_qs)
            .order_by('-submitted_at')
            .distinct()
        )

        # --- 3. Top Statistics Cards Data (Filtered) ---
        total_inspections = submissions.count()
        current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        context['total_inspections'] = total_inspections
        context['open_schedules'] = schedules_qs.filter(status__in=['SCHEDULED', 'IN_PROGRESS', 'OVERDUE']).count()
        context['this_month_inspections'] = (
            submissions.count() if selected_month else submissions.filter(submitted_at__gte=current_month_start).count()
        )
        context['this_month_label'] = context.get('selected_month_label', 'This Month')

        # New Stat: Average Compliance Score (Calculated from filtered submissions)
        if total_inspections > 0:
            avg = submissions.aggregate(avg_score=Avg('compliance_score'))['avg_score']
            context['average_compliance_score'] = round(avg, 2) if avg else 0
        else:
            context['average_compliance_score'] = 0
        context['overdue_inspections'] = (
            schedules_qs.filter(status='OVERDUE')
            .select_related('assigned_to')
            .prefetch_related('plants')
            .order_by('-due_date')[:5]
        )

        plant_summary = list(
            schedules_qs.annotate(
                display_plant_name=Coalesce('plants__name', Value('Unassigned'))
            ).values(
                'plants__id',
                'display_plant_name'
            ).annotate(
                total=Count('id', distinct=True),
                closed_count=Count('id', filter=Q(status='CLOSED'), distinct=True),
                pending_count=Count('id', filter=Q(status='SCHEDULED'), distinct=True),
                in_progress_count=Count('id', filter=Q(status='IN_PROGRESS'), distinct=True),
                cancelled_count=Count('id', filter=Q(status='CANCELLED'), distinct=True),
                overdue_count=Count('id', filter=Q(status='OVERDUE'), distinct=True),
                late_close_count=Count('id', filter=Q(status='LATE_CLOSE'), distinct=True),
            ).order_by('-total', 'display_plant_name')
        )

        top_plant = plant_summary[0] if plant_summary else None
        plant_status_rows = []
        for item in plant_summary:
            total_count = item['total'] or 0
            closed_percent = round((item['closed_count'] / total_count) * 100) if total_count else 0
            plant_status_rows.append({
                'plant_name': item['display_plant_name'],
                'closed_count': item['closed_count'],
                'pending_count': item['pending_count'],
                'in_progress_count': item['in_progress_count'],
                'cancelled_count': item['cancelled_count'],
                'overdue_count': item['overdue_count'],
                'late_close_count': item['late_close_count'],
                'total': total_count,
                'closed_percent': closed_percent,
            })
        context['plant_chart_labels'] = json.dumps([item['display_plant_name'] for item in plant_summary])
        context['plant_closed_data'] = json.dumps([item['closed_count'] for item in plant_summary])
        context['plant_pending_data'] = json.dumps([item['pending_count'] for item in plant_summary])
        context['plant_in_progress_data'] = json.dumps([item['in_progress_count'] for item in plant_summary])
        context['plant_cancelled_data'] = json.dumps([item['cancelled_count'] for item in plant_summary])
        context['plant_overdue_data'] = json.dumps([item['overdue_count'] for item in plant_summary])
        context['plant_late_close_data'] = json.dumps([item['late_close_count'] for item in plant_summary])
        context['plant_chart_data'] = bool(plant_summary)
        context['plant_status_rows'] = plant_status_rows
        context['plant_summary'] = {
            'plants_covered': len(plant_summary),
            'top_plant_name': top_plant['display_plant_name'] if top_plant else 'N/A',
            'top_plant_total': top_plant['total'] if top_plant else 0,
            'top_plant_overdue': top_plant['overdue_count'] if top_plant else 0,
        }

        # --- 5. Top Non-Compliant Questions Chart Data (Filtered) ---
        top_non_compliant = (
            InspectionResponse.objects.filter(submission__in=submissions, answer='No')
            .values('question__question_text')
            .annotate(no_count=Count('id'))
            .order_by('-no_count')[:5]
        )
        chart_labels = [i['question__question_text'] for i in top_non_compliant]
        chart_data = [i['no_count'] for i in top_non_compliant]

        # Pass to context in JSON format for JavaScript
        context['non_compliant_labels'] = json.dumps(chart_labels)
        context['non_compliant_data'] = json.dumps(chart_data)

        # --- 6. Paginated Inspections Table Data (Already filtered via `submissions` queryset) ---
        paginator = Paginator(submissions, 10)  # 10 items per page
        page_number_from_url = self.request.GET.get('page')

        try:
            # get_page handles invalid inputs (like 'abc', '', None)
            page_obj = paginator.get_page(page_number_from_url)
        except EmptyPage:
            # If page number is valid but out of range, show the first page.
            page_obj = paginator.get_page(1)

        context['page_obj'] = page_obj

        plants_qs = accessible_plants.order_by('name').distinct()

        zones_qs = Zone.objects.filter(is_active=True)
        if not is_admin_user:
            zones_qs = zones_qs.filter(plant__in=accessible_plants)
        if selected_plant:
            zones_qs = zones_qs.filter(plant_id=selected_plant)

        locations_qs = Location.objects.filter(is_active=True)
        if not is_admin_user:
            locations_qs = locations_qs.filter(zone__plant__in=accessible_plants)
        if selected_zone:
            locations_qs = locations_qs.filter(zone_id=selected_zone)
        elif selected_plant:
            locations_qs = locations_qs.filter(zone__plant_id=selected_plant)

        sublocations_qs = SubLocation.objects.filter(is_active=True)
        if not is_admin_user:
            sublocations_qs = sublocations_qs.filter(location__zone__plant__in=accessible_plants)
        if selected_location:
            sublocations_qs = sublocations_qs.filter(location_id=selected_location)
        elif selected_zone:
            sublocations_qs = sublocations_qs.filter(location__zone_id=selected_zone)
        elif selected_plant:
            sublocations_qs = sublocations_qs.filter(location__zone__plant_id=selected_plant)

        template_qs = InspectionTemplate.objects.filter(schedules__in=template_filter_qs).distinct().order_by('template_name')
        department_qs = Department.objects.filter(inspection_schedules__in=schedules_qs).distinct().order_by('name')

        context['plants'] = plants_qs
        context['zones'] = zones_qs.order_by('name').distinct()
        context['locations'] = locations_qs.order_by('name').distinct()
        context['sublocations'] = sublocations_qs.order_by('name').distinct()
        context['all_templates'] = template_qs
        context['all_departments'] = department_qs
        context['month_options'] = [{
            'value': (today - timedelta(days=i * 30)).strftime('%Y-%m'),
            'label': (today - timedelta(days=i * 30)).strftime('%B %Y')
        } for i in range(12)]

        context.update({
            'selected_plant': selected_plant,
            'selected_zone': selected_zone,
            'selected_location': selected_location,
            'selected_sublocation': selected_sublocation,
            'selected_department': selected_department,
            'selected_template': selected_template,
            'selected_templates': selected_templates,
            'selected_month': selected_month,
        })

        if selected_plant:
            plant_obj = Plant.objects.filter(pk=selected_plant).first()
            if plant_obj:
                context['selected_plant_name'] = plant_obj.name
        if selected_zone:
            zone_obj = Zone.objects.filter(pk=selected_zone).first()
            if zone_obj:
                context['selected_zone_name'] = zone_obj.name
        if selected_location:
            location_obj = Location.objects.filter(pk=selected_location).first()
            if location_obj:
                context['selected_location_name'] = location_obj.name
        if selected_sublocation:
            sublocation_obj = SubLocation.objects.filter(pk=selected_sublocation).first()
            if sublocation_obj:
                context['selected_sublocation_name'] = sublocation_obj.name
        if selected_department:
            department_obj = Department.objects.filter(pk=selected_department).first()
            if department_obj:
                context['selected_department_name'] = department_obj.name
        if selected_templates:
            selected_template_objects = list(
                InspectionTemplate.objects.filter(pk__in=selected_templates)
                .order_by('template_name')
                .values_list('template_name', flat=True)
            )
            if selected_template_objects:
                context['selected_template_names'] = selected_template_objects
                if len(selected_template_objects) == 1:
                    context['selected_template_name'] = selected_template_objects[0]
                else:
                    context['selected_template_name'] = ', '.join(selected_template_objects)

        total_template_options = template_qs.count()
        if not selected_templates or (total_template_options and len(selected_templates) >= total_template_options):
            context['selected_template_display'] = 'All Templates'
        else:
            context['selected_template_display'] = context.get('selected_template_name', 'All Templates')

        context['has_active_filters'] = any([
            selected_plant,
            selected_zone,
            selected_location,
            selected_sublocation,
            selected_department,
            bool(selected_templates),
            selected_month,
        ])

        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['querystring'] = querydict.urlencode()

        return context




@login_required
def schedule_clone(request, pk):
    """
    Directly clones an inspection schedule upon request.

    It creates a new schedule with the same details but generates a new, unique
    schedule_code before saving. It then redirects to the list view.
    """
    # Fetch the original schedule to copy from.
    original_schedule = get_object_or_404(
        InspectionSchedule.objects.prefetch_related(
            'plants', 'zones', 'locations', 'sublocations', 'assigned_users'
        ),
        pk=pk
    )
    
    original_code = original_schedule.schedule_code
    new_schedule = _clone_schedule_as_scheduled(original_schedule)
    
    # Trigger a notification for the newly created schedule.
    NotificationService.notify(
        content_object=new_schedule,
        notification_type='INSPECTION_SCHEDULE',
        module='INSPECTION'
    )
    
    # Create a success message for the user.
    messages.success(
        request,
        f'Schedule "{original_code}" was successfully cloned! New Schedule Code: {new_schedule.schedule_code}'
    )
    
    # Redirect the user back to the list of schedules.
    return redirect('inspections:schedule_detail', pk=new_schedule.pk)


@login_required
def schedule_restart(request, pk):
    """Restart an overdue inspection as a fresh schedule and close it as close late on submission."""
    original_schedule = get_object_or_404(
        InspectionSchedule.objects.select_related('assigned_to', 'assigned_by').prefetch_related(
            'plants', 'zones', 'locations', 'sublocations', 'assigned_users'
        ),
        pk=pk
    )

    if original_schedule.status != 'OVERDUE':
        messages.error(request, 'Only overdue inspections can be restarted.')
        return redirect('inspections:schedule_detail', pk=pk)

    if not (
        request.user == original_schedule.assigned_to or
        request.user.is_superuser or
        request.user.is_admin_user
    ):
        messages.error(request, 'You are not authorized to restart this inspection.')
        return redirect('inspections:schedule_detail', pk=pk)

    original_code = original_schedule.schedule_code
    original_notes = original_schedule.assignment_notes or ''
    restarted_schedule = _clone_schedule_as_scheduled(
        original_schedule,
        assignment_notes=f"[RESTARTED_FROM:{original_code}]\n{original_notes}".strip()
    )

    NotificationService.notify(
        content_object=restarted_schedule,
        notification_type='INSPECTION_SCHEDULE',
        module='INSPECTION'
    )

    messages.success(
        request,
        f'Inspection "{original_code}" restarted successfully as {restarted_schedule.schedule_code}. Submit it to close as Close Late.'
    )
    return redirect('inspections:schedule_detail', pk=restarted_schedule.pk)
