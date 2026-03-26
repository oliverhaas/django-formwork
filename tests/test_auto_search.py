"""Tests for auto-search registry: registration, auto-wiring, and dispatch view."""

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.test import RequestFactory

from django_formwork.registry import (
    SearchRegistration,
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
                widget=SearchSelect(search_fields=["username"]),
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
                widget=SearchSelect(search_fields=["username", "email"]),
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
                widget=SearchSelect(),
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
                widget=SearchSelect(search_fields=["name"]),
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
                widget=SearchSelect(search_fields=["username"]),
            )

        form = F()
        widget = form.fields["user"].widget
        assert widget._registry_key == make_key("auth.user", ["username"])  # noqa: SLF001

    def test_multiselect_auto_registers(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import MultiSelect

        class F(FormworkForm):
            users = forms.ModelMultipleChoiceField(
                queryset=User.objects.all(),
                widget=MultiSelect(search_fields=["username"]),
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
                widget=SearchSelect(search_fields=["first_name"]),
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
                widget=SearchSelect(search_fields=["username"]),
            )

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
        assert reg.label_from_instance is not None

    def test_captures_icon_from_instance(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        def my_icon(obj):
            return f"<img src='{obj.pk}.png'>"

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"], icon_from_instance=my_icon),
            )

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
        assert reg.icon_from_instance is my_icon

    def test_queryset_factory_returns_fresh_qs(self):
        from django import forms

        from django_formwork.forms import FormworkForm
        from django_formwork.widgets import SearchSelect

        class F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=SearchSelect(search_fields=["username"]),
            )

        F()
        reg = get_registration(make_key("auth.user", ["username"]))
        qs = reg.queryset_factory()
        assert qs.model is User


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

    def test_permission_denied(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=User.objects.all,
            search_fields=("username",),
            permission=lambda request: False,
        )
        key = "test.denied"
        register(key, reg)

        request = factory.get("/search/", {"q": ""})
        response = FormworkAutoSearchView.as_view()(request, key=key)
        assert response.status_code == 403

    def test_permission_allowed(self):
        from django_formwork.views import FormworkAutoSearchView

        reg = SearchRegistration(
            queryset_factory=User.objects.all,
            search_fields=("username",),
            permission=lambda request: True,
        )
        key = "test.allowed"
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
