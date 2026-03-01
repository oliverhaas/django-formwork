from django.shortcuts import render
from forms import AllWidgetsForm, ContactForm, ErrorStatesForm, RegistrationForm, WidgetShowcaseForm


def index(request):
    if request.method == "POST":
        contact_form = ContactForm(request.POST, prefix="contact")
        showcase_form = WidgetShowcaseForm(request.POST, request.FILES, prefix="showcase")
        all_widgets_form = AllWidgetsForm(request.POST, request.FILES, prefix="all")
        contact_form.is_valid()
        showcase_form.is_valid()
        all_widgets_form.is_valid()
    else:
        contact_form = ContactForm(prefix="contact")
        showcase_form = WidgetShowcaseForm(prefix="showcase")
        all_widgets_form = AllWidgetsForm(prefix="all")

    registration_form = RegistrationForm(prefix="reg")

    # Always render error form pre-bound with empty data to show error states.
    error_form = ErrorStatesForm(data={}, prefix="err")
    error_form.is_valid()

    return render(
        request,
        "index.html",
        {
            "contact_form": contact_form,
            "showcase_form": showcase_form,
            "all_widgets_form": all_widgets_form,
            "registration_form": registration_form,
            "error_form": error_form,
        },
    )
