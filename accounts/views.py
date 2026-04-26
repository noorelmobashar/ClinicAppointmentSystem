from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password
from .forms import LoginForm, RegisterForm
from .models import CustomUser


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
                user = CustomUser.objects.get(email=email)
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
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            return redirect('login')
        return render(request, "accounts/register.html", {'form': form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("login")

    def post(self, request):
        logout(request)
        return redirect("login")

