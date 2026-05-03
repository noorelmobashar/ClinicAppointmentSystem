from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect

class AdminRequiredMixin(AccessMixin):
    """Verify that the current user is authenticated and is an ADMIN."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role != 'ADMIN':
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
