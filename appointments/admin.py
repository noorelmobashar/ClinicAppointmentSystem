from django.contrib import admin
from .models import Appointment, AppointmentSlot, DoctorSchedule

admin.site.register(Appointment)
admin.site.register(AppointmentSlot)
admin.site.register(DoctorSchedule)