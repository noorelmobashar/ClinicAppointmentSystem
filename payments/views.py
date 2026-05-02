import stripe
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
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
def CreateCheckoutSessionView(request, appointment_id):
    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient=request.user,
        status=Appointment.Status.AWAITING_PAYMENT,
    )
    
    slot = appointment.slot

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
            "appointment_id": str(appointment.id),
        },
    )
    
    PaymentTransaction.objects.get_or_create(
        appointment=appointment,
        defaults={
            'stripe_checkout_id': session.id,
            'amount': CONSULTATION_FEE,
            'status': PaymentTransaction.Status.PENDING,
        }
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
        appointment_id = session.metadata.get("appointment_id")

        if not appointment_id:
            return HttpResponse(status=200)

        with transaction.atomic():
            try:
                appointment = Appointment.objects.select_for_update().get(id=appointment_id)
            except Appointment.DoesNotExist:
                return HttpResponse(status=200)

            slot = AppointmentSlot.objects.select_for_update().get(id=appointment.slot_id)
            
            # Retrieve the transaction
            try:
                txn = PaymentTransaction.objects.get(appointment=appointment)
            except PaymentTransaction.DoesNotExist:
                txn = None

            if slot.is_booked and appointment.status != Appointment.Status.CONFIRMED:
                # Slot was taken by someone else who paid first
                if session.payment_intent:
                    stripe.Refund.create(payment_intent=session.payment_intent)
                
                appointment.status = Appointment.Status.CANCELLED
                appointment.save(update_fields=["status"])
                if txn:
                    txn.status = PaymentTransaction.Status.FAILED
                    txn.save(update_fields=["status"])
                    
                return HttpResponse(status=200)

            # Slot is free! Book it.
            slot.is_booked = True
            slot.save(update_fields=["is_booked"])

            appointment.status = Appointment.Status.CONFIRMED
            appointment.save(update_fields=["status"])

            if txn:
                txn.stripe_checkout_id = session.id
                txn.status = PaymentTransaction.Status.PAID
                txn.paid_at = now()
                txn.save(update_fields=["stripe_checkout_id", "status", "paid_at"])
                
            # Cancel all OTHER awaiting appointments for this slot
            Appointment.objects.filter(
                slot=slot,
                status=Appointment.Status.AWAITING_PAYMENT
            ).exclude(id=appointment.id).update(status=Appointment.Status.CANCELLED)

    elif event.type in ["checkout.session.expired", "checkout.session.async_payment_failed"]:
        session = event.data.object
        appointment_id = session.metadata.get("appointment_id")
        
        if appointment_id:
            with transaction.atomic():
                try:
                    appointment = Appointment.objects.get(id=appointment_id)
                    appointment.status = Appointment.Status.CANCELLED
                    appointment.save(update_fields=["status"])
                    
                    PaymentTransaction.objects.filter(appointment=appointment).update(
                        status=PaymentTransaction.Status.FAILED
                    )
                except Appointment.DoesNotExist:
                    pass

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
