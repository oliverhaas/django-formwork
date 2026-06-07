"""Views for the simple formwork example."""

from django.shortcuts import render

from .forms import (
    ContactForm,
    TicketEditForm,
    TicketTitleForm,
    TicketValidatedForm,
    TicketWidgetsForm,
)
from .models import Ticket


def contact_view(request):
    """Render the contact form with htmx morph support."""
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            # In a real app you'd process the data here.
            return render(request, "success.html", {"data": form.cleaned_data})
    else:
        form = ContactForm()

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        # htmx request — return just the form HTML for morphing.
        return render(request, "form_partial.html", {"form": form})
    return render(request, "contact.html", {"form": form})


def cookbook_step1(request):
    return render(request, "cookbook/step1.html", {"form": TicketTitleForm()})


def cookbook_step2(request):
    return render(request, "cookbook/step2.html", {"form": TicketWidgetsForm()})


def cookbook_step3(request):
    """Server-side validation that morphs the form back in on error."""
    if request.method == "POST":
        form = TicketValidatedForm(request.POST)
        form.is_valid()
        if request.headers.get("HX-Request") == "true":
            return render(request, "cookbook/_ticket_form.html", {"form": form, "action": "ck-step3"})
        return render(request, "cookbook/step3.html", {"form": form})
    return render(request, "cookbook/step3.html", {"form": TicketValidatedForm()})


def cookbook_step4(request):
    """Edit the seeded legacy ticket with validate_dirty_only."""
    ticket = Ticket.objects.order_by("pk").first()
    if request.method == "POST":
        form = TicketEditForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
        if request.headers.get("HX-Request") == "true":
            return render(request, "cookbook/_ticket_form.html", {"form": form, "action": "ck-step4"})
        return render(request, "cookbook/step4.html", {"form": form})
    return render(request, "cookbook/step4.html", {"form": TicketEditForm(instance=ticket)})
