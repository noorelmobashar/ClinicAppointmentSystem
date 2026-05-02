from django.contrib import admin
from .models import Appointment, AppointmentSlot

@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'date', 'start_time', 'end_time', 'is_booked')
    list_filter = ('doctor', 'date', 'is_booked')
    search_fields = ('doctor__username', 'doctor__email')
    list_editable = ('is_booked',)
    ordering = ('-date', '-start_time')
    
    # Filter by doctor by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'DOCTOR':
            return qs.filter(doctor=request.user)
        return qs
    
    # Hide doctor selection for doctors
    def get_readonly_fields(self, request, obj=None):
        if obj and request.user.role == 'DOCTOR':
            return ('doctor',)
        return self.readonly_fields

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'slot', 'status', 'created_at')
    list_filter = ('status', 'slot__date', 'doctor', 'patient')
    search_fields = ('patient__username', 'patient__email', 'doctor__username', 'doctor__email')
    list_editable = ('status',)
    ordering = ('-slot__date', '-slot__start_time')
    readonly_fields = ('created_at', 'updated_at')
    
    # Filter by doctor by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'DOCTOR':
            return qs.filter(doctor=request.user)
        return qs
    
    # Hide doctor selection for doctors
    def get_readonly_fields(self, request, obj=None):
        if obj and request.user.role == 'DOCTOR':
            return ('doctor', 'patient', 'slot', 'status')
        return self.readonly_fields
