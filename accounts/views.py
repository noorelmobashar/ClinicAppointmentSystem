import os

from django.conf import settings
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password
from .forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm
from .models import CustomUser
from django.core.mail import send_mail
from django.db import transaction
from .utils.return_testmail_recepient import map_to_testmail
from .utils.verification_service import VerificationService
from django.utils import timezone
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
                recepient_email = map_to_testmail(user.email)
                send_mail(
                    subject="Activate Your Account",
                    message=f"Please activate your account using the following link: {verification_link}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recepient_email],
                )
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

                recepient_email = map_to_testmail(user.email)
                send_mail(
                    subject="Reset Your Password",
                    message=f"Please reset your password using the following link: {reset_link}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recepient_email],
                )
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

       
def activate_account(request,uid, token):
    user = VerificationService.verify(uid, token)
    if user and not user.is_active:
        user.is_active = True
        user.last_login = timezone.now()
        user.save()
        return render(request, "accounts/activation_success.html")
    else:
        return render(request, "accounts/activation_failed.html")

