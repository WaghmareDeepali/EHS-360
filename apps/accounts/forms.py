from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm as BaseUserChangeForm
from .models import User,Role
from apps.organizations.models import Plant, Zone, Location, SubLocation, Department

class UserCreationFormCustom(UserCreationForm):
    """Custom User Creation Form with all fields"""
    
    role = forms.ModelChoiceField(        
        queryset=Role.objects.all(),
        empty_label="Select Role",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'username', 'employee_id', 'password1', 'password2',
            'date_of_birth', 'gender', 'employment_type', 
            'job_title', 'date_joined_company',
            'role', 'department',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_joined_company': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        
        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if field.widget.__class__.__name__ != 'CheckboxInput':
                field.widget.attrs['class'] = 'form-control'
        
        # Make email required
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

        self.fields['date_of_birth'].required = False
        self.fields['date_joined_company'].required = False
        if self.request:
            creator=self.request.user
            is_admin=creator.is_superuser or creator.is_admin_user or creator.has_permission('CAN_CREATE_USERS')

            if not is_admin:
                self.fields['role'].querset=Role.objects.none()
                self.fields['role'].required=False
                self.fields['role'].widget.attrs['disabled']='disabled'
                self.fields['role'].help_text="Role Assignment is restricted to admins only"

                #restrict department to creator's own department 
                if creator.department:
                    self.fields['department'].queryset = Department.objects.filter(id=creator.department.id)
                else:
                    self.fields['department'].queryset=Department.objects.none()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered!!")
        return email


class UserUpdateForm(BaseUserChangeForm):
    """Custom User Update Form"""
    
    password = None
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'username', 'employee_id',
            'date_of_birth', 'gender', 'employment_type',
            'job_title', 'date_joined_company',
            'role', 'department', 'is_active',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_joined_company': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Pop the request object passed from the view.
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        
        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if field.widget.__class__.__name__ != 'CheckboxInput':
                field.widget.attrs['class'] = 'form-control'
        
        # Define required fields
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

        self.fields['date_of_birth'].required = False
        self.fields['date_joined_company'].required = False
        
        # --- NEW CODE STARTS HERE ---
        # Conditionally disable organization fields if the user is not an admin.
        # if self.request and not (self.request.user.is_superuser or self.request.user.is_admin_user):
        if self.request and not (self.request.user.is_superuser or self.request.user.is_admin_user
            or (self.request.user.role and self.request.user.role.name == 'SAFETY MANAGER')):
            # Disable Role and Department fields
            self.fields['role'].widget.attrs['disabled'] = 'disabled'
            self.fields['department'].widget.attrs['disabled'] = 'disabled'
            
            # Provide help text to inform the user why the field is disabled.
            self.fields['role'].help_text = "You do not have permission to change the role."
            self.fields['department'].help_text = "You do not have permission to change the department."
            self.fields['is_active'].widget.attrs['disabled'] = 'disabled'
        # --- NEW CODE ENDS HERE ---

    def clean_email(self):
        email = self.cleaned_data.get("email")
        qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This email is already registered!!')
        return email