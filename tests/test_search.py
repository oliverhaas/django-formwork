"""Server search: registration at class creation and the endpoint that serves every key.

This module enables postponed annotations on purpose: the registry must read the
string annotations of ``_group_members`` as the param types they name.
"""

from __future__ import annotations

import inspect
from functools import partial
from types import ModuleType
from typing import TYPE_CHECKING, Any

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.checks import Tags, run_checks
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.forms import modelform_factory
from django.test import Client
from django.urls import reverse
from e2e.models import City, Region

from django_formwork import views
from django_formwork.forms import FormworkForm, FormworkModelForm
from django_formwork.search import search_url
from django_formwork.widgets import ComboBox, Select, SelectMultiple
from django_formwork.widgets.select import ChoiceLabel

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.db.models import QuerySet
    from django.http import HttpRequest


@pytest.fixture(autouse=True)
def _search_urls(settings: Any) -> None:
    settings.ROOT_URLCONF = "e2e.urls"


def _make_users(count: int, prefix: str = "user") -> list[User]:
    return User.objects.bulk_create(
        User(username=f"{prefix}{i}", email=f"{prefix}{i}@example.com") for i in range(count)
    )


def _rows(response: Any, selector: str = "[data-value]") -> list[str]:
    soup = BeautifulSoup(response.content.decode(), "html.parser")
    return [str(el["data-value"]) for el in soup.select(selector)]


def _key(form_cls: type[forms.Form], name: str) -> str:
    key = form_cls.base_fields[name].widget.search_key
    assert key is not None
    return key


@pytest.fixture
def auth_middleware(settings: Any) -> None:
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, "django.contrib.auth.middleware.AuthenticationMiddleware"]


def _users(request: HttpRequest) -> QuerySet[User]:
    return User.objects.order_by("pk")


class _StyledUserField(forms.ModelChoiceField):
    def label_from_instance(self, obj: User) -> ChoiceLabel:  # type: ignore[override]
        return ChoiceLabel(obj.email, icon='<i class="icon icon-user"></i>')


class _UserSearchForm(FormworkForm):
    """Registers its search at import, as a project form does."""

    user = _StyledUserField(
        queryset=User.objects.all(),
        widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


class _ClearableUserForm(FormworkForm):
    """An optional field whose search offers a clear row when the widget asks for one."""

    people = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        empty_label="Not set",
        widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


def _group_members(request: HttpRequest, *, group: int) -> QuerySet[User]:
    return User.objects.filter(groups=group).order_by("pk")


class _GroupMembersForm(FormworkForm):
    """Builds one field per group in ``__init__`` from a template field's search."""

    members_template = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=SelectMultiple(search_fields=["email"], search_queryset=_group_members, search_decorator=None),
    )

    def __init__(
        self,
        *args: Any,
        groups: Sequence[Group],
        widget_class: type[Select | SelectMultiple],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        key = self.fields.pop("members_template").widget.search_key
        for group in groups:
            self.fields[f"group_{group.pk}"] = forms.ModelMultipleChoiceField(
                queryset=User.objects.filter(groups=group),
                widget=widget_class(search_key=key, search_params={"group": group.pk}),
            )


def test_search_fields_without_search_queryset_is_rejected() -> None:
    with pytest.raises(ImproperlyConfigured, match="search_queryset"):

        class _F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=Select(search_fields=["email"], search_decorator=None),
            )


@pytest.mark.parametrize("widget_class", [Select, SelectMultiple, ComboBox])
def test_search_queryset_without_search_decorator_is_rejected(widget_class: type[forms.Widget]) -> None:
    with pytest.raises(ImproperlyConfigured, match="search_decorator"):

        class _F(FormworkForm):
            user = forms.CharField(widget=widget_class(search_queryset=_users))


def _groups(request: HttpRequest) -> QuerySet[Group]:
    return Group.objects.order_by("name")


def _ranked_form() -> type[FormworkForm]:
    class _RankedGroupForm(FormworkForm):
        group = forms.ModelChoiceField(
            queryset=Group.objects.all(),
            widget=Select(search_fields=["name"], search_queryset=_groups, search_decorator=None, search_ranked=True),
        )

    return _RankedGroupForm


@pytest.mark.skipif(connection.vendor == "postgresql", reason="the ranked search runs on PostgreSQL")
def test_ranked_search_is_refused_on_other_databases() -> None:
    with pytest.raises(ImproperlyConfigured, match=f"needs PostgreSQL.*{connection.vendor}"):
        _ranked_form()


def test_ranked_search_needs_search_fields() -> None:
    with pytest.raises(ImproperlyConfigured, match="search_fields"):

        class _F(FormworkModelForm):
            class Meta:
                model = Group
                fields = ["name"]
                widgets = {"name": ComboBox(search_queryset=_groups, search_decorator=None, search_ranked=True)}


def _positional(request: HttpRequest, group: int) -> QuerySet[User]:
    return User.objects.none()


def _float_param(request: HttpRequest, *, group: float) -> QuerySet[User]:
    return User.objects.none()


def _reserved_param(request: HttpRequest, *, offset: int) -> QuerySet[User]:
    return User.objects.none()


@pytest.mark.parametrize("queryset", [_positional, _float_param, _reserved_param])
def test_queryset_params_must_be_keyword_only_int_or_str(queryset: Callable[..., Any]) -> None:
    with pytest.raises(ImproperlyConfigured, match="keyword-only int or str"):

        class _F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=Select(search_queryset=queryset, search_decorator=None),
            )


def test_search_queryset_must_be_callable() -> None:
    with pytest.raises(ImproperlyConfigured, match="must be a callable"):

        class _F(FormworkForm):
            user = forms.ModelChoiceField(
                queryset=User.objects.all(),
                widget=Select(search_queryset=User.objects.all(), search_decorator=None),
            )


class _PartialSearchForm(FormworkForm):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=SelectMultiple(search_queryset=partial(_group_members), search_decorator=None),
    )


def test_wrong_params_for_a_partial_search_are_rejected() -> None:
    with pytest.raises(ImproperlyConfigured, match="takes"):
        Select(search_key=_key(_PartialSearchForm, "members"), search_params={})


@pytest.mark.parametrize("routed", [True, False])
def test_system_check_reports_an_unrouted_search_endpoint(settings: Any, routed: bool) -> None:  # noqa: FBT001
    unrouted = ModuleType("urls_without_formwork")
    unrouted.urlpatterns = []  # type: ignore[attr-defined]
    settings.ROOT_URLCONF = "e2e.urls" if routed else unrouted

    ids = {error.id for error in run_checks(tags=[Tags.urls])}

    assert ("django_formwork.E001" in ids) is not routed


def test_postponed_annotations_declare_the_param_type(db: None) -> None:
    assert inspect.get_annotations(_group_members)["group"] == "int"
    crew = Group.objects.create(name="crew")
    members = _make_users(2)
    crew.user_set.add(*members)
    url = search_url(_key(_GroupMembersForm, "members_template"), {"group": crew.pk}, widget="select")

    response = Client().get(url)

    assert _rows(response) == [str(member.pk) for member in members]


@pytest.mark.parametrize("widget_class", [Select, ComboBox])
@pytest.mark.parametrize(
    ("registered", "params"),
    [
        (False, {"group": 1}),
        (True, {}),
        (True, {"team": 1}),
    ],
)
def test_search_key_is_checked_where_the_widget_is_built(
    widget_class: type[forms.Widget],
    registered: bool,  # noqa: FBT001
    params: dict[str, int],
) -> None:
    key = _key(_GroupMembersForm, "members_template") if registered else "not-a-key"

    with pytest.raises(ImproperlyConfigured):
        widget_class(search_key=key, search_params=params)


def _build_form() -> type[FormworkForm]:
    class _Rebuilt(FormworkForm):
        user = forms.ModelChoiceField(
            queryset=User.objects.all(),
            widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=None),
        )

    return _Rebuilt


def test_a_rebuilt_form_gets_the_same_key() -> None:
    assert _key(_build_form(), "user") == _key(_build_form(), "user")


def _city_form(search_queryset: Callable[..., Any]) -> type[forms.ModelForm]:
    widget = Select(search_fields=["name"], search_queryset=search_queryset, search_decorator=None)
    return modelform_factory(City, form=FormworkModelForm, fields=["region"], widgets={"region": widget})


def _north(request: HttpRequest) -> QuerySet[Region]:
    return Region.objects.filter(name="North")


def _south(request: HttpRequest) -> QuerySet[Region]:
    return Region.objects.filter(name="South")


@pytest.mark.django_db
def test_factory_built_forms_over_one_model_keep_their_own_search() -> None:
    north_form = _city_form(_north)
    _city_form(_south)
    north = Region.objects.create(name="North")
    Region.objects.create(name="South")

    response = Client().get(search_url(_key(north_form, "region"), {}, widget="select"))

    assert _rows(response) == [str(north.pk)]


def test_factory_form_closing_over_other_data_is_rejected() -> None:
    def build(name: str) -> type[forms.ModelForm]:
        return _city_form(lambda request: Region.objects.filter(name=name))

    build("North")
    with pytest.raises(ImproperlyConfigured, match="request"):
        build("South")


def _staff(request: HttpRequest) -> QuerySet[User]:
    return User.objects.filter(is_staff=True)


class _StaffForm(FormworkForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=Select(search_fields=["email"], search_queryset=_staff, search_decorator=None),
    )
    backup = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("form_cls", "name", "expected"),
    [
        (_UserSearchForm, "user", ["staff0", "user0"]),
        (_StaffForm, "user", ["staff0"]),
        (_StaffForm, "backup", ["staff0", "user0"]),
    ],
)
def test_each_form_field_serves_its_own_search(form_cls: type[forms.Form], name: str, expected: list[str]) -> None:
    User.objects.create(username="staff0", email="staff0@example.com", is_staff=True)
    _make_users(1)
    url = search_url(_key(form_cls, name), {}, widget="select")

    response = Client().get(url)

    usernames = User.objects.filter(pk__in=_rows(response)).values_list("username", flat=True)
    assert sorted(usernames) == expected


@pytest.mark.django_db
def test_endpoint_serves_the_request_scoped_queryset_not_the_field_one() -> None:
    def scoped(request: HttpRequest) -> QuerySet[User]:
        return User.objects.none()

    class _F(FormworkForm):
        user = forms.ModelChoiceField(
            queryset=User.objects.all(),
            widget=Select(search_fields=["email"], search_queryset=scoped, search_decorator=None),
        )

    _make_users(1)

    response = Client().get(search_url(_key(_F, "user"), {}, widget="select"))

    assert response.status_code == 200
    assert _rows(response) == []


def _starting_with_query(request: HttpRequest) -> QuerySet[User]:
    return User.objects.filter(username__startswith=request.GET.get("q", "")).order_by("pk")


class _OwnRankingForm(FormworkForm):
    """No ``search_fields``: the queryset reads ``q`` itself."""

    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=Select(search_queryset=_starting_with_query, search_decorator=None),
    )


@pytest.mark.django_db
def test_without_search_fields_the_queryset_alone_filters() -> None:
    ada = User.objects.create(username="ada", email="x@example.com")
    User.objects.create(username="bob", email="ada@example.com")
    url = search_url(_key(_OwnRankingForm, "user"), {}, widget="select")

    response = Client().get(f"{url}&q=ad")

    assert _rows(response) == [str(ada.pk)]


@pytest.mark.django_db
def test_unknown_key_redirects_an_anonymous_request_to_login() -> None:
    response = Client().get(reverse("formwork:search", kwargs={"key": "nope"}))

    assert response.status_code == 302
    assert response.headers["location"].startswith("/accounts/login/")


@pytest.mark.django_db
@pytest.mark.usefixtures("auth_middleware")
def test_unknown_key_is_not_found_for_a_signed_in_user() -> None:
    client = Client()
    client.force_login(User.objects.create(username="ada"))

    response = client.get(reverse("formwork:search", kwargs={"key": "nope"}))

    assert response.status_code == 404


def test_unknown_key_is_not_found_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    installed = views.apps.is_installed
    monkeypatch.setattr(views.apps, "is_installed", lambda name: name != "django.contrib.auth" and installed(name))

    response = Client().get(reverse("formwork:search", kwargs={"key": "nope"}))

    assert response.status_code == 404


class _MembersOnlyForm(FormworkForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=login_required),
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("auth_middleware")
@pytest.mark.parametrize(("signed_in", "status"), [(False, 302), (True, 200)])
def test_search_decorator_guards_the_endpoint(signed_in: bool, status: int) -> None:  # noqa: FBT001
    client = Client()
    if signed_in:
        client.force_login(User.objects.create(username="ada"))

    response = client.get(search_url(_key(_MembersOnlyForm, "user"), {}, widget="select"))

    assert response.status_code == status


@pytest.fixture
def user_search_url() -> str:
    return search_url(_key(_UserSearchForm, "user"), {}, widget="select")


@pytest.mark.django_db
def test_row_carries_the_choice_icon(user_search_url: str) -> None:
    User.objects.create(username="ada", email="ada@example.com")

    response = Client().get(f"{user_search_url}&q=ada")

    row = BeautifulSoup(response.content.decode(), "html.parser").select_one("[data-value]")
    assert row is not None
    assert "icon-user" in str(row.get("data-icon"))


@pytest.mark.django_db
def test_no_match_swaps_in_the_no_results_row(user_search_url: str) -> None:
    User.objects.create(username="ada", email="ada@example.com")

    response = Client().get(f"{user_search_url}&q=nobody")

    soup = BeautifulSoup(response.content.decode(), "html.parser")
    assert soup.select_one("[data-value]") is None
    assert soup.select_one('[role="status"]') is not None


@pytest.mark.django_db
def test_capped_page_loads_the_next_one_until_none_is_left() -> None:
    _make_users(41)
    url: str | None = search_url(_key(_ClearableUserForm, "people"), {}, widget="select", allow_clear=True) + "&q=%40"

    pages = []
    while url:
        soup = BeautifulSoup(Client().get(url).content.decode(), "html.parser")
        pages.append([str(el["data-value"]) for el in soup.select("[data-value]")])
        hint = soup.select_one('[role="status"]')
        assert (hint is not None) is (len(pages) < 3)
        more = hint.select_one("button[hx-get]") if hint else None
        url = str(more["hx-get"]) if more else None

    assert [len(page) for page in pages] == [21, 20, 1]
    assert pages[0][0] == ""
    assert len({value for page in pages for value in page}) == 42


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("widget_class", "row"),
    [
        (Select, "button[data-value]"),
        (SelectMultiple, "input[type=checkbox][data-value]"),
    ],
)
def test_search_serves_the_rows_of_the_bound_param(widget_class: type[Select | SelectMultiple], row: str) -> None:
    crew = Group.objects.create(name="crew")
    member = User.objects.create(username="ada", email="ada@example.com")
    crew.user_set.add(member, *_make_users(20))
    outsider = User.objects.create(username="ada2", email="ada@other.example.com")
    outsider.groups.add(Group.objects.create(name="other"))
    form = _GroupMembersForm(groups=[crew], widget_class=widget_class)

    rendered = BeautifulSoup(str(form[f"group_{crew.pk}"]), "html.parser")
    search = rendered.select_one("[hx-get]")
    assert search is not None
    response = Client().get(f"{search['hx-get']}&q=ada")

    assert _rows(response, row) == [str(member.pk)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("group", "suffix"),
    [
        ("crew", ""),
        ("1", "&exclude=crew"),
        ("1", "&offset=-20"),
        ("1", "&offset=next"),
        ("1", "&widget=table"),
    ],
)
def test_malformed_param_is_not_found(group: str, suffix: str) -> None:
    url = search_url(_key(_GroupMembersForm, "members_template"), {"group": group}, widget="select")

    response = Client().get(f"{url}{suffix}")

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("allow_clear", [True, False])
def test_clear_row_follows_the_allow_clear_flag(allow_clear: bool) -> None:  # noqa: FBT001
    User.objects.create(username="ada", email="ada@example.com")
    url = search_url(_key(_ClearableUserForm, "people"), {}, widget="select", allow_clear=allow_clear)

    response = Client().get(url)

    assert (_rows(response)[0] == "") is allow_clear
    assert ("Not set" in response.content.decode()) is allow_clear


@pytest.mark.django_db
def test_a_required_field_never_offers_a_clear_row() -> None:
    User.objects.create(username="ada", email="ada@example.com")
    url = search_url(_key(_UserSearchForm, "user"), {}, widget="select", allow_clear=True)

    response = Client().get(url)

    assert "" not in _rows(response)


def _labelled(user: User) -> ChoiceLabel:
    return ChoiceLabel(user.username.title(), icon="*")


class _ComboForm(FormworkForm):
    """A free-text field: the widget names the label of each suggestion row."""

    name = forms.CharField(
        widget=ComboBox(
            search_fields=["username"],
            search_queryset=_users,
            search_decorator=None,
            label_from_instance=_labelled,
        ),
    )


@pytest.mark.django_db
def test_combo_box_rows_take_the_widget_label() -> None:
    User.objects.create(username="ada")
    url = search_url(_key(_ComboForm, "name"), {}, widget="combo_box")

    response = Client().get(url)

    soup = BeautifulSoup(response.content.decode(), "html.parser")
    assert [li["data-label"] for li in soup.select("li[role=option]")] == ["Ada"]


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="the ranked search needs PostgreSQL")
@pytest.mark.parametrize(
    ("names", "query", "best"),
    [
        (["10/L", "104/L", "XL", "L"], "l", "L"),
        (["Baumwollmischung", "Bio-Baumwolle"], "baumwole", "Bio-Baumwolle"),
        (["Black", "Dunkelblau"], "blau", "Dunkelblau"),
        (["Rote", "Bordeaux Rot"], "rot", "Bordeaux Rot"),
    ],
)
def test_ranked_search_puts_the_best_match_first(names: list[str], query: str, best: str) -> None:
    Group.objects.bulk_create(Group(name=name) for name in names)
    url = search_url(_key(_ranked_form(), "group"), {}, widget="select")

    response = Client().get(f"{url}&q={query}")

    row = BeautifulSoup(response.content.decode(), "html.parser").select_one("[data-value]")
    assert row is not None
    assert row["data-label"] == best
