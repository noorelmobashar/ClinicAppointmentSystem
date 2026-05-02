from django.contrib import admin
from .models import WalkInPatient

@admin.register(WalkInPatient)
class WalkInPatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'notes', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone_number')
    readonly_fields = ('created_at',)
    
    # Filter by doctor by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'DOCTOR':
            return qs.filter(patient__doctor=request.user)
        return qs
