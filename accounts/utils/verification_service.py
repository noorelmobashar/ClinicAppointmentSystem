from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from ..models import CustomUser
import os
class VerificationService:
    @staticmethod
    def generate_link(user,forget_password=False):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        host = os.getenv('HOST', 'localhost')
        port = os.getenv('PORT', '3000')
        socket = f"{host}:{port}" if os.getenv("DEBUG", "True") == "True" else host
        method = "http" if os.getenv("DEBUG", "True") == "True" else "https"
        if forget_password:
            return f"{method}://{socket}/accounts/reset-password/{uid}/{token}/"
        return f"{method}://{socket}/accounts/verify/{uid}/{token}/"

    @staticmethod
    def verify(uid, token):
        try:
            uid = force_str(urlsafe_base64_decode(uid))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            return user
        return False