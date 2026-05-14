from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from django.http import JsonResponse
from django.db.models import Q
from .models import User,Role,Permissions
from .forms import UserCreationFormCustom, UserUpdateForm
from apps.organizations.models import *
from apps.accidents.utils import get_incidents_for_user
from django.contrib.auth.forms import PasswordResetForm


class CustomLoginView(LoginView):
    """Custom Login View for EHS-360"""
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')

        if not username_or_email or not password:
            messages.error(request, 'Both fields are required.')
            return self.get(request, *args, **kwargs)

        if '@' in username_or_email:
            try:
                user_obj = User.objects.get(email__iexact=username_or_email)
                request.POST = request.POST.copy()
                request.POST['username'] = user_obj.username
            except User.DoesNotExist:
                messages.error(request, 'Invalid username/email or password.')
                return self.get(request, *args, **kwargs)

        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        user = self.request.user
        
        # If superuser (created via createsuperuser), redirect to Django admin
        if user.is_superuser:
            return '/admin/'
        
        # Otherwise redirect to dashboard
        return reverse_lazy('dashboards:home')
    
    def form_valid(self, form):
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        
        user = form.get_user()
        
        # ============================================
        # SINGLE SESSION: Delete all previous sessions
        # for this user before creating a new one
        # ============================================
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        for session in active_sessions:
            session_data = session.get_decoded()
            # _auth_user_id stores the logged-in user's PK
            if str(session_data.get('_auth_user_id')) == str(user.pk):
                session.delete()
        
        # Check if superuser
        if user.is_superuser:
            messages.success(
                self.request, 
                f'Welcome, {user.get_full_name() or user.username}! Redirecting to Admin Panel...'
            )
        else:
            messages.success(
                self.request, 
                f'Welcome back, {user.get_full_name() or user.username}!'
            )
        
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(
            self.request, 
            'Invalid username or password. Please try again.'
        )
        return super().form_invalid(form)

class ForgetPasswordView(View):
    template_name = 'accounts/forget_pass.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email')

        if not email:
            messages.error(request, "Please enter your registered email address.")
            return redirect('forget_password')
        
        if not User.objects.filter(email=email).exists():
            messages.error(request, "This email is not register")
            return redirect('accounts:forget-password')

        form = PasswordResetForm({'email': email})
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                from_email=None,
                email_template_name='accounts/password_reset_email.html',
                subject_template_name='accounts/password_reset_subject.txt',
            )

        messages.success(
            request,
            "If an account exists with this email, a password reset link has been sent."
        )
        return redirect('accounts:login')


class CustomLogoutView(LogoutView):
    """Custom Logout View"""
    next_page = 'accounts:login'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, 'You have been successfully logged out.')
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to require admin access"""
    
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or
            (user.role and user.role.name == 'ADMIN')
        )
    
    def handle_no_permission(self):
        messages.error(self.request, 'You do not have permission to access this page.')
        return redirect('dashboards:home')

class CanCreateUsersMixin(UserPassesTestMixin):
    def test_func(self):
        user=self.request.user
        return user.is_authenticated and(
            user.is_superuser or
            (user.role and user.role.name=='ADMIN') or
            user.can_create_users
        )
    def handle_no_permission(self):
        messages.error(self.request,'you do not have permission to create users.')
        return redirect('dashboards:home')

class ProfileView(LoginRequiredMixin, TemplateView):
    """User Profile View"""
    template_name = 'accounts/profile.html'
    login_url = 'accounts:login'
    
    def dispatch(self, request, *args, **kwargs):
        # Block superuser from accessing profile
        if request.user.is_superuser:
            messages.warning(request, 'Superadmin cannot access this page.')
            return redirect('/admin/')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


class UserListView(LoginRequiredMixin,CanCreateUsersMixin,ListView):
    """List all users - Only accessible by Admin"""
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        # Exclude superuser accounts
        queryset = User.objects.filter(is_superuser=False).select_related('role').order_by('-date_joined')

        # ============================================
        # Non-admin: show only users from their plants
        # ============================================
        user = self.request.user
        if not (user.is_superuser or user.is_admin_user):
            creator_plant_ids = list(user.assigned_plants.values_list('id', flat=True))
            if user.plant:
                creator_plant_ids.append(user.plant.id)
            queryset = queryset.filter(
                assigned_plants__id__in=creator_plant_ids
            ).distinct()

        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search)
            )

        role_id = self.request.GET.get('role')
        if role_id:
            queryset = queryset.filter(role_id=role_id)

        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        base_queryset = User.objects.filter(is_superuser=False)

        if not (user.is_superuser or user.is_admin_user):
            creator_plant_ids = list(user.assigned_plants.values_list('id', flat=True))
            if user.plant:
                creator_plant_ids.append(user.plant.id)

            base_queryset = base_queryset.filter(assigned_plants__id__in=creator_plant_ids).distinct()

        context['total_users'] = base_queryset.count()
        context['active_users'] = base_queryset.filter(is_active=True).count()
        context['inactive_users'] = base_queryset.filter(is_active=False).count()
        context['roles'] = Role.objects.all()

        context['search_query'] = self.request.GET.get('search', '')
        context['selected_role'] = self.request.GET.get('role', '')
        context['selected_status'] = self.request.GET.get('status', '')
        
        return context


class UserCreateView(LoginRequiredMixin, CanCreateUsersMixin, CreateView):
    """Create new user — accessible by Admin OR users with can_create_users permission"""
    model = User
    form_class = UserCreationFormCustom
    template_name = 'accounts/user_create.html'
    success_url = reverse_lazy('accounts:user_list')

    def get_form_kwargs(self):
        """Pass request to form so it can restrict fields based on creator"""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        creator = self.request.user
        is_admin = creator.is_superuser or creator.is_admin_user

        # Admin sees all plants, non-admin sees only their assigned plants
        if is_admin:
            context['all_plants'] = Plant.objects.filter(is_active=True).order_by('name')
        else:
            context['all_plants'] = creator.assigned_plants.filter(is_active=True).order_by('name')

        return context

    def form_valid(self, form):
        creator = self.request.user
        is_admin = creator.is_superuser or creator.is_admin_user

        user = form.save(commit=False)
        user.save()

        # ============================================
        # PLANT ASSIGNMENT
        # Admin → any plant | Non-admin → only their plants
        # ============================================
        assigned_plants = self.request.POST.getlist('assigned_plants')

        if not is_admin:
            # Security check: filter only plants the creator has access to
            creator_plant_ids = list(creator.assigned_plants.values_list('id', flat=True))
            if creator.plant:
                creator_plant_ids.append(creator.plant.id)
            
            # Only allow plants that belong to creator
            assigned_plants = [
                p for p in assigned_plants if int(p) in creator_plant_ids
            ]

        if assigned_plants:
            user.assigned_plants.set(assigned_plants)
            user.plant = Plant.objects.filter(id__in=assigned_plants).first()

        # ============================================
        # ZONE ASSIGNMENT
        # ============================================
        assigned_zones = self.request.POST.getlist('assigned_zones')

        if not is_admin:
            creator_zone_ids = list(creator.assigned_zones.values_list('id', flat=True))
            if creator.zone:
                creator_zone_ids.append(creator.zone.id)
            assigned_zones = [
                z for z in assigned_zones if int(z) in creator_zone_ids
            ]

        if assigned_zones:
            user.assigned_zones.set(assigned_zones)
            user.zone = Zone.objects.filter(id__in=assigned_zones).first()

        # ============================================
        # LOCATION ASSIGNMENT
        # ============================================
        assigned_locations = self.request.POST.getlist('assigned_locations')

        if not is_admin:
            creator_location_ids = list(creator.assigned_locations.values_list('id', flat=True))
            if creator.location:
                creator_location_ids.append(creator.location.id)
            assigned_locations = [
                l for l in assigned_locations if int(l) in creator_location_ids
            ]

        if assigned_locations:
            user.assigned_locations.set(assigned_locations)
            user.location = Location.objects.filter(id__in=assigned_locations).first()

        # ============================================
        # SUBLOCATION ASSIGNMENT
        # ============================================
        assigned_sublocations = self.request.POST.getlist('assigned_sublocations')

        if not is_admin:
            creator_sublocation_ids = list(creator.assigned_sublocations.values_list('id', flat=True))
            if creator.sublocation:
                creator_sublocation_ids.append(creator.sublocation.id)
            assigned_sublocations = [
                s for s in assigned_sublocations if int(s) in creator_sublocation_ids
            ]

        if assigned_sublocations:
            user.assigned_sublocations.set(assigned_sublocations)
            user.sublocation = SubLocation.objects.filter(id__in=assigned_sublocations).first()

        user.save()

        # Auto-sync permissions if role assigned
        if user.role:
            updated = user.sync_permissions_to_flags()
            messages.info(self.request, f'Synced {updated} permissions from {user.role.name} role')

        plant_count = user.assigned_plants.count()
        zone_count = user.assigned_zones.count()
        loc_count = user.assigned_locations.count()
        subloc_count = user.assigned_sublocations.count()

        messages.success(
            self.request,
            f'User "{user.get_full_name()}" created successfully! '
            f'Assigned: {plant_count} plant(s), {zone_count} zone(s), '
            f'{loc_count} location(s), {subloc_count} sub-location(s).'
        )

        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

    
from django.contrib.auth import update_session_auth_hash

class UserUpdateView(LoginRequiredMixin, UpdateView):
    """Update user - Only accessible by Admin"""
    model = User
    form_class = UserUpdateForm
    template_name = 'accounts/user_update.html'

    def get_success_url(self):
        return reverse_lazy('accounts:user_detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        
        # context['all_plants'] = Plant.objects.filter(is_active=True).order_by('name')
        # Admin → all plants
        if self.request.user.is_superuser or self.request.user.is_admin_user:

            context['all_plants'] = Plant.objects.filter(
                is_active=True
            ).order_by('name')

        # Safety Manager → only assigned plants
        elif (
            self.request.user.role
            and self.request.user.role.name == 'SAFETY MANAGER'
        ):

            context['all_plants'] = self.request.user.assigned_plants.filter(
                is_active=True
            ).order_by('name')

        # Other users
        else:

            context['all_plants'] = Plant.objects.none()
        
        context['user_assigned_plants'] = list(user.assigned_plants.values_list('id', flat=True))
        context['user_assigned_zones'] = list(user.assigned_zones.values_list('id', flat=True))
        context['user_assigned_locations'] = list(user.assigned_locations.values_list('id', flat=True))
        context['user_assigned_sublocations'] = list(user.assigned_sublocations.values_list('id', flat=True))
        
        if not (self.request.user.is_superuser or self.request.user.is_admin_user):
            context['user_assigned_plants_details'] = user.assigned_plants.all().order_by('name')
            context['user_assigned_zones_details'] = user.assigned_zones.all().order_by('name')
            context['user_assigned_locations_details'] = user.assigned_locations.all().order_by('name')
            context['user_assigned_sublocations_details'] = user.assigned_sublocations.all().order_by('name')

        context['can_edit_location_assignment'] = (self.request.user.is_superuser or self.request.user.is_admin_user
            or (self.request.user.role and self.request.user.role.name == 'SAFETY MANAGER')
)
        context['cancel_url'] = (self.request.GET.get('next') or self.request.META.get('HTTP_REFERER') or '/')
        return context
    
    def form_valid(self, form):
        old_user = User.objects.get(pk=self.object.pk)
        old_role = old_user.role
        
        user = form.save(commit=False)
        user.is_active = old_user.is_active
        
        if not (self.request.user.is_superuser or self.request.user.is_admin_user):
            user.role = old_user.role
            user.department = old_user.department
            user.is_active = old_user.is_active
        
        user.save()

        # ✅ FIX: Immediately after first save, re-bind session to logged-in admin
        # This prevents Django from switching the session to the updated user
        update_session_auth_hash(self.request, self.request.user)

        if (self.request.user.is_superuser or self.request.user.is_admin_user
            or (self.request.user.role and self.request.user.role.name == 'SAFETY MANAGER')):
            assigned_plants = self.request.POST.getlist('assigned_plants')
            user.assigned_plants.set(assigned_plants)
            user.plant = Plant.objects.filter(id__in=assigned_plants).first()
            
            assigned_zones = self.request.POST.getlist('assigned_zones')
            user.assigned_zones.set(assigned_zones)
            user.zone = Zone.objects.filter(id__in=assigned_zones).first()
            
            assigned_locations = self.request.POST.getlist('assigned_locations')
            user.assigned_locations.set(assigned_locations)
            user.location = Location.objects.filter(id__in=assigned_locations).first()
            
            assigned_sublocations = self.request.POST.getlist('assigned_sublocations')
            user.assigned_sublocations.set(assigned_sublocations)
            user.sublocation = SubLocation.objects.filter(id__in=assigned_sublocations).first()
            
            user.save()

        if old_role != user.role:
            if user.role:
                updated = user.sync_permissions_to_flags()
                messages.info(self.request, f'Role changed! Synced {updated} permissions from {user.role.name}')
            else:
                user.sync_permissions_to_flags()
                messages.info(self.request, 'Role removed. All permissions reset.')
        
        messages.success(self.request, f'User {user.username} updated successfully!')
        
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_admin_user or self.request.user.can_create_users:
            return User.objects.filter(is_superuser=False)
        
        return User.objects.filter(pk=self.request.user.pk)


class UserDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete user - Only accessible by Admin"""
    model = User
    template_name = 'accounts/user_confirm_delete.html'
    success_url = reverse_lazy('accounts:user_list')
    
    def get_queryset(self):
        # Prevent deleting superuser accounts
        return User.objects.filter(is_superuser=False)
    
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        messages.success(request, f'User {user.username} deleted successfully!')
        return super().delete(request, *args, **kwargs)


class UserDetailView(LoginRequiredMixin, TemplateView):
    """View user details - Only accessible by Admin"""
    template_name = 'accounts/user_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs.get('pk')
        # Only show employee details, not superuser
        if not(self.request.user.is_superuser or self.request.user.is_admin_user or self.request.user.can_create_users):
            user_obj = get_object_or_404(User, pk=self.request.user.pk)
        else:
            user_obj = get_object_or_404(User.objects.filter(is_superuser=False),pk=user_id)
        
        context['user_detail'] = user_obj
        context['cancel_url'] = (self.request.GET.get('next') or self.request.META.get('HTTP_REFERER') or '/')
        return context


class UserToggleActiveView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Toggle user active status"""
    
    def post(self, request, pk):
        # Only allow toggling for employees, not superuser
        user = get_object_or_404(
            User.objects.filter(is_superuser=False), 
            pk=pk
        )
        
        user.is_active = not user.is_active
        user.save()
        
        status = 'activated' if user.is_active else 'deactivated'
        messages.success(request, f'User {user.username} has been {status}.')
        return redirect('accounts:user_list')
    

######## permission module i am creating   ###########################
# class UserPermissionsOnlyView(LoginRequiredMixin, AdminRequiredMixin, ListView):
#     """
#     Separate page ONLY for managing permissions
#     Shows users with checkboxes for module access and approval permissions
#     """
#     model = User
#     template_name = 'accounts/permissions_only.html'
#     context_object_name = 'users'
#     paginate_by = 15
    
#     def get_queryset(self):
#         queryset = User.objects.filter(is_active=True).exclude(
#             is_superuser=True
#         ).select_related('plant', 'department').order_by('first_name', 'last_name')
        
#         # Search filter
#         search = self.request.GET.get('search')
#         if search:
#             queryset = queryset.filter(
#                 Q(first_name__icontains=search) |
#                 Q(last_name__icontains=search) |
#                 Q(username__icontains=search) |
#                 Q(email__icontains=search) |
#                 Q(employee_id__icontains=search)
#             )
        
#         # Role filter
#         role = self.request.GET.get('role')
#         if role:
#             queryset = queryset.filter(role__name=role)
        
#         # Plant filter
#         plant_id = self.request.GET.get('plant')
#         if plant_id:
#             queryset = queryset.filter(plant_id=plant_id)
        
#         return queryset
    
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         from apps.organizations.models import Plant
        
#         context['roles'] = Role.objects.all()
#         context['plants'] = Plant.objects.filter(is_active=True)
#         context['search_query'] = self.request.GET.get('search', '')
        
#         # Statistics
#         context['total_users'] = User.objects.filter(is_active=True).exclude(is_superuser=True).count()
#         context['users_with_incident_access'] = User.objects.filter(can_access_incident_module=True).count()
#         context['users_with_hazard_access'] = User.objects.filter(can_access_hazard_module=True).count()
#         context['hazard_approvers'] = User.objects.filter(can_approve_hazards=True).count()
#         context['incident_approvers'] = User.objects.filter(can_approve_incidents=True).count()
        
#         return context


# def update_user_permission(request, user_id):
#     """
#     AJAX endpoint to update a single permission for a user
#     """
#     if not (request.user.is_superuser or request.user.role.name == 'ADMIN' and request.user.role.name == 'ADMIN'):
#         return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
#     if request.method == 'POST':
#         user = get_object_or_404(User, pk=user_id)
#         permission_field = request.POST.get('permission_field')
#         value = request.POST.get('value') == 'true'
        
#         # List of valid permission fields
#         valid_fields = [
#             'can_access_incident_module',
#             'can_access_hazard_module',
#             'can_access_inspection_module',
#             'can_access_audit_module',
#             'can_access_training_module',
#             'can_access_permit_module',
#             'can_access_observation_module',
#             'can_access_reports_module',
#             'can_approve_incidents',
#             'can_approve_hazards',
#             'can_approve_inspections',
#             'can_approve_permits',
#             'can_close_incidents',
#             'can_close_hazards',
#         ]
        
#         if permission_field in valid_fields:
#             setattr(user, permission_field, value)
#             user.save()
            
#             messages.success(
#                 request, 
#                 f"{'Granted' if value else 'Revoked'} {permission_field.replace('_', ' ').title()} for {user.get_full_name()}"
#             )
            
#             return JsonResponse({
#                 'success': True,
#                 'message': f"Permission updated for {user.get_full_name()}"
#             })
#         else:
#             return JsonResponse({'success': False, 'error': 'Invalid permission field'}, status=400)
    
#     return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


# def bulk_update_permissions(request):
#     """
#     Bulk update permissions for multiple users
#     """
#     if not (request.user.is_superuser or request.user.role.name == 'ADMIN'):
#         messages.error(request, "You don't have permission to perform this action.")
#         return redirect('accounts:permissions_only')
    
#     if request.method == 'POST':
#         user_ids = request.POST.getlist('user_ids')
#         permission_field = request.POST.get('permission_field')
#         action = request.POST.get('action')  # 'grant' or 'revoke'
        
#         if not user_ids:
#             messages.error(request, "No users selected")
#             return redirect('accounts:permissions_only')
        
#         users = User.objects.filter(id__in=user_ids)
        
#         # List of valid permission fields
#         valid_fields = [
#             'can_access_incident_module',
#             'can_access_hazard_module',
#             'can_access_inspection_module',
#             'can_access_audit_module',
#             'can_access_training_module',
#             'can_access_permit_module',
#             'can_access_observation_module',
#             'can_access_reports_module',
#             'can_approve_incidents',
#             'can_approve_hazards',
#             'can_approve_inspections',
#             'can_approve_permits',
#             'can_close_incidents',
#             'can_close_hazards',
#         ]
        
#         if permission_field in valid_fields:
#             value = action == 'grant'
#             users.update(**{permission_field: value})
            
#             perm_name = permission_field.replace('_', ' ').replace('can ', '').title()
#             messages.success(
#                 request, 
#                 f"{action.title()}ed {perm_name} permission for {len(user_ids)} user(s)"
#             )
#         else:
#             messages.error(request, "Invalid permission field")
        
#         return redirect('accounts:permissions_only')
    
#     return redirect('accounts:permissions_only')  



class GetSubLocationsAjaxView(LoginRequiredMixin, View):
    """AJAX view to get sublocations for selected location"""
    
    def get(self, request):
        location_id = request.GET.get('location_id')
        sublocations = SubLocation.objects.filter(
            location_id=location_id, 
            is_active=True
        ).values('id', 'name', 'code')
        return JsonResponse(list(sublocations), safe=False)

# =======================
# Role and permission
#========================
class RolePermission(LoginRequiredMixin, TemplateView):
    template_name = 'roles/role_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = Role.objects.all()
        return context
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = self.request.GET.get('search', '')
        roles = Role.objects.all()
        if search:
            roles = roles.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        context['roles'] = roles
        context['search_query'] = search
        return context
    
class RoleCreateView(LoginRequiredMixin, TemplateView):
    """Assigning user roles"""
    template_name = 'roles/roles_permission.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['permission'] = Permissions.objects.all()
        return context

    def post(self, request):
        role_name = request.POST.get("role_name", "").strip()
        description = request.POST.get("description", "").strip()

        permission_ids = [
            pid for pid in request.POST.getlist("permissions") if pid
        ]

        if not role_name:
            messages.error(request, "Role name is required")
            return redirect('accounts:createrole')

        if Role.objects.filter(name=role_name).exists():
            messages.error(request, "Role name already exists")
            return redirect('accounts:createrole')

        role = Role.objects.create(
            name=role_name,
            description=description
        )

        if permission_ids:
            permissions = Permissions.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)

        messages.success(request, "Role created successfully")
        return redirect('accounts:role-list')
    
class RoleUpdateView(LoginRequiredMixin, TemplateView):
    """Update an existing role"""
    template_name = 'roles/roleupdate.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_id = self.kwargs.get('role_id')
        role = get_object_or_404(Role, id=role_id)

        context['role'] = role
        context['permission'] = Permissions.objects.all()
        context['role_permissions'] = role.permissions.values_list('id', flat=True)
        return context

    def post(self, request, *args, **kwargs):
        role_id = self.kwargs.get('role_id')
        role = get_object_or_404(Role, id=role_id)

        role_name = request.POST.get("role_name", "").strip()
        description = request.POST.get("description", "").strip()
        permission_ids = [
            pid for pid in request.POST.getlist("permissions") if pid
        ]

        if not role_name:
            messages.error(request, "Role name is required")
            return redirect('accounts:updaterole', role_id=role.id)

        if Role.objects.filter(name=role_name).exclude(id=role.id).exists():
            messages.error(request, "Role name already exists")
            return redirect('accounts:updaterole', role_id=role.id)

        role.name = role_name
        role.description = description
        role.save()
        
        if permission_ids:
            permissions = Permissions.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
        else:
            role.permissions.clear()

        # ✅ NEW: Sync permissions to all users with this role
        affected_users = role.role_user.all()
        synced_count = 0
        for user in affected_users:
            user.sync_permissions_to_flags()
            synced_count += 1
        
        if synced_count > 0:
            messages.info(request, f"Synced permissions to {synced_count} user(s) with this role")

        messages.success(request, "Role updated successfully")
        return redirect('accounts:role-list')
    

###########################Role-permissin#############################

class RolePermissionsHierarchicalView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Hierarchical permission management with module grouping"""
    template_name = 'roles/role_permissions_hierarchical.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_id = self.kwargs.get('role_id')
        role = get_object_or_404(Role, id=role_id)
        
        context['role'] = role
        context['role_permission_ids'] = list(role.permissions.values_list('id', flat=True))
        
        # Group permissions by module
        modules = {}
        module_choices = dict(Permissions._meta.get_field('module').choices)
        
        for module_code, module_name in module_choices.items():
            # Get all permissions for this module
            module_perms = Permissions.objects.filter(
                module=module_code
            ).order_by('display_order')
            
            if module_perms.exists():
                # Separate module access from other permissions
                access_perm = module_perms.filter(permission_type='MODULE_ACCESS').first()
                other_perms = module_perms.exclude(permission_type='MODULE_ACCESS')
                
                # Check if role has access
                has_access = access_perm and (access_perm.id in context['role_permission_ids'])
                
                modules[module_code] = {
                    'name': module_name,
                    'access_permission': access_perm,
                    'has_access': has_access,
                    'permissions': other_perms
                }
        
        context['modules'] = modules
        
        return context


def toggle_module_access(request, role_id):
    """Toggle module access - grants/revokes parent permission"""
    if not (request.user.is_superuser or (request.user.role and request.user.role.name == 'ADMIN')):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        role = get_object_or_404(Role, id=role_id)
        module_code = request.POST.get('module_code')
        action = request.POST.get('action')  # 'grant' or 'revoke'
        
        try:
            # Get module access permission
            access_perm = Permissions.objects.get(
                module=module_code,
                permission_type='MODULE_ACCESS'
            )
            
            if action == 'grant':
                # Grant module access
                role.permissions.add(access_perm)
                message = f"Granted access to {access_perm.name}"
                
            elif action == 'revoke':
                # Revoke module access AND all child permissions
                role.permissions.remove(access_perm)
                
                # Remove ALL permissions in this module
                module_perms = Permissions.objects.filter(module=module_code)
                role.permissions.remove(*module_perms)
                
                message = f"Revoked access to {access_perm.name} and all related permissions"
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
            
            # ✅ NEW: Sync permissions to all users with this role
            affected_users = role.role_user.all()
            synced_count = 0
            for user in affected_users:
                user.sync_permissions_to_flags()
                synced_count += 1
            
            # Count users affected
            user_count = role.role_user.count()
            
            return JsonResponse({
                'success': True,
                'message': f"{message}. Synced permissions for {synced_count} user(s).",
                'module_code': module_code,
                'has_access': action == 'grant',
                'affected_users': user_count,
                'synced_users': synced_count
            })
            
        except Permissions.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Module access permission not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def toggle_permission_in_module(request, role_id):
    """Toggle individual permission - only works if module access granted"""
    if not (request.user.is_superuser or (request.user.role and request.user.role.name == 'ADMIN')):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        role = get_object_or_404(Role, id=role_id)
        permission_id = request.POST.get('permission_id')
        action = request.POST.get('action')  # 'add' or 'remove'
        
        try:
            permission = Permissions.objects.get(id=permission_id)
            
            # Check if role has module access
            has_module_access = role.permissions.filter(
                module=permission.module,
                permission_type='MODULE_ACCESS'
            ).exists()
            
            if not has_module_access and action == 'add':
                return JsonResponse({
                    'success': False,
                    'error': f'Must grant "{permission.module}" module access first'
                }, status=400)
            
            if action == 'add':
                role.permissions.add(permission)
                message = f"Added '{permission.name}'"
            elif action == 'remove':
                role.permissions.remove(permission)
                message = f"Removed '{permission.name}'"
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
            
            # ✅ NEW: Sync permissions to all users with this role
            affected_users = role.role_user.all()
            synced_count = 0
            for user in affected_users:
                user.sync_permissions_to_flags()
                synced_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f"{message}. Synced to {synced_count} user(s).",
                'permission_count': role.permissions.count(),
                'synced_users': synced_count
            })
            
        except Permissions.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Permission not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)




###Download the excel for the user list 
import pandas as pd
from io import BytesIO
from django.http import HttpResponse
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

class UserExportExcelView(LoginRequiredMixin, CanCreateUsersMixin, View):
    """Export all users to Excel"""

    def get(self, request):
        users = User.objects.filter(is_superuser=False).select_related(
            'role', 'plant', 'department'
        ).prefetch_related('assigned_plants').order_by('first_name', 'last_name')

        data = []
        for i, user in enumerate(users, start=1):
            assigned_plants = ", ".join(
                user.assigned_plants.values_list('name', flat=True)
            )
            data.append({
                '#': i,
                'Employee ID': user.employee_id or 'N/A',
                'Full Name': user.get_full_name(),
                'Username': user.username,
                'Email': user.email,
                'Role': user.role.name if user.role else 'No Role',
                'Status': 'Active' if user.is_active else 'Inactive',
                'Primary Plant': user.plant.name if user.plant else 'N/A',
                'Assigned Plants': assigned_plants or 'N/A',
                'Department': user.department.name if user.department else 'N/A',
                'Employment Type': user.get_employment_type_display(),
                'Job Title': user.job_title or 'N/A',
                'Date Joined Company': user.date_joined_company.strftime('%d-%m-%Y') if user.date_joined_company else 'N/A',
                'System Date Joined': user.date_joined.strftime('%d-%m-%Y') if user.date_joined else 'N/A',
            })

        df = pd.DataFrame(data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Users')
            workbook = writer.book
            worksheet = writer.sheets['Users']

            # ── Header styling ──────────────────────────────
            header_fill = PatternFill(start_color='1E5FA8', end_color='1E5FA8', fill_type='solid')
            header_font = Font(bold=True, color='FFFFFF', size=11)
            header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
            thin_border = Border(
                left=Side(style='thin', color='CCCCCC'),
                right=Side(style='thin', color='CCCCCC'),
                top=Side(style='thin', color='CCCCCC'),
                bottom=Side(style='thin', color='CCCCCC'),
            )

            for col_num, col_name in enumerate(df.columns, start=1):
                cell = worksheet.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_align
                cell.border = thin_border

            # ── Row styling (alternating) ───────────────────
            even_fill = PatternFill(start_color='EAF2FB', end_color='EAF2FB', fill_type='solid')
            odd_fill  = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')
            row_font  = Font(size=10)
            row_align = Alignment(horizontal='left', vertical='center', wrap_text=False)

            for row_num in range(2, len(data) + 2):
                fill = even_fill if row_num % 2 == 0 else odd_fill
                for col_num in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=row_num, column=col_num)
                    cell.fill = fill
                    cell.font = row_font
                    cell.alignment = row_align
                    cell.border = thin_border

            # ── Column widths ───────────────────────────────
            col_widths = {
                '#': 5, 'Employee ID': 14, 'Full Name': 22, 'Username': 16,
                'Email': 28, 'Role': 14, 'Status': 10, 'Primary Plant': 18,
                'Assigned Plants': 30, 'Department': 18, 'Employment Type': 16,
                'Job Title': 20, 'Date Joined Company': 20, 'System Date Joined': 20,
            }
            for col_num, col_name in enumerate(df.columns, start=1):
                width = col_widths.get(col_name, 15)
                worksheet.column_dimensions[get_column_letter(col_num)].width = width

            # ── Row height ──────────────────────────────────
            worksheet.row_dimensions[1].height = 35
            for row_num in range(2, len(data) + 2):
                worksheet.row_dimensions[row_num].height = 20

            # ── Freeze header ───────────────────────────────
            worksheet.freeze_panes = 'A2'

        output.seek(0)
        from datetime import date
        filename = f"users_export_{date.today().strftime('%Y-%m-%d')}.xlsx"

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response