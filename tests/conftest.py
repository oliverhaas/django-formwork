import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import MultiSelect, Range, Rating, Toggle


def pytest_addoption(parser):
    parser.addoption(
        "--update-screenshots",
        action="store_true",
        default=False,
        help="Regenerate screenshot baselines instead of comparing.",
    )


class SimpleForm(forms.Form):
    name = forms.CharField(help_text="Your full name")
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)


class AllWidgetsForm(FormworkForm):
    text = forms.CharField()
    email = forms.EmailField()
    url = forms.URLField()
    number = forms.IntegerField()
    password = forms.CharField(widget=forms.PasswordInput)
    textarea = forms.CharField(widget=forms.Textarea)
    checkbox = forms.BooleanField(required=False)
    select = forms.ChoiceField(choices=[("a", "A"), ("b", "B")])
    radio = forms.ChoiceField(
        choices=[("x", "X"), ("y", "Y")],
        widget=forms.RadioSelect,
    )
    multi_checkbox = forms.MultipleChoiceField(
        choices=[("1", "One"), ("2", "Two")],
        widget=forms.CheckboxSelectMultiple,
    )
    date = forms.DateField()
    file = forms.FileField(required=False)
    hidden = forms.CharField(widget=forms.HiddenInput)
    color = forms.CharField(widget=forms.ColorInput, required=False)
    phone = forms.CharField(widget=forms.TelInput, required=False)
    search = forms.CharField(widget=forms.SearchInput, required=False)
    select_multiple = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B")],
        widget=forms.SelectMultiple,
        required=False,
    )
    multi_select_dropdown = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B")],
        widget=MultiSelect,
        required=False,
    )


class CustomWidgetsForm(FormworkForm):
    toggle = forms.BooleanField(widget=Toggle, required=False)
    volume = forms.IntegerField(widget=Range(attrs={"min": "0", "max": "100"}))
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
    )


class SimpleFormworkForm(FormworkForm):
    name = forms.CharField(help_text="Your full name")
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)


@pytest.fixture
def simple_form():
    return SimpleForm()


@pytest.fixture
def all_widgets_form():
    return AllWidgetsForm()


@pytest.fixture
def custom_widgets_form():
    return CustomWidgetsForm()


@pytest.fixture
def simple_formwork_form():
    return SimpleFormworkForm()


@pytest.fixture
def bound_form_with_errors():
    form = SimpleFormworkForm(data={"name": "", "email": "bad", "message": ""})
    form.is_valid()
    return form


@pytest.fixture(autouse=True)
def _reregister_e2e_search(request):
    """Re-establish the e2e forms' search registrations before each browser test.

    Search endpoints register once, in the form metaclass, when a form module
    is imported (see ``django_formwork.registry``).  In production nothing ever
    clears that registry, but the autouse registry-cleanup fixtures wipe it
    between tests for isolation, and Python will not re-import an already-loaded
    module.  Without this, the in-process live server would 404 on every search
    endpoint after the first test that clears the registry.  Re-registering is
    idempotent and yields the same opaque keys, so the rendered widgets keep
    resolving to a live endpoint.
    """
    if request.node.get_closest_marker("e2e") is None:
        return

    import inspect

    # Imported as ``e2e.views`` (not ``tests.e2e.views``) so the module label,
    # and therefore the registry keys, match what the live server renders.
    import e2e.views as e2e_views

    from django_formwork.forms import FormworkForm, FormworkModelForm, _register_search_widgets

    for _name, obj in inspect.getmembers(e2e_views, inspect.isclass):
        if issubclass(obj, (FormworkForm, FormworkModelForm)) and obj.__module__ == e2e_views.__name__:
            _register_search_widgets(obj)
