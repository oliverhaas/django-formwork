from django.shortcuts import render
from forms import ContactForm, WidgetShowcaseForm


def index(request):
    if request.method == "POST":
        contact_form = ContactForm(request.POST, prefix="contact")
        showcase_form = WidgetShowcaseForm(request.POST, request.FILES, prefix="showcase")
        contact_form.is_valid()
        showcase_form.is_valid()
    else:
        contact_form = ContactForm(prefix="contact")
        showcase_form = WidgetShowcaseForm(prefix="showcase")

    return render(
        request,
        "index.html",
        {
            "contact_form": contact_form,
            "showcase_form": showcase_form,
        },
    )
