from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from appointments.models import Appointment, AppointmentSlot, RescheduleHistory
from .models import WalkInPatient
from .forms import WalkInPatientForm, UpdateStatusForm, RescheduleForm

User = get_user_model()


class ReceptionistRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'RECEPTIONIST':
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)


class UpdateAppointmentStatusView(LoginRequiredMixin, ReceptionistRequiredMixin, View):
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        form = UpdateStatusForm(request.POST)

        if form.is_valid():
            new_status = form.cleaned_data['status']
            if new_status == Appointment.Status.COMPLETED:
                if appointment.status != Appointment.Status.CHECKED_IN:
                    messages.error(request, "Only checked‑in appointments can be marked as completed.")
                    return redirect('dashboard')
            appointment.status = new_status
            appointment.save()
            name = appointment.patient.get_full_name() or appointment.patient.username
            messages.success(request, f"Status for {name} changed to {appointment.status}.")

        return redirect('dashboard')


class WalkInPatientCreateView(LoginRequiredMixin, ReceptionistRequiredMixin, View):
    def get(self, request):
        form = WalkInPatientForm()
        return render(request, 'reception/walk_in.html', {
            'form': form,
            'current_section': 'walkin'
        })

    def post(self, request):
        form = WalkInPatientForm(request.POST)

        if form.is_valid():
            walk_in = self.create_walk_in_patient(form)
            doctor = form.cleaned_data['doctor']
            patient_user = self.get_or_create_walk_in_user(walk_in)
            self.create_walk_in_appointment(patient_user, doctor)

            messages.success(request, f"Successfully registered {walk_in.name}!")
            return redirect('dashboard')

        messages.error(request, "Could not register the walk-in. Please check the data and try again.")
        return render(request, 'reception/walk_in.html', {
            'form': form,
            'current_section': 'walkin'
        })

    def create_walk_in_patient(self, form):
        return WalkInPatient.objects.create(
            name=form.cleaned_data['name'],
            phone_number=form.cleaned_data['phone_number'],
            notes=form.cleaned_data['notes'],
        )

    def get_or_create_walk_in_user(self, walk_in):
        username = f"walkin_{walk_in.id}"
        patient_user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@local',
                'role': 'PATIENT',
            },
        )
        if created:
            patient_user.set_unusable_password()
            patient_user.save()
        return patient_user

    def create_walk_in_appointment(self, patient_user, doctor):
        now = timezone.now()
        slot = AppointmentSlot.objects.create(
            doctor=doctor,
            date=now.date(),
            start_time=now.time(),
            end_time=(now + timedelta(minutes=30)).time(),
            is_booked=True,
        )
        return Appointment.objects.create(
            patient=patient_user,
            doctor=doctor,
            slot=slot,
            status=Appointment.Status.CHECKED_IN,
        )



class RescheduleAppointmentView(LoginRequiredMixin, ReceptionistRequiredMixin, View):
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)

        if appointment.status in [Appointment.Status.CANCELLED, Appointment.Status.COMPLETED]:
            messages.error(request, "Completed or cancelled appointments cannot be rescheduled.")
            return redirect('dashboard')

        form = RescheduleForm(request.POST)
        
        if form.is_valid():
            new_date = form.cleaned_data['new_date']
            new_start_time = form.cleaned_data['new_start_time']
            reason = form.cleaned_data['reason']

            old_slot = appointment.slot
            
          
            new_slot, created = AppointmentSlot.objects.get_or_create(
                doctor=appointment.doctor,
                date=new_date,
                start_time=new_start_time,
                defaults={
                    'end_time': (timezone.datetime.combine(new_date, new_start_time) + timedelta(minutes=30)).time(),
                    'is_booked': True
                }
            )
            
            if not created and new_slot.is_booked:
                messages.error(request, "The selected new slot is already booked.")
                return redirect('dashboard')
                
            new_slot.is_booked = True
            new_slot.save()
            
            old_slot.is_booked = False
            old_slot.save()
            
            RescheduleHistory.objects.create(
                appointment=appointment,
                old_slot=old_slot,
                new_slot=new_slot,
                changed_by=request.user,
                reason=reason
            )
            
            appointment.slot = new_slot
            appointment.save()
            
            messages.success(request, f"Successfully rescheduled appointment for {appointment.patient}.")
            
        else:
            messages.error(request, "Failed to reschedule. Please check the form data.")
            
        return redirect('dashboard')
