"""Tests for auto-search registry: registration, auto-wiring, and dispatch view."""

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.test import RequestFactory

from django_formwork.registry import (
    SearchRegistration,
    get_registration,
    get_registry,
    make_choices_key,
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
    def test_basic_key(self):
        assert make_key("myapp.mymodel", ["name"]) == "myapp.mymodel.name"

    def test_multiple_fields_sorted(self):
        assert make_key("myapp.mymodel", ["name", "code", "email"]) == "myapp.mymodel.code,email,name"

    def test_custom_to_field_name(self):
        assert make_key("myapp.mymodel", ["name"], to_field_name="slug") == "myapp.mymodel.name.slug"

    def test_pk_default_no_suffix(self):
        assert make_key("myapp.mymodel", ["name"], to_field_name="pk") == "myapp.mymodel.name"


# ---------------------------------------------------------------------------
# register / get_registration / get_registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_and_get(self):
        reg = SearchRegistration(queryset_factory=lambda: None, search_fields=("name",))
        register("test.key", reg)
        assert get_registration("test.key") is reg

    def test_get_missing_returns_none(self):
        assert get_registration("nonexistent") is None

    def test_register_idempotent(self):
        reg1 = SearchRegistration(queryset_factory=lambda: None, search_fields=("a",))
        reg2 = SearchRegistration(queryset_factory=lambda: None, search_fields=("b",))
        register("key", reg1)
        register("key", reg2)
        assert get_registration("key") is reg2

    def test_get_registry_returns_all(self):
        reg = SearchRegistration(queryset_factory=lambda: None, search_fields=("a",))
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

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
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

        F()
        reg = get_registration(make_key("auth.user", ["username", "email"]))
        assert reg is not None

    def test_skips_widget_without_search_fields(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_decorator=None),
            )

        F()
        assert len(get_registry()) == 0

    def test_skips_explicit_search_url(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_url="/my/url/", search_fields=["username"]),
            )

        F()
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

        F()
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
        assert widget._registry_key == make_key("auth.user", ["username"])

    def test_multiselect_auto_registers(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import MultiSelect

        class F(FormworkForm):
            users = forms.ModelMultipleChoiceField(
                queryset=User.objects.all(),
                widget=MultiSelect(search_fields=["username"], search_decorator=None),
            )

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
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

        F()
        reg = get_registration(make_key("auth.user", ["first_name"], to_field_name="username"))
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

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
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

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
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

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
        qs = reg.queryset_factory()
        assert qs.model is User

    def test_missing_search_decorator_raises(self):
        """Omitting search_decorator on a widget with search_fields raises ImproperlyConfigured."""
        from django import forms
        from django.core.exceptions import ImproperlyConfigured

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"]),
            )

        with pytest.raises(ImproperlyConfigured, match="search_decorator"):
            F()

    def test_missing_search_decorator_choices_raises(self):
        """Omitting search_decorator with a search_choices_ method raises ImproperlyConfigured."""
        from django import forms
        from django.core.exceptions import ImproperlyConfigured

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class CityForm(FormworkForm):
            city = forms.ChoiceField(choices=_CITIES, widget=SearchSelect())

            @staticmethod
            def search_choices_city(query, request=None):
                return _search_cities(query, request)

        with pytest.raises(ImproperlyConfigured, match="search_decorator"):
            CityForm()

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

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
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
            queryset_factory=User.objects.all,
            search_fields=("username", "first_name"),
        )
        key = make_key("auth.user", ["username", "first_name"])
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
            queryset_factory=User.objects.all,
            search_fields=("username",),
            search_decorator=deny_all,
        )
        key = "test.protected"
        register(key, reg)

        request = factory.get("/search/", {"q": ""})
        response = FormworkAutoSearchView.as_view()(request, key=key)
        assert response.status_code == 403

    def test_search_decorator_none_allows_anonymous(self):
        """search_decorator=None means public — no auth check."""
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=User.objects.all,
            search_fields=("username",),
            search_decorator=None,
        )
        key = "test.public"
        register(key, reg)

        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key=key)
        assert response.status_code == 200

    def test_total_count_oob(self, registered_key):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "", "type": "search_select", "name": "user"})
        response = FormworkAutoSearchView.as_view()(request, key=registered_key)
        soup = BeautifulSoup(response.content, "html.parser")
        total_input = soup.find("input", {"type": "hidden"})
        assert total_input is not None
        assert total_input["value"] == "3"
        assert total_input.get("hx-swap-oob") == "true"

    def test_custom_label_from_instance(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=User.objects.all,
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
            queryset_factory=User.objects.all,
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
            queryset_factory=User.objects.all,
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
            queryset_factory=User.objects.all,
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
            queryset_factory=User.objects.all,
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
            queryset_factory=User.objects.all,
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
            queryset_factory=User.objects.all,
            search_fields=("username",),
        )
        register("test.noresults", reg)

        request = factory.get("/search/", {"q": "zzzzz", "type": "search_select"})
        response = FormworkAutoSearchView.as_view()(request, key="test.noresults")
        assert b"No results" in response.content


# ---------------------------------------------------------------------------
# make_choices_key
# ---------------------------------------------------------------------------


class TestMakeChoicesKey:
    def test_basic_key(self):
        class MyForm:
            pass

        MyForm.__module__ = "myapp.forms"
        MyForm.__qualname__ = "MyForm"
        assert make_choices_key(MyForm, "city") == "myapp.forms.myform.city"

    def test_nested_class(self):
        class Outer:
            class Inner:
                pass

        Outer.Inner.__module__ = "myapp.forms"
        Outer.Inner.__qualname__ = "Outer.Inner"
        key = make_choices_key(Outer.Inner, "color")
        assert key == "myapp.forms.outer.inner.color"


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

        CityForm()
        key = make_choices_key(CityForm, "city")
        reg = get_registration(key)
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
        assert widget._registry_key == make_choices_key(CityForm, "city")

    def test_skips_without_search_choices_method(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class CityForm(FormworkForm):
            city = forms.ChoiceField(choices=_CITIES, widget=SearchSelect(search_decorator=None))

        CityForm()
        assert len(get_registry()) == 0

    def test_skips_explicit_search_url(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class CityForm(FormworkForm):
            city = forms.ChoiceField(
                choices=_CITIES,
                widget=SearchSelect(search_url="/my/url/"),
            )

            @staticmethod
            def search_choices_city(query, request=None):
                return _search_cities(query, request)

        CityForm()
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

        CityForm()
        key = make_choices_key(CityForm, "cities")
        reg = get_registration(key)
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

        TagForm()
        key = make_choices_key(TagForm, "tag")
        reg = get_registration(key)
        assert reg is not None
        assert reg.widget_type == "combobox"


# ---------------------------------------------------------------------------
# FormworkAutoSearchView — choices-backed dispatch
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

    def test_total_count_oob(self, choices_key):
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "lon", "type": "search_select", "name": "city"})
        response = FormworkAutoSearchView.as_view()(request, key=choices_key)
        soup = BeautifulSoup(response.content, "html.parser")
        total_input = soup.find("input", {"type": "hidden"})
        assert total_input is not None
        # Total is always the UNFILTERED count.
        assert total_input["value"] == "5"

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
