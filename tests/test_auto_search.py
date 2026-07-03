"""Tests for auto-search registry: registration, auto-wiring, and dispatch view."""

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.test import RequestFactory

from django_formwork.registry import (
    SearchRegistration,
    form_label,
    get_registration,
    get_registry,
    make_key,
    register,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear the registry before and after each test."""
    get_registry().clear()
    yield
    get_registry().clear()


# ---------------------------------------------------------------------------
# make_key
# ---------------------------------------------------------------------------


class TestMakeKey:
    def test_deterministic(self):
        class F:
            pass

        assert make_key(F, "city") == make_key(F, "city")

    def test_fixed_length_hex(self):
        class F:
            pass

        key = make_key(F, "city")
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_opaque_no_leaked_paths(self):
        """The key must not expose the field name or the module path."""

        class F:
            pass

        key = make_key(F, "city")
        assert "city" not in key
        assert F.__module__ not in key

    def test_distinct_per_field(self):
        class F:
            pass

        assert make_key(F, "city") != make_key(F, "country")

    def test_distinct_per_form(self):
        class A:
            pass

        class B:
            pass

        assert make_key(A, "city") != make_key(B, "city")

    def test_form_label_is_module_and_qualname(self):
        class F:
            pass

        assert form_label(F) == f"{F.__module__}.{F.__qualname__}"


# ---------------------------------------------------------------------------
# register / get_registration / get_registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_and_get(self):
        reg = SearchRegistration(queryset_factory=lambda request: None, search_fields=("name",))
        register("test.key", reg)
        assert get_registration("test.key") is reg

    def test_get_missing_returns_none(self):
        assert get_registration("nonexistent") is None

    def test_register_idempotent(self):
        reg1 = SearchRegistration(queryset_factory=lambda request: None, search_fields=("a",))
        reg2 = SearchRegistration(queryset_factory=lambda request: None, search_fields=("b",))
        register("key", reg1)
        register("key", reg2)
        assert get_registration("key") is reg2

    def test_get_registry_returns_all(self):
        reg = SearchRegistration(queryset_factory=lambda request: None, search_fields=("a",))
        register("k1", reg)
        register("k2", reg)
        assert len(get_registry()) == 2


# ---------------------------------------------------------------------------
# Auto-registration via FormworkForm / FormworkModelForm
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAutoRegistration:
    def test_formwork_form_auto_registers(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        reg = get_registration(make_key(F, "user"))
        assert reg is not None
        assert reg.search_fields == ("username",)
        assert reg.to_field_name == "pk"
        assert reg.widget_type == "search_select"

    def test_formwork_model_form_auto_registers(self):
        from django import forms

        from django_formwork.forms import FormworkModelForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkModelForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username", "email"], search_decorator=None),
            )

            class Meta:
                model = User
                fields = []

        reg = get_registration(make_key(F, "user"))
        assert reg is not None
        assert reg.search_fields == ("username", "email")

    def test_registration_happens_at_class_definition(self):
        """Registration is done by the metaclass, before any instance exists."""
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        # No F() call: the endpoint exists purely from defining the class.
        assert get_registration(make_key(F, "user")) is not None

    def test_two_forms_same_model_do_not_collide(self):
        """Per-form-field keys mean two forms searching one model get two endpoints."""
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class A(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        class B(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        assert make_key(A, "user") != make_key(B, "user")
        assert get_registration(make_key(A, "user")) is not None
        assert get_registration(make_key(B, "user")) is not None
        assert len(get_registry()) == 2

    def test_skips_widget_without_search_fields(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_decorator=None),
            )

        assert len(get_registry()) == 0

    def test_skips_non_model_field(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            city = forms.ChoiceField(
                choices=[("a", "A")],
                widget=SearchSelect(search_fields=["name"], search_decorator=None),
            )

        assert len(get_registry()) == 0

    def test_sets_registry_key_on_widget(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        form = F()
        widget = form.fields["user"].widget
        assert widget._registry_key == make_key(F, "user")

    def test_multiselect_auto_registers(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import MultiSelect

        class F(FormworkForm):
            users = forms.ModelMultipleChoiceField(
                queryset=User.objects.all(),
                widget=MultiSelect(search_fields=["username"], search_decorator=None),
            )

        reg = get_registration(make_key(F, "users"))
        assert reg is not None
        assert reg.widget_type == "multiselect"

    def test_custom_to_field_name(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                to_field_name="username",
                widget=SearchSelect(search_fields=["first_name"], search_decorator=None),
            )

        reg = get_registration(make_key(F, "user"))
        assert reg is not None
        assert reg.to_field_name == "username"

    def test_captures_label_from_instance(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class MyField(forms.ModelChoiceField):
            def label_from_instance(self, obj):
                return f"User: {obj.username}"

        class F(FormworkForm):
            user = MyField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        reg = get_registration(make_key(F, "user"))
        assert reg.label_from_instance is not None

    def test_captures_icon_from_instance(self):
        from django_formwork.fields import FormworkModelChoiceField
        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        def my_icon(obj):
            return f"<img src='{obj.pk}.png'>"

        class F(FormworkForm):
            user = FormworkModelChoiceField(
                queryset=User.objects.all(),
                icon_from_instance=my_icon,
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        reg = get_registration(make_key(F, "user"))
        assert reg.icon_from_instance is not None

    def test_queryset_factory_returns_fresh_qs(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        reg = get_registration(make_key(F, "user"))
        # Render-time call passes None (no request available yet).
        qs = reg.queryset_factory(None)
        assert qs.model is User

    def test_search_queryset_used_as_request_scoped_factory(self):
        """A widget's search_queryset becomes the request-scoped factory."""
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        sentinel = User.objects.filter(is_staff=True)

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(
                    search_fields=["username"],
                    search_decorator=None,
                    search_queryset=lambda request: sentinel,
                ),
            )

        reg = get_registration(make_key(F, "user"))
        assert reg.queryset_factory(None) is sentinel

    def test_missing_search_decorator_raises(self):
        """Omitting search_decorator on a widget with search_fields raises at class definition."""
        from django import forms
        from django.core.exceptions import ImproperlyConfigured

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        with pytest.raises(ImproperlyConfigured, match="search_decorator"):

            class F(FormworkForm):
                user = forms.ModelChoiceField(
                    queryset=User.objects.all(),
                    widget=SearchSelect(search_fields=["username"]),
                )

    def test_missing_search_decorator_choices_raises(self):
        """Omitting search_decorator with a search_choices_ method raises at class definition."""
        from django import forms
        from django.core.exceptions import ImproperlyConfigured

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        with pytest.raises(ImproperlyConfigured, match="search_decorator"):

            class CityForm(FormworkForm):
                city = forms.ChoiceField(choices=_CITIES, widget=SearchSelect())

                @staticmethod
                def search_choices_city(query, request=None):
                    return _search_cities(query, request)

    def test_search_decorator_stored_in_registration(self):
        """The search_decorator value is stored in the SearchRegistration."""
        from django import forms
        from django.contrib.auth.decorators import login_required

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=login_required),
            )

        reg = get_registration(make_key(F, "user"))
        assert reg.search_decorator is login_required


# ---------------------------------------------------------------------------
# FormworkAutoSearchView
# ---------------------------------------------------------------------------

factory = RequestFactory()


@pytest.mark.django_db
class TestFormworkAutoSearchView:
    @pytest.fixture(autouse=True)
    def _create_users(self):
        User.objects.create_user("alice", "alice@example.com", first_name="Alice")
        User.objects.create_user("bob", "bob@example.com", first_name="Bob")
        User.objects.create_user("charlie", "charlie@example.com", first_name="Charlie")

    @pytest.fixture
    def registered_key(self):
        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username", "first_name"),
        )
        key = "test.users"
        register(key, reg)
        return key

    def test_returns_all_results(self, registered_key):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "", "type": "search_select", "name": "user"})
        response = FormworkAutoSearchView.as_view()(request, key=registered_key)
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 3

    def test_filters_by_query(self, registered_key):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "ali", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key=registered_key)
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 1
        assert "alice" in buttons[0].get_text()

    def test_request_scoped_queryset_factory_receives_request(self):
        """The dispatch view calls the queryset factory with the live request."""
        from django_formwork.views import FormworkAutoSearchView

        seen = {}

        def factory_fn(request):
            seen["request"] = request
            return User.objects.all()

        reg = SearchRegistration(queryset_factory=factory_fn, search_fields=("username",))
        register("test.scoped", reg)

        request = factory.get("/search/", {"q": "", "type": "search_select"})
        FormworkAutoSearchView.as_view()(request, key="test.scoped")
        assert seen["request"] is request

    def test_returns_404_for_unknown_key(self):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": ""})
        response = FormworkAutoSearchView.as_view()(request, key="nonexistent.key")
        assert response.status_code == 404

    def test_search_decorator_applied(self):
        """A search_decorator is applied at dispatch time."""
        from functools import wraps

        from django.http import HttpResponse

        from django_formwork.views import FormworkAutoSearchView

        def deny_all(view_func):
            @wraps(view_func)
            def wrapper(request, *args, **kwargs):
                return HttpResponse(status=403)

            return wrapper

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            search_decorator=deny_all,
        )
        key = "test.protected"
        register(key, reg)

        request = factory.get("/search/", {"q": ""})
        response = FormworkAutoSearchView.as_view()(request, key=key)
        assert response.status_code == 403

    def test_search_decorator_none_allows_anonymous(self):
        """search_decorator=None means public, no auth check."""
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            search_decorator=None,
        )
        key = "test.public"
        register(key, reg)

        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key=key)
        assert response.status_code == 200

    def test_no_oob_total_count_in_response(self, registered_key):
        """The response is just the option markup, with no OOB total swap.
        Widgets know the total at render time from the registry."""
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "", "type": "search_select", "name": "user"})
        response = FormworkAutoSearchView.as_view()(request, key=registered_key)
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.find(attrs={"hx-swap-oob": True}) is None

    def test_custom_label_from_instance(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            label_from_instance=lambda obj: f"USER:{obj.username}",
        )
        register("test.label", reg)

        request = factory.get("/search/", {"q": "alice", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.label")
        assert b"USER:alice" in response.content

    def test_icon_from_instance(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            icon_from_instance=lambda obj: f"icon-{obj.username}",
        )
        register("test.icon", reg)

        request = factory.get("/search/", {"q": "bob", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.icon")
        assert b"icon-bob" in response.content

    def test_description_from_instance(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            description_from_instance=lambda obj: obj.email,
        )
        register("test.desc", reg)

        request = factory.get("/search/", {"q": "alice", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.desc")
        assert b"alice@example.com" in response.content

    def test_custom_to_field_name(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            to_field_name="username",
        )
        register("test.tofield", reg)

        request = factory.get("/search/", {"q": "alice", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.tofield")
        soup = BeautifulSoup(response.content, "html.parser")
        btn = soup.find("button")
        assert btn["data-value"] == "alice"

    def test_max_results_limits_output(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            max_results=2,
        )
        register("test.max", reg)

        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.max")
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 2

    def test_multiselect_widget_type(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
            widget_type="multiselect",
        )
        register("test.multi", reg)

        request = factory.get("/search/", {"q": "", "type": "multiselect", "name": "users"})
        response = FormworkAutoSearchView.as_view()(request, key="test.multi")
        soup = BeautifulSoup(response.content, "html.parser")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        assert len(checkboxes) == 3

    def test_no_results_message(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=lambda request: User.objects.all(),
            search_fields=("username",),
        )
        register("test.noresults", reg)

        request = factory.get("/search/", {"q": "zzzzz", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.noresults")
        assert b"No results" in response.content


# ---------------------------------------------------------------------------
# Choices-backed auto-registration
# ---------------------------------------------------------------------------

_CITIES = [
    ("nyc", "New York"),
    ("ldn", "London"),
    ("par", "Paris"),
    ("tky", "Tokyo"),
    ("syd", "Sydney"),
]


def _search_cities(query, request=None):
    if not query:
        return _CITIES
    return [(v, lbl) for v, lbl in _CITIES if query.lower() in lbl.lower()]


class TestChoicesAutoRegistration:
    def test_registers_search_choices_method(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class CityForm(FormworkForm):
            city = forms.ChoiceField(
                choices=_CITIES,
                widget=SearchSelect(search_decorator=None),
            )

            @staticmethod
            def search_choices_city(query, request=None):
                return _search_cities(query, request)

        reg = get_registration(make_key(CityForm, "city"))
        assert reg is not None
        assert reg.search_func is not None
        assert reg.widget_type == "search_select"

    def test_sets_registry_key_on_widget(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class CityForm(FormworkForm):
            city = forms.ChoiceField(choices=_CITIES, widget=SearchSelect(search_decorator=None))

            @staticmethod
            def search_choices_city(query, request=None):
                return _search_cities(query, request)

        form = CityForm()
        widget = form.fields["city"].widget
        assert widget._registry_key == make_key(CityForm, "city")

    def test_skips_without_search_choices_method(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class CityForm(FormworkForm):
            city = forms.ChoiceField(choices=_CITIES, widget=SearchSelect(search_decorator=None))

        assert len(get_registry()) == 0

    def test_multiselect_choices(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import MultiSelect

        class CityForm(FormworkForm):
            cities = forms.MultipleChoiceField(choices=_CITIES, widget=MultiSelect(search_decorator=None))

            @staticmethod
            def search_choices_cities(query, request=None):
                return _search_cities(query, request)

        reg = get_registration(make_key(CityForm, "cities"))
        assert reg is not None
        assert reg.widget_type == "multiselect"

    def test_combobox_choices(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import ComboBox

        class TagForm(FormworkForm):
            tag = forms.CharField(widget=ComboBox(search_decorator=None))

            @staticmethod
            def search_choices_tag(query, request=None):
                tags = ["python", "javascript", "go", "rust"]
                if not query:
                    return [{"value": t, "label": t} for t in tags]
                return [{"value": t, "label": t} for t in tags if query.lower() in t]

        reg = get_registration(make_key(TagForm, "tag"))
        assert reg is not None
        assert reg.widget_type == "combobox"


# ---------------------------------------------------------------------------
# FormworkAutoSearchView, choices-backed dispatch
# ---------------------------------------------------------------------------


class TestAutoSearchViewChoices:
    @pytest.fixture
    def choices_key(self):
        reg = SearchRegistration(
            search_func=_search_cities,
            widget_type="search_select",
        )
        key = "test.choices.city"
        register(key, reg)
        return key

    def test_returns_all_results(self, choices_key):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "", "type": "search_select", "name": "city"})
        response = FormworkAutoSearchView.as_view()(request, key=choices_key)
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 5

    def test_filters_by_query(self, choices_key):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "new", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key=choices_key)
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 1
        assert "New York" in buttons[0].get_text()

    def test_no_oob_total_count_in_response(self, choices_key):
        """The response is just option markup, with no OOB total swap.
        Widgets know the total at render time from the registry."""
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "lon", "type": "search_select", "name": "city"})
        response = FormworkAutoSearchView.as_view()(request, key=choices_key)
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.find(attrs={"hx-swap-oob": True}) is None

    def test_no_results(self, choices_key):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "zzz", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key=choices_key)
        assert b"No results" in response.content

    def test_dict_results(self):
        """search_func can return dicts with extra keys (icon, description)."""
        from django_formwork.views import FormworkAutoSearchView

        def search_with_extras(query, request=None):
            return [
                {"value": "nyc", "label": "New York", "icon": "🗽", "description": "USA"},
            ]

        reg = SearchRegistration(search_func=search_with_extras)
        register("test.dict", reg)

        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.dict")
        content = response.content.decode()
        assert "New York" in content
        assert "🗽" in content
        assert "USA" in content
