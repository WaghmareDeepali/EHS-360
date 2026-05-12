# apps/inspections/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import (
    InspectionCategory,
    InspectionQuestion,
    InspectionTemplate,
    TemplateQuestion,
    InspectionSchedule,
    TemplateAutoScheduleConfig
)
from apps.accounts.models import User
from apps.organizations.models import Plant, Zone, Location, SubLocation, Department


class InspectionCategoryForm(forms.ModelForm):
    class Meta:
        model = InspectionCategory
        fields = [
            'category_name',
            'category_code',
            'description',
            'is_active'
        ]
        widgets = {
            'category_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name (e.g., Fire Safety)'
            }),
            'category_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., FS, ES, HK',
                'maxlength': '10'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe this category'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean_category_code(self):
        code = self.cleaned_data.get('category_code')
        if code:
            code = code.upper()
            existing = InspectionCategory.objects.filter(category_code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(f'Category code "{code}" already exists.')
        return code


class InspectionQuestionForm(forms.ModelForm):
    class Meta:
        model = InspectionQuestion
        fields = [
            'category',
            'question_text',
            'question_type',
            'is_remarks_mandatory',
            'is_photo_required',
            'is_critical',
            'auto_generate_finding',
            'weightage',
            'reference_standard',
            'guidance_notes',
            'is_active'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'question_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter the inspection question'
            }),
            'question_type': forms.Select(
                attrs={'class': 'form-control'},
                choices=[('', 'Select Question Type')]
            ),
            'weightage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01',
                'value': '1.00'
            }),
            'reference_standard': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., OSHA 1910.36, IS 2309'
            }),
            'guidance_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional guidance for inspectors'
            }),
            'is_remarks_mandatory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_photo_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_critical': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_generate_finding': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = "Select Category"
        self.fields['question_type'].choices = (
            [('', 'Select Question Type')] +
            list(self.fields['question_type'].choices)
        )
        self.fields['question_type'].initial = ''


class InspectionTemplateForm(forms.ModelForm):
    class Meta:
        model = InspectionTemplate
        fields = [
            'template_name',
            'inspection_type',
            'description',
            'applicable_plants',
            'applicable_departments',
            'min_compliance_score',
            'is_active'
        ]
        widgets = {
            'template_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Monthly Plant Safety Inspection'
            }),
            'inspection_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the purpose of this inspection'
            }),
            'applicable_plants': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input',
            }),
            'applicable_departments': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input',
            }),
            'min_compliance_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01',
                'value': '80.00'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inspection_type'].choices = (
            [('', 'Select Inspection Type')] +
            [c for c in self.fields['inspection_type'].choices if c[0] != '']
        )


class TemplateQuestionForm(forms.ModelForm):
    class Meta:
        model = TemplateQuestion
        fields = ['question', 'section_name', 'is_mandatory']
        widgets = {
            'question': forms.Select(attrs={'class': 'form-control'}),
            'section_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional: Section name'
            }),
            'is_mandatory': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['question'].empty_label = "Select Question"


class BulkAddQuestionsForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=InspectionCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_bulk_category'
        }),
        label="Filter by Category"
    )
    questions = forms.ModelMultipleChoiceField(
        queryset=InspectionQuestion.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select Questions"
    )
    section_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional section name for selected questions'
        }),
        label="Section Name (Optional)"
    )

    def __init__(self, *args, **kwargs):
        template = kwargs.pop('template', None)
        super().__init__(*args, **kwargs)
        if template:
            existing_question_ids = template.template_questions.values_list(
                'question_id', flat=True
            )
            self.fields['questions'].queryset = InspectionQuestion.objects.filter(
                is_active=True
            ).exclude(id__in=existing_question_ids)


class InspectionScheduleForm(forms.ModelForm):
    """
    Updated schedule form — plants/zones/locations/sublocations
    are handled via checkboxes in the template (not form fields).
    assigned_users is also checkbox-based via AJAX.
    Only non-location fields are here.
    """

    # Checkbox to enable auto monthly schedule
    enable_auto_schedule = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_enable_auto_schedule'}),
        label="Enable Auto Schedule",
        help_text="Automatically create this schedule on 1st of every month"
    )

    due_date_offset_days = forms.IntegerField(
        required=False,
        initial=7,
        min_value=1,
        # max_value=60,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_due_date_offset_days',
            'placeholder': 'Days after scheduled date'
        }),
        label="Due Date Offset (days)",
        help_text="For auto-schedule: due date = 1st of month + this many days"
    )

    class Meta:
        model = InspectionSchedule
        fields = [
            'template',
            'department',
            'scheduled_date',
            'due_date',
            'scheduled_end_date',
            'assignment_notes',
        ]
        widgets = {
            'template': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'scheduled_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'scheduled_end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'assignment_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special instructions for the inspector'
            })
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['template'].queryset = InspectionTemplate.objects.filter(
            is_active=True
        )
        self.fields['template'].empty_label = "Select Inspection Template"
        self.fields['department'].empty_label = "Select Department (Optional)"
        self.fields['department'].required = False

        # scheduled_date not required when auto_schedule enabled
        # (handled in clean)
        self.fields['scheduled_date'].required = False
        self.fields['due_date'].required = False
        self.fields['scheduled_end_date'].required = False

    def clean(self):
        cleaned_data = super().clean()
        enable_auto = cleaned_data.get('enable_auto_schedule')
        scheduled_date = cleaned_data.get('scheduled_date')
        due_date = cleaned_data.get('due_date')
        scheduled_end_date = cleaned_data.get('scheduled_end_date')

        if not enable_auto:
            # Manual schedule — dates are required
            if not scheduled_date:
                self.add_error('scheduled_date', 'Scheduled date is required.')
            if not due_date:
                self.add_error('due_date', 'Due date is required.')
            if scheduled_date and due_date and due_date < scheduled_date:
                self.add_error('due_date','Due date cannot be before scheduled date.')

            if (due_date and scheduled_end_date and scheduled_end_date < due_date):
                self.add_error('scheduled_end_date', 'Scheduled end date cannot be before due date.')

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)

        enable_auto = self.cleaned_data.get('enable_auto_schedule')
        offset_days = self.cleaned_data.get('due_date_offset_days')

        if commit:
            instance.save()

        # ✅ HANDLE AUTO SCHEDULE CONFIG CREATION
        if enable_auto:
            from apps.inspections.models import TemplateAutoScheduleConfig

            config, created = TemplateAutoScheduleConfig.objects.get_or_create(
                template=instance.template,
                created_by=self.user,
                defaults={
                    'due_date_offset_days': offset_days or 7,
                    'is_active': True
                }
            )

            # You will assign plants/zones/users in view
            instance.auto_schedule_config = config
            instance.save()

        return instance


class QuestionFilterForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=InspectionCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    question_type = forms.ChoiceField(
        choices=[('', 'All Types')] + InspectionQuestion.QUESTION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_critical = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ('', 'All Questions'),
                ('true', 'Critical Only'),
                ('false', 'Non-Critical')
            ],
            attrs={'class': 'form-control'}
        )
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search questions...'
        })
    )