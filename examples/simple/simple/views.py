"""Views for the simple formwork example."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    ContactForm,
    TicketCreateForm,
    TicketEditForm,
    TicketTitleForm,
    TicketUploadForm,
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
        # For an htmx request, return just the form HTML for morphing.
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
        form.is_valid()  # render any errors; the happy path arrives in step 4
        if request.headers.get("HX-Request") == "true":
            return render(request, "cookbook/_ticket_form.html", {"form": form, "action": "ck-step3"})
        return render(request, "cookbook/step3.html", {"form": form})
    return render(request, "cookbook/step3.html", {"form": TicketValidatedForm()})


def cookbook_step4(request):
    """Create the ticket on valid POST, then redirect, htmx-aware."""
    if request.method == "POST":
        form = TicketCreateForm(request.POST)
        if form.is_valid():
            ticket = form.save()
            url = reverse("ck-created", args=[ticket.pk])
            if request.headers.get("HX-Request") == "true":
                return HttpResponse(headers={"HX-Redirect": url})
            return redirect(url)
        if request.headers.get("HX-Request") == "true":
            return render(request, "cookbook/_ticket_form.html", {"form": form, "action": "ck-step4"})
        return render(request, "cookbook/step4.html", {"form": form})
    return render(request, "cookbook/step4.html", {"form": TicketCreateForm()})


def cookbook_step5(request):
    """Step 4 plus a screenshot drop zone; uploads arrive in request.FILES."""
    if request.method == "POST":
        form = TicketUploadForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save()
            url = reverse("ck-created", args=[ticket.pk])
            if request.headers.get("HX-Request") == "true":
                return HttpResponse(headers={"HX-Redirect": url})
            return redirect(url)
        if request.headers.get("HX-Request") == "true":
            return render(request, "cookbook/_ticket_form.html", {"form": form, "action": "ck-step5"})
        return render(request, "cookbook/step5.html", {"form": form})
    return render(request, "cookbook/step5.html", {"form": TicketUploadForm()})


def cookbook_created(request, pk):
    """Redirect target for the create steps."""
    ticket = get_object_or_404(Ticket, pk=pk)
    return render(request, "cookbook/created.html", {"ticket": ticket})


def cookbook_step6(request):
    """Edit the seeded legacy ticket with validate_dirty_only."""
    ticket = Ticket.objects.order_by("pk").first()
    if request.method == "POST":
        form = TicketEditForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
        if request.headers.get("HX-Request") == "true":
            return render(request, "cookbook/_ticket_form.html", {"form": form, "action": "ck-step6"})
        return render(request, "cookbook/step6.html", {"form": form})
    return render(request, "cookbook/step6.html", {"form": TicketEditForm(instance=ticket)})
