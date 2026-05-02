from django.contrib import admin
from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("appointment", "stripe_checkout_id", "amount", "status", "created_at", "paid_at")
    list_filter = ("status",)
    search_fields = ("stripe_checkout_id",)
    readonly_fields = ("created_at",)
