from django.core.exceptions import ObjectDoesNotExist

from accounts.models import CustomUser


def _get_related_profile(user, attr_name):
    try:
        return getattr(user, attr_name)
    except ObjectDoesNotExist:
        return None


def is_profile_complete(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if user.role == CustomUser.Role.DOCTOR:
        profile = _get_related_profile(user, "doctor_profile")
        return bool(profile and profile.specialty)

    if user.role == CustomUser.Role.PATIENT:
        profile = _get_related_profile(user, "patient_profile")
        return bool(profile and profile.blood_type)

    return True
