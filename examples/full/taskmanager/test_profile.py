"""Tests for the persisted Profile and the settings page."""

from __future__ import annotations

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from taskmanager.models import Profile


def _form_data(**overrides):
    data = {
        "full_name": "Mira Chen",
        "email": "mira@example.com",
        "phone_0": "+49",
        "phone_1": "171 1234567",
        "country": "de",
        "favourite_food": "Ramen",
        "satisfaction": "4",
        "new_password": "",
        "two_factor_code": "",
    }
    data.update(overrides)
    return data


def test_load_creates_the_singleton_once(db):
    first = Profile.load()
    second = Profile.load()
    assert first.pk == second.pk == 1
    assert Profile.objects.count() == 1


def test_save_pins_everything_to_one_row(db):
    Profile.load()
    Profile(full_name="Someone Else", email="someone@example.com").save()
    assert Profile.objects.count() == 1
    assert Profile.load().full_name == "Someone Else"


def test_clean_strips_the_name(db):
    profile = Profile.load()
    profile.full_name = "  Devon Vega  "
    profile.full_clean()
    assert profile.full_name == "Devon Vega"


def test_phone_must_be_dial_code_plus_number(db):
    profile = Profile.load()
    profile.phone = "five five five"
    with pytest.raises(ValidationError) as exc_info:
        profile.full_clean()
    assert "phone" in exc_info.value.error_dict


def test_save_rejects_invalid_data(db):
    profile = Profile.load()
    profile.satisfaction = 6
    with pytest.raises(ValidationError):
        profile.save()


def test_settings_page_prefills_from_the_profile(client, db):
    Profile.load()
    response = client.get(reverse("settings"))
    assert response.status_code == 200
    assert b"Devon Vega" in response.content


def test_settings_post_persists_the_profile(client, db):
    response = client.post(reverse("settings"), _form_data())
    assert response.status_code == 302
    profile = Profile.load()
    assert profile.full_name == "Mira Chen"
    assert profile.email == "mira@example.com"
    assert profile.phone == "+49 171 1234567"
    assert profile.country == Profile.Country.DE
    assert profile.favourite_food == "Ramen"
    assert profile.satisfaction == 4


def test_settings_post_with_invalid_phone_shows_error_and_saves_nothing(client, db):
    response = client.post(reverse("settings"), _form_data(phone_1="not a number"))
    assert response.status_code == 200
    assert "phone" in response.context["form"].errors
    assert Profile.load().full_name == "Devon Vega"


def test_settings_post_stores_the_avatar(client, db, settings, tmp_path):
    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format="PNG")
    avatar = SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png")

    response = client.post(reverse("settings"), {**_form_data(), "avatar": avatar})

    assert response.status_code == 302
    assert Profile.load().avatar.name.startswith("avatars/")


def test_password_and_otp_are_accepted_but_never_stored(client, db):
    response = client.post(
        reverse("settings"),
        _form_data(new_password="a-long-passphrase", two_factor_code="123456"),
    )
    assert response.status_code == 302
    field_names = {field.name for field in Profile._meta.get_fields()}
    assert "new_password" not in field_names
    assert "two_factor_code" not in field_names
