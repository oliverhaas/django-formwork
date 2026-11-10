"""Tests for the User and Group admins of django_formwork.admin."""

import json
from urllib.parse import urljoin

import pytest
from bs4 import BeautifulSoup
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def admin_urls(settings):
    settings.ROOT_URLCONF = "admin_app.urls"


@pytest.fixture
def ada(django_user_model):
    return django_user_model.objects.create_user("ada", password="old-pw-12345")


def url(model, view, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{view}", args=args)


def password_url(user):
    return reverse("admin:auth_user_password_change", args=(user.pk,))


def test_user_change_form_links_to_the_password_page(admin_client, ada):
    soup = BeautifulSoup(admin_client.get(url(User, "change", ada.pk)).content, "html.parser")

    link = soup.select_one('[data-field="password"] a[href]')
    assert urljoin(url(User, "change", ada.pk), link["href"]) == password_url(ada)


def test_add_user_opens_the_new_users_change_page(admin_client):
    response = admin_client.post(
        url(User, "add"),
        {"username": "grace", "usable_password": "true", "password1": "pw-Kd83jx!q", "password2": "pw-Kd83jx!q"},
    )

    grace = User.objects.get(username="grace")
    assert response.status_code == 302
    assert response["Location"] == url(User, "change", grace.pk)
    assert grace.check_password("pw-Kd83jx!q")


def test_add_user_in_a_dialog_answers_with_the_new_user(admin_client):
    response = admin_client.post(url(User, "add"), {"username": "grace", "usable_password": "false", "_popup": "1"})

    soup = BeautifulSoup(response.content, "html.parser")
    data = json.loads(soup.find(id="formwork-admin-popup-response")["data-popup-response"])
    assert data == {"value": str(User.objects.get(username="grace").pk), "obj": "grace"}


def test_password_page_in_a_dialog_posts_back_that_it_is_one(admin_client, ada):
    soup = BeautifulSoup(admin_client.get(password_url(ada), {"_popup": "1"}).content, "html.parser")

    assert soup.find("aside") is None
    assert soup.find("input", {"name": "_popup"})["value"] == "1"


def test_add_user_with_password_authentication_disabled_sets_an_unusable_password(admin_client):
    soup = BeautifulSoup(admin_client.get(url(User, "add")).content, "html.parser")
    assert [radio["value"] for radio in soup.select('input[name="usable_password"]')] == ["true", "false"]

    admin_client.post(url(User, "add"), {"username": "grace", "usable_password": "false"})

    assert not User.objects.get(username="grace").has_usable_password()


def test_add_user_needs_the_change_permission(client, django_user_model):
    staff = django_user_model.objects.create_user("staff", password="pw-12345", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="add_user"))
    client.force_login(staff)

    assert client.get(url(User, "add")).status_code == 403


def test_password_page_sets_the_password_and_logs_the_change(admin_client, ada):
    response = admin_client.post(
        password_url(ada), {"usable_password": "true", "password1": "new-Pw-7781", "password2": "new-Pw-7781"}
    )

    ada.refresh_from_db()
    assert response["Location"] == url(User, "change", ada.pk)
    assert ada.check_password("new-Pw-7781")
    assert LogEntry.objects.filter(object_id=str(ada.pk), action_flag=CHANGE).exists()


@pytest.mark.parametrize(("button", "usable"), [("set-password", True), ("unset-password", False)])
def test_password_page_disables_password_authentication_only_from_its_button(admin_client, ada, button, usable):
    admin_client.post(password_url(ada), {"usable_password": "false", button: ""})

    ada.refresh_from_db()
    assert ada.has_usable_password() is usable


def test_password_page_needs_the_change_permission(client, django_user_model, ada):
    staff = django_user_model.objects.create_user("staff", password="pw-12345", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_user"))
    client.force_login(staff)

    assert client.post(password_url(ada), {"password1": "x", "password2": "x"}).status_code == 403


def test_group_permissions_are_grouped_by_model(admin_client):
    soup = BeautifulSoup(admin_client.get(url(Group, "add")).content, "html.parser")

    title = soup.find("li", class_="menu-title", string="Authentication and Authorization | user")
    assert title.find_next_sibling("li")["data-label"] == "Can add user"
