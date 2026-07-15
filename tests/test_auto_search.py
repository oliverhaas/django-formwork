"""Tests for auto-search registry: registration, auto-wiring, and dispatch view."""

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.test import RequestFactory

from django_formwork._registry import (
    SearchRegistration,
    clear_registry,
    get_registration,
    get_registry,
    make_choices_key,
    make_key,
    register,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear the registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


# ---------------------------------------------------------------------------
# make_key
# ---------------------------------------------------------------------------


class TestMakeKey:
    @pytest.fixture
    def form_cls(self):
        class MyForm:
            pass

        MyForm.__module__ = "myapp.forms"
        MyForm.__qualname__ = "MyForm"
        return MyForm

    def test_basic_key(self, form_cls):
        assert make_key(form_cls, "user", "myapp.mymodel", ["name"]) == "myapp.forms.myform.user.myapp.mymodel.name"

    def test_multiple_fields_sorted(self, form_cls):
        assert (
            make_key(form_cls, "user", "myapp.mymodel", ["name", "code", "email"])
            == "myapp.forms.myform.user.myapp.mymodel.code,email,name"
        )

    def test_custom_to_field_name(self, form_cls):
        assert (
            make_key(form_cls, "user", "myapp.mymodel", ["name"], to_field_name="slug")
            == "myapp.forms.myform.user.myapp.mymodel.name.slug"
        )

    def test_pk_default_no_suffix(self, form_cls):
        assert (
            make_key(form_cls, "user", "myapp.mymodel", ["name"], to_field_name="pk")
            == "myapp.forms.myform.user.myapp.mymodel.name"
        )

    def test_form_class_discriminates(self, form_cls):
        """SECURITY: two forms on the same model+fields must not share a key."""

        class OtherForm:
            pass

        OtherForm.__module__ = "myapp.forms"
        OtherForm.__qualname__ = "OtherForm"
        assert make_key(form_cls, "user", "myapp.mymodel", ["name"]) != make_key(
            OtherForm,
            "user",
            "myapp.mymodel",
            ["name"],
        )

    def test_field_name_discriminates(self, form_cls):
        """Two fields in the same form on the same model+fields get distinct keys."""
        assert make_key(form_cls, "owner", "myapp.mymodel", ["name"]) != make_key(
            form_cls,
            "manager",
            "myapp.mymodel",
            ["name"],
        )


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
        reg = get_registration(make_key(F, "user", "auth.user", ["username"]))
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
        reg = get_registration(make_key(F, "user", "auth.user", ["username", "email"]))
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
        assert widget._registry_key == make_key(F, "user", "auth.user", ["username"])

    def test_multi_select_auto_registers(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import MultiSelect

        class F(FormworkForm):
            users = forms.ModelMultipleChoiceField(
                queryset=User.objects.all(),
                widget=MultiSelect(search_fields=["username"], search_decorator=None),
            )

        F()
        reg = get_registration(make_key(F, "users", "auth.user", ["username"]))
        assert reg is not None
        assert reg.widget_type == "multi_select"

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
        reg = get_registration(make_key(F, "user", "auth.user", ["first_name"], to_field_name="username"))
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
        reg = get_registration(make_key(F, "user", "auth.user", ["username"]))
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
        reg = get_registration(make_key(F, "user", "auth.user", ["username"]))
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
        reg = get_registration(make_key(F, "user", "auth.user", ["username"]))
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
        reg = get_registration(make_key(F, "user", "auth.user", ["username"]))
        assert reg.search_decorator is login_required

    def test_two_forms_same_model_fields_do_not_collide(self):
        """SECURITY: a public form must not overwrite another form's protected registration.

        Regression: keys were built from (model, search_fields, to_field_name)
        only, so the last-instantiated form silently replaced the other's
        search_decorator and queryset for the shared key.
        """
        from functools import wraps

        from django import forms
        from django.http import HttpResponse

        from django_formwork.forms import FormworkForm
        from django_formwork.views import FormworkAutoSearchView
        from django_formwork.widgets import SearchSelect

        def deny_all(view_func):
            @wraps(view_func)
            def wrapper(request, *args, **kwargs):
                return HttpResponse(status=403)

            return wrapper

        class ProtectedForm(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.filter(is_staff=True),
                widget=SearchSelect(search_fields=["username"], search_decorator=deny_all),
            )

        class PublicForm(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        protected_key = ProtectedForm().fields["user"].widget._registry_key
        public_key = PublicForm().fields["user"].widget._registry_key

        assert protected_key != public_key
        assert get_registration(protected_key).search_decorator is deny_all
        assert get_registration(public_key).search_decorator is None

        # Dispatching the protected key is still denied after the public form registered.
        request = factory.get("/search/", {"q": ""})
        assert FormworkAutoSearchView.as_view()(request, key=protected_key).status_code == 403
        assert FormworkAutoSearchView.as_view()(request, key=public_key).status_code == 200

    def test_two_fields_same_model_fields_get_distinct_registrations(self):
        """Two fields in one form on the same model+search_fields keep their own querysets."""
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            owner = forms.ModelChoiceField(
                queryset=User.objects.filter(is_staff=True),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )
            member = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], search_decorator=None),
            )

        form = F()
        owner_key = form.fields["owner"].widget._registry_key
        member_key = form.fields["member"].widget._registry_key
        assert owner_key != member_key
        assert str(get_registration(owner_key).queryset_factory().query) != str(
            get_registration(member_key).queryset_factory().query,
        )


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
        class UserForm:
            pass

        reg = SearchRegistration(
            queryset_factory=User.objects.all,
            search_fields=("username", "first_name"),
        )
        key = make_key(UserForm, "user", "auth.user", ["username", "first_name"])
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
        """search_decorator=None means public: no auth check."""
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

    def test_no_oob_total_count_in_response(self, registered_key):
        """The response is just the option markup, not an OOB total swap: widgets know the total at render time from the registry."""
        from django_formwork.views import FormworkAutoSearchView

        request = factory.get("/search/", {"q": "", "type": "search_select", "name": "user"})
        response = FormworkAutoSearchView.as_view()(request, key=registered_key)
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.find(attrs={"hx-swap-oob": True}) is None

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

    def test_multi_select_widget_type(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=User.objects.all,
            search_fields=("username",),
            widget_type="multi_select",
        )
        register("test.multi", reg)

        request = factory.get("/search/", {"q": "", "name": "users"})
        response = FormworkAutoSearchView.as_view()(request, key="test.multi")
        soup = BeautifulSoup(response.content, "html.parser")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        assert len(checkboxes) == 3

    def test_widget_type_forced_from_registration(self):
        """SECURITY: the client 'type' param is ignored; the registration decides the template."""
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=User.objects.all,
            search_fields=("username",),
            widget_type="multi_select",
        )
        register("test.forced", reg)

        request = factory.get("/search/", {"q": "", "type": "combo_box", "name": "users"})
        response = FormworkAutoSearchView.as_view()(request, key="test.forced")
        soup = BeautifulSoup(response.content, "html.parser")
        assert len(soup.find_all("input", {"type": "checkbox"})) == 3
        assert soup.find(attrs={"data-suggestion": True}) is None

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

    def test_multi_select_choices(self):
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
        assert reg.widget_type == "multi_select"

    def test_combo_box_choices(self):
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
        assert reg.widget_type == "combo_box"


# ---------------------------------------------------------------------------
# FormworkAutoSearchView: choices-backed dispatch
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
        """The response is just option markup, not an OOB total swap: widgets know the total at render time from the registry."""
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
