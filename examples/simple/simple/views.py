"""Views for the simple formwork example."""

from django.shortcuts import render

from .forms import ContactForm


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
