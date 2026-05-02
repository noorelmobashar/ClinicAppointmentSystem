from django.contrib import admin
from .models import PatientRegistration

@admin.register(PatientRegistration)
class PatientRegistrationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'gender', 'date_of_birth', 'address', 'created_at')
    list_filter = ('gender', 'date_of_birth')
    search_fields = ('patient__username', 'patient__email', 'patient__phone_number', 'address')
    readonly_fields = ('created_at', 'updated_at')
    
    # Filter by doctor by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'DOCTOR':
            return qs.filter(patient__doctor=request.user)
        return qs
