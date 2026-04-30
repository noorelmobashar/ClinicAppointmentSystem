from django.urls import path
from .views import (
    CustomLoginView,
    LogoutView,
    CustomRegisterView,
    CustomForgotPasswordView,
    CustomResetPasswordView,
    activate_account,
)

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', CustomRegisterView.as_view(), name='register'),
    path('forgot-password/', CustomForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/<uid>/<token>/', CustomResetPasswordView.as_view(), name='reset_password'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify/<uid>/<token>/', activate_account, name='activate'),
]
