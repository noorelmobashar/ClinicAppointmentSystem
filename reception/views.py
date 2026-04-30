from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib import messages

from appointments.models import Appointment, AppointmentSlot
from .models import WalkInPatient
from .forms import WalkInPatientForm, UpdateStatusForm

User = get_user_model()


class ReceptionistRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'RECEPTIONIST':
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)


class FrontDeskTrafficView(LoginRequiredMixin, ReceptionistRequiredMixin, ListView):
    model = Appointment
    template_name = 'reception/traffic_board.html'
    context_object_name = 'appointments'

    def get_queryset(self):
        today = timezone.now().date()
        return Appointment.objects.filter(
            slot__date=today
        ).select_related(
            'patient', 'slot', 'slot__doctor'
        ).order_by('slot__start_time')

    def get(self, request, *args, **kwargs):
        return redirect('dashboard')


class UpdateAppointmentStatusView(LoginRequiredMixin, ReceptionistRequiredMixin, View):
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        form = UpdateStatusForm(request.POST)

        if form.is_valid():
            appointment.status = form.cleaned_data['status']
            appointment.save()
            name = appointment.patient.get_full_name() or appointment.patient.username
            messages.success(request, f"Status for {name} changed to {appointment.status}.")

        return redirect('reception:traffic_board')


class ForceBookingView(LoginRequiredMixin, ReceptionistRequiredMixin, View):
    def get(self, request):
        return redirect('dashboard')

    def post(self, request):
        form = WalkInPatientForm(request.POST)

        if form.is_valid():
           
            walk_in = WalkInPatient.objects.create(
                name=form.cleaned_data['name'],
                phone_number=form.cleaned_data['phone_number'],
                notes=form.cleaned_data['notes'],
            )
            doctor = form.cleaned_data['doctor']

         
            username = f"walkin_{walk_in.id}"
            patient_user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@local', 'role': 'PATIENT'}
            )
            if created:
                patient_user.set_unusable_password()
                patient_user.save()

          
            now = timezone.now()
            slot = AppointmentSlot.objects.create(
                doctor=doctor,
                date=now.date(),
                start_time=now.time(),
                end_time=(now + timezone.timedelta(minutes=30)).time(),
                is_booked=True,
            )

           
            Appointment.objects.create(
                patient=patient_user,
                doctor=doctor,
                slot=slot,
                status=Appointment.Status.CHECKED_IN,
            )

            messages.success(request, f"Successfully registered {walk_in.name}!")
            return redirect('dashboard')

        messages.error(request, "Could not register the walk-in. Please check the data and try again.")
        return redirect('dashboard')