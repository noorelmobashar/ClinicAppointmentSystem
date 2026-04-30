from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.timezone import now
from appointments.models import Appointment

class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        context = {
            "current_section": "overview",
        }

        if request.user.role == "PATIENT":
            patient_appointments = Appointment.objects.filter(patient=request.user)
            context.update({
                "total_appointments": patient_appointments.count(),
                "upcoming_appointments": patient_appointments.filter(slot__date__gte=now().date()).count(),
                "completed_visits": patient_appointments.filter(status=Appointment.Status.COMPLETED).count(),
                "active_appointments": patient_appointments.exclude(
                    status__in=[Appointment.Status.COMPLETED, Appointment.Status.CANCELLED]
                ).count(),
            })

        return render(request, 'dashboard/dashboard.html', context)
