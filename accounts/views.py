import os

from django.conf import settings
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.hashers import check_password
from .forms import (
    LoginForm,
    RegisterForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    ChangePasswordForm,
    BaseProfileForm,
    DoctorProfileForm,
    PatientProfileForm,
    DoctorOnboardingForm,
    PatientOnboardingForm,
)
from .models import CustomUser, DoctorProfile, PatientProfile
from .utils.profile_completion import is_profile_complete
from django.db import transaction
# from .utils.return_testmail_recepient import map_to_testmail
from .utils.verification_service import VerificationService
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
class CustomLoginView(View):

    def get(self, request):
        form = LoginForm()
        return render(request, 'accounts/login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            try:
                user = CustomUser.objects.get(email=email,is_active=True)
            except CustomUser.DoesNotExist:
                form.add_error(None, "Invalid email or password")
                return render(request, 'accounts/login.html', {'form': form})

            if not check_password(password, user.password):
                form.add_error(None, "Invalid email or password")
                return render(request, 'accounts/login.html', {'form': form})

            login(request, user)
            if not is_profile_complete(user):
                return redirect('onboarding')
            return redirect('dashboard')  

        return render(request, 'accounts/login.html', {'form': form})


class CustomRegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, "accounts/register.html", {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.set_password(form.cleaned_data['password'])
                user.is_active = False
                user.save()
                
                # Generate verification
                verification_link = VerificationService.generate_link(user)

                # Using utility function to map email to testmail recepient
                # recepient_email = map_to_testmail(user.email)
                html_content = render_to_string(
                    "emails/activate_account.html",
                    {
                        "user": user,
                        "verification_link": verification_link
                    }
                )
                email = EmailMultiAlternatives(
                    subject="Activate Your Account",
                    body="Please activate your account.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email],
                )

                email.attach_alternative(html_content, "text/html")
                email.send()
            messages.success(
                request,
                "Account created successfully. Please check your email to activate your account."
            )
            return redirect('login')
        return render(request, "accounts/register.html", {'form': form})

class CustomForgotPasswordView(View):
    def get(self, request):
        form = ForgotPasswordForm()
        return render(request, "accounts/forgot_password.html", {'form': form})

    def post(self, request):
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email)

                reset_link = VerificationService.generate_link(user,forget_password=True)  

                # recepient_email = map_to_testmail(user.email)
                html_content = render_to_string(
                    "emails/reset_password.html",
                    {
                        "user": user,
                        "reset_link": reset_link
                    }
                )
                email = EmailMultiAlternatives(
                    subject="Reset Your Password",
                    body="Reset your password using the link.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email],
                )

                email.attach_alternative(html_content, "text/html")
                email.send()
                messages.success(
                    request,
                    "Password reset link sent. Please check your email."
                )
            except CustomUser.DoesNotExist:
                messages.error(request, "No account found with that email.")
            return redirect('login')
        return render(request, "accounts/forgot_password.html", {'form': form})

class CustomResetPasswordView(View):
    def get(self, request, uid, token):
        user = VerificationService.verify(uid, token)
        if user:
            messages.success(request, "Verification successful. Please enter your new password.")
            form = ResetPasswordForm()
            return render(request, "accounts/reset_password.html", {'form': form, 'uid': uid, 'token': token})
        else:
            messages.error(request, "Invalid or expired reset link.")
            return redirect('login')

    def post(self, request, uid, token):
        user = VerificationService.verify(uid, token)
        if not user:
            messages.error(request, "Invalid or expired reset link.")
            return redirect('login')

        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password']
            user.set_password(new_password)
            user.save()
            messages.success(request, "Password reset successful. You can now log in with your new password.")
            return redirect('login')

        return render(request, "accounts/reset_password.html", {'form': form, 'uid': uid, 'token': token})

class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("login")

    def post(self, request):
        logout(request)
        return redirect("login")


class OnboardingView(LoginRequiredMixin, View):
    login_url = "login"

    def _get_doctor_profile(self, user):
        try:
            return user.doctor_profile
        except DoctorProfile.DoesNotExist:
            return None

    def _get_patient_profile(self, user):
        try:
            return user.patient_profile
        except PatientProfile.DoesNotExist:
            return None

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in (CustomUser.Role.DOCTOR, CustomUser.Role.PATIENT):
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if is_profile_complete(request.user):
            return redirect("dashboard")

        if request.user.role == CustomUser.Role.DOCTOR:
            form = DoctorOnboardingForm(instance=self._get_doctor_profile(request.user))
            template_name = "onboarding/doctor_onboarding.html"
        else:
            form = PatientOnboardingForm(instance=self._get_patient_profile(request.user))
            template_name = "onboarding/patient_onboarding.html"

        return render(request, template_name, {"form": form})

    def post(self, request):
        if request.user.role == CustomUser.Role.DOCTOR:
            profile = self._get_doctor_profile(request.user)
            form = DoctorOnboardingForm(request.POST, instance=profile)
            template_name = "onboarding/doctor_onboarding.html"
        else:
            profile = self._get_patient_profile(request.user)
            form = PatientOnboardingForm(request.POST, instance=profile)
            template_name = "onboarding/patient_onboarding.html"

        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            return redirect("dashboard")

        return render(request, template_name, {"form": form})


class ProfileView(LoginRequiredMixin, View):
    login_url = "login"

    def _get_doctor_profile(self, user):
        if user.role != "DOCTOR":
            return None
        try:
            return user.doctor_profile
        except DoctorProfile.DoesNotExist:
            return None

    def _get_patient_profile(self, user):
        if user.role != "PATIENT":
            return None
        try:
            return user.patient_profile
        except PatientProfile.DoesNotExist:
            return None

    def get(self, request):
        edit_mode = request.GET.get("edit") == "1"
        doctor_profile = self._get_doctor_profile(request.user)
        patient_profile = self._get_patient_profile(request.user)
        return render(
            request,
            "profile/profile.html",
            {
                "base_profile_form": BaseProfileForm(instance=request.user),
                "doctor_profile_form": DoctorProfileForm(instance=doctor_profile) if doctor_profile else None,
                "patient_profile_form": PatientProfileForm(instance=patient_profile) if patient_profile else None,
                "change_password_form": ChangePasswordForm(),
                "doctor_profile": doctor_profile,
                "patient_profile": patient_profile,
                "doctor_profile_missing": request.user.role == "DOCTOR" and doctor_profile is None,
                "patient_profile_missing": request.user.role == "PATIENT" and patient_profile is None,
                "edit_mode": edit_mode,
                "current_section": "profile",
            },
        )

    def post(self, request):
        form_type = request.POST.get("form_type")
        edit_mode = request.GET.get("edit") == "1"
        doctor_profile = self._get_doctor_profile(request.user)
        patient_profile = self._get_patient_profile(request.user)
        doctor_profile_missing = request.user.role == "DOCTOR" and doctor_profile is None
        patient_profile_missing = request.user.role == "PATIENT" and patient_profile is None

        base_form = BaseProfileForm(instance=request.user)
        doctor_form = DoctorProfileForm(instance=doctor_profile) if doctor_profile else None
        patient_form = PatientProfileForm(instance=patient_profile) if patient_profile else None
        change_password_form = ChangePasswordForm()

        base_profile_updated = False
        doctor_profile_updated = False
        patient_profile_updated = False
        password_updated = False

        if form_type == "base":
            edit_mode = True
            base_form = BaseProfileForm(request.POST, instance=request.user)
            if base_form.is_valid():
                base_form.save()
                base_profile_updated = True
                base_form = BaseProfileForm(instance=request.user)
        elif form_type == "doctor":
            edit_mode = True
            if doctor_profile is None:
                doctor_profile_missing = True
            else:
                doctor_form = DoctorProfileForm(request.POST, instance=doctor_profile)
                if doctor_form.is_valid():
                    doctor_form.save()
                    doctor_profile_updated = True
                    doctor_form = DoctorProfileForm(instance=doctor_profile)
        elif form_type == "patient":
            edit_mode = True
            if patient_profile is None:
                patient_profile_missing = True
            else:
                patient_form = PatientProfileForm(request.POST, instance=patient_profile)
                if patient_form.is_valid():
                    patient_form.save()
                    patient_profile_updated = True
                    patient_form = PatientProfileForm(instance=patient_profile)
        elif form_type == "password":
            change_password_form = ChangePasswordForm(request.POST)
            if change_password_form.is_valid():
                old_password = change_password_form.cleaned_data["old_password"]
                if not request.user.check_password(old_password):
                    change_password_form.add_error("old_password", "Current password is incorrect.")
                else:
                    request.user.set_password(change_password_form.cleaned_data["new_password"])
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    password_updated = True
                    change_password_form = ChangePasswordForm()

        return render(
            request,
            "profile/profile.html",
            {
                "base_profile_form": base_form,
                "doctor_profile_form": doctor_form,
                "patient_profile_form": patient_form,
                "change_password_form": change_password_form,
                "password_updated": password_updated,
                "base_profile_updated": base_profile_updated,
                "doctor_profile_updated": doctor_profile_updated,
                "patient_profile_updated": patient_profile_updated,
                "doctor_profile": doctor_profile,
                "patient_profile": patient_profile,
                "doctor_profile_missing": doctor_profile_missing,
                "patient_profile_missing": patient_profile_missing,
                "edit_mode": edit_mode,
                "current_section": "profile",
            },
        )

       
def activate_account(request,uid, token):
    user = VerificationService.verify(uid, token)
    if user and not user.is_active:
        user.is_active = True
        user.last_login = timezone.now()
        user.save()
        return render(request, "accounts/activation_success.html")
    else:
        return render(request, "accounts/activation_failed.html")

