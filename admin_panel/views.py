import csv
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.db.models.functions import TruncMonth
from django.views.generic import ListView, CreateView, UpdateView, View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse

from .mixins import AdminRequiredMixin
from .forms import AdminUserCreateForm, AdminUserEditForm
from accounts.models import CustomUser, DoctorProfile, PatientProfile
from appointments.models import Appointment
from payments.models import PaymentTransaction
from reception.models import WalkInPatient

class UserListView(AdminRequiredMixin, ListView):
    model = CustomUser
    template_name = 'admin_panel/user_list.html'
    context_object_name = 'users'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        
        q = self.request.GET.get('q', '')
        role = self.request.GET.get('role', '')
        status = self.request.GET.get('status', '')

        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(email__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q)
            )
        
        if role and role != 'ALL':
            qs = qs.filter(role=role)
            
        if status == 'Active':
            qs = qs.filter(is_active=True)
        elif status == 'Inactive':
            qs = qs.filter(is_active=False)
            
        return qs.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['role'] = self.request.GET.get('role', 'ALL')
        context['status'] = self.request.GET.get('status', 'ALL')
        context['current_section'] = 'admin-users'
        return context

class UserCreateView(AdminRequiredMixin, CreateView):
    model = CustomUser
    form_class = AdminUserCreateForm
    template_name = 'admin_panel/user_create.html'
    success_url = reverse_lazy('admin-users')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        
        if user.role == 'DOCTOR':
            DoctorProfile.objects.get_or_create(user=user)
        elif user.role == 'PATIENT':
            PatientProfile.objects.get_or_create(
                user=user,
                defaults={'date_of_birth': timezone.now().date()}
            )
            
        messages.success(self.request, f"User {user.username} created successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_section'] = 'admin-users'
        return context

class UserEditView(AdminRequiredMixin, UpdateView):
    model = CustomUser
    form_class = AdminUserEditForm
    template_name = 'admin_panel/user_edit.html'
    success_url = reverse_lazy('admin-users')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        
        if user.role == 'DOCTOR':
            DoctorProfile.objects.get_or_create(user=user)
        elif user.role == 'PATIENT':
            PatientProfile.objects.get_or_create(
                user=user,
                defaults={'date_of_birth': timezone.now().date()}
            )
            
        messages.success(self.request, f"User {user.username} updated successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_section'] = 'admin-users'
        return context

class UserToggleActiveView(AdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        user = get_object_or_404(CustomUser, pk=pk)
        # Prevent deactivating oneself
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect('admin-users')
            
        user.is_active = not user.is_active
        user.save()
        status_text = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User {user.username} {status_text}.")
        return redirect('admin-users')


def get_analytics_data(date_from, date_to):
    appointments = Appointment.objects.filter(created_at__gte=date_from, created_at__lte=date_to)
    transactions = PaymentTransaction.objects.filter(created_at__gte=date_from, created_at__lte=date_to)
    users = CustomUser.objects.filter(date_joined__gte=date_from, date_joined__lte=date_to)
    
    total_revenue = transactions.filter(status='PAID').aggregate(total=Sum('amount'))['total'] or 0
    total_appointments = appointments.count()
    total_users = users.count()
    
    confirmed_statuses = ['CONFIRMED', 'COMPLETED', 'CHECKED_IN']
    confirmed_count = appointments.filter(status__in=confirmed_statuses).count()
    confirmed_rate = round((confirmed_count / total_appointments * 100), 1) if total_appointments > 0 else 0
    
    paid_tx_count = transactions.filter(status='PAID').count()
    avg_revenue = round(float(total_revenue) / paid_tx_count, 2) if paid_tx_count > 0 else 0
    
    refund_qs = transactions.filter(status='REFUNDED')
    total_refunds = refund_qs.count()
    refund_amount = refund_qs.aggregate(total=Sum('amount'))['total'] or 0

    # Monthly Breakdown
    monthly_new_users = list(users.annotate(month=TruncMonth('date_joined')).values('month').annotate(count=Count('id')).order_by('month'))
    monthly_revenue = list(transactions.filter(status='PAID').annotate(month=TruncMonth('paid_at')).values('month').annotate(total=Sum('amount')).order_by('month'))
    monthly_appointments = list(appointments.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month'))

    # Payment Status
    payment_status_dist = list(transactions.values('status').annotate(count=Count('id')))

    # Appointment Status
    appt_status_dist = list(appointments.values('status').annotate(count=Count('id')))

    # Role Distribution
    role_dist = list(users.values('role').annotate(count=Count('id')))

    # Doctor Performance
    doctor_performance = []
    doctors = CustomUser.objects.filter(role='DOCTOR')
    for doc in doctors:
        doc_appts = appointments.filter(slot__doctor=doc)
        doc_total = doc_appts.count()
        if doc_total > 0:
            doc_completed = doc_appts.filter(status='COMPLETED').count()
            doc_rate = round((doc_completed / doc_total * 100), 1)
            doc_revenue = transactions.filter(appointment__slot__doctor=doc, status='PAID').aggregate(total=Sum('amount'))['total'] or 0
            doctor_performance.append({
                'name': doc.get_full_name() or doc.username,
                'total_appointments': doc_total,
                'completed': doc_completed,
                'completion_rate': doc_rate,
                'revenue': doc_revenue
            })
    doctor_performance.sort(key=lambda x: x['revenue'], reverse=True)

    return {
        'total_revenue': total_revenue,
        'total_appointments': total_appointments,
        'total_users': total_users,
        'confirmed_rate': confirmed_rate,
        'avg_revenue': avg_revenue,
        'total_refunds': total_refunds,
        'refund_amount': refund_amount,
        'monthly_new_users': monthly_new_users,
        'monthly_revenue': monthly_revenue,
        'monthly_appointments': monthly_appointments,
        'payment_status_dist': payment_status_dist,
        'appt_status_dist': appt_status_dist,
        'role_dist': role_dist,
        'doctor_performance': doctor_performance,
    }



class AnalyticsExportView(AdminRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        date_from_str = request.GET.get('date_from')
        date_to_str = request.GET.get('date_to')

        if date_to_str:
            try:
                date_to = timezone.datetime.strptime(date_to_str, '%Y-%m-%d').date()
                date_to = timezone.make_aware(timezone.datetime.combine(date_to, timezone.datetime.max.time()))
            except ValueError:
                date_to = timezone.now()
        else:
            date_to = timezone.now()
            
        if date_from_str:
            try:
                date_from = timezone.datetime.strptime(date_from_str, '%Y-%m-%d').date()
                date_from = timezone.make_aware(timezone.datetime.combine(date_from, timezone.datetime.min.time()))
            except ValueError:
                date_from = date_to - timedelta(days=365)
        else:
            date_from = date_to - timedelta(days=365)

        data = get_analytics_data(date_from, date_to)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="analytics_export_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        
        # KPIs Section
        writer.writerow(['Overview KPIs'])
        writer.writerow(['Total Revenue (EGP)', data['total_revenue']])
        writer.writerow(['Total Appointments', data['total_appointments']])
        writer.writerow(['Total Users', data['total_users']])
        writer.writerow(['Confirmed Rate (%)', data['confirmed_rate']])
        writer.writerow(['Average Revenue/Appt (EGP)', data['avg_revenue']])
        writer.writerow(['Total Refunds', data['total_refunds']])
        writer.writerow(['Refund Amount (EGP)', data['refund_amount']])
        writer.writerow([])

        # Doctor Performance
        writer.writerow(['Doctor Performance'])
        writer.writerow(['Doctor Name', 'Total Appointments', 'Completed', 'Completion Rate (%)', 'Revenue Generated (EGP)'])
        for doc in data['doctor_performance']:
            writer.writerow([doc['name'], doc['total_appointments'], doc['completed'], doc['completion_rate'], doc['revenue']])
        writer.writerow([])

        # Appointment Status Distribution
        writer.writerow(['Appointment Status Distribution'])
        writer.writerow(['Status', 'Count'])
        for stat in data['appt_status_dist']:
            writer.writerow([stat['status'], stat['count']])
            
        return response
