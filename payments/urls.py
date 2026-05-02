from django.urls import path
from .views import (
    CreateCheckoutSessionView,
    StripeWebhookView,
    PaymentSuccessView,
    PaymentCancelView,
)

urlpatterns = [
    path("checkout/<int:appointment_id>/", CreateCheckoutSessionView, name="stripe-checkout"),
    path("webhook/", StripeWebhookView, name="stripe-webhook"),
    path("success/", PaymentSuccessView, name="payment-success"),
    path("cancel/", PaymentCancelView, name="payment-cancel"),
    path("cancel/<int:appointment_id>/", PaymentCancelView, name="payment-cancel-appointment"),
]
