import stripe
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from appointments.models import Appointment, AppointmentSlot
from .models import PaymentTransaction

stripe.api_key = settings.STRIPE_SECRET_KEY

# Fixed consultation fee in EGP
CONSULTATION_FEE = Decimal("200.00")


@login_required
def CreateCheckoutSessionView(request, slot_id):

    slot = get_object_or_404(AppointmentSlot, id=slot_id)

    if slot.is_booked:
        messages.error(request, "The session is already booked by another user.")
        return redirect("patient-booking")

    success_url = request.build_absolute_uri("/payments/success/") + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri("/payments/cancel/")

    doctor_name = str(slot.doctor.get_full_name() or slot.doctor.username)
    slot_date = slot.date.strftime("%Y-%m-%d")
    slot_time = slot.start_time.strftime("%H:%M")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "egp",
                    "unit_amount": int(CONSULTATION_FEE * 100),  # Stripe expects cents/piasters
                    "product_data": {
                        "name": f"Consultation with {doctor_name}",
                        "description": f"Appointment on {slot_date} at {slot_time}",
                    },
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "slot_id": str(slot.id),
            "patient_id": str(request.user.id),
        },
    )

    return redirect(session.url)


@csrf_exempt
@require_POST
def StripeWebhookView(request):

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")


    if event.type == "checkout.session.completed":
        session = event.data.object
        slot_id = session.metadata.get("slot_id")
        patient_id = session.metadata.get("patient_id")

        if not slot_id or not patient_id:
            return HttpResponse(status=200)

        with transaction.atomic():
            slot = AppointmentSlot.objects.select_for_update().get(id=slot_id)
            
            if slot.is_booked:
                # Slot was taken by someone else who paid first
                if session.payment_intent:
                    stripe.Refund.create(payment_intent=session.payment_intent)
                return HttpResponse(status=200)

            slot.is_booked = True
            slot.save(update_fields=["is_booked"])

            appointment = Appointment.objects.create(
                patient_id=patient_id,
                doctor=slot.doctor,
                slot=slot,
                status=Appointment.Status.CONFIRMED,
            )

            PaymentTransaction.objects.create(
                appointment=appointment,
                stripe_checkout_id=session.id,
                amount=Decimal(session.amount_total) / 100,
                status=PaymentTransaction.Status.PAID,
                paid_at=now(),
            )

    return HttpResponse(status=200)


@login_required
def PaymentSuccessView(request):

    return render(request, "payments/success.html", {
        "dashboard_title": "Payment Successful",
        "dashboard_subtitle": "Your appointment has been confirmed.",
    })


@login_required
def PaymentCancelView(request):
    
    return render(request, "payments/cancel.html", {
        "dashboard_title": "Payment Cancelled",
        "dashboard_subtitle": "Your appointment was not confirmed.",
    })
