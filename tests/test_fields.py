"""Tests for FormworkChoiceLabel, FormworkModelChoiceField, and FormworkModelMultipleChoiceField."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, User

from django_formwork.fields import (
    FormworkChoiceLabel,
    FormworkModelChoiceField,
    FormworkModelMultipleChoiceField,
)


class TestFormworkChoiceLabel:
    def test_str_returns_label(self):
        label = FormworkChoiceLabel("New York", icon="building", description="East Coast")
        assert str(label) == "New York"

    def test_icon_attribute(self):
        label = FormworkChoiceLabel("New York", icon="building")
        assert label.icon == "building"

    def test_description_attribute(self):
        label = FormworkChoiceLabel("New York", description="East Coast")
        assert label.description == "East Coast"

    def test_defaults_empty_strings(self):
        label = FormworkChoiceLabel("New York")
        assert label.icon == ""
        assert label.description == ""

    def test_equality_by_str(self):
        """FormworkChoiceLabel compares equal to its string representation."""
        label = FormworkChoiceLabel("New York", icon="building")
        assert label == "New York"

    def test_repr(self):
        label = FormworkChoiceLabel("NYC", icon="building", description="East Coast")
        assert "NYC" in repr(label)


@pytest.mark.django_db
class TestFormworkModelChoiceField:
    @pytest.fixture(autouse=True)
    def _create_users(self):
        User.objects.create_user("alice", "alice@example.com", first_name="Alice")
        User.objects.create_user("bob", "bob@example.com", first_name="Bob")

    def test_default_label_from_instance_is_str(self):
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert str(label) == str(User.objects.first())

    def test_label_from_instance_kwarg(self):
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            label_from_instance=lambda u: u.first_name,
        )
        choices = list(field.choices)
        labels = [str(lbl) for _, lbl in choices if str(lbl)]
        assert "Alice" in labels
        assert "Bob" in labels

    def test_label_from_instance_method_override(self):
        class MyField(FormworkModelChoiceField):
            def label_from_instance(self, obj):
                return f"User: {obj.username}"

        field = MyField(queryset=User.objects.all())
        choices = list(field.choices)
        labels = [str(lbl) for _, lbl in choices if str(lbl)]
        assert "User: alice" in labels

    def test_kwarg_overrides_method(self):
        """Kwarg takes precedence over the default method."""
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            label_from_instance=lambda u: u.first_name,
        )
        choices = list(field.choices)
        labels = [str(lbl) for _, lbl in choices if str(lbl)]
        assert "Alice" in labels

    def test_choices_yield_formwork_choice_label(self):
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert isinstance(label, FormworkChoiceLabel)

    def test_icon_from_instance_default_empty(self):
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert label.icon == ""

    def test_icon_from_instance_kwarg(self):
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            icon_from_instance=lambda u: f"avatar-{u.username}",
        )
        choices = list(field.choices)
        _, label = choices[1]
        assert label.icon.startswith("avatar-")

    def test_description_from_instance_kwarg(self):
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            description_from_instance=lambda u: u.email,
        )
        choices = list(field.choices)
        _, label = choices[1]
        assert "@example.com" in label.description

    def test_icon_from_instance_method_override(self):
        class MyField(FormworkModelChoiceField):
            def icon_from_instance(self, obj):
                return f"icon-{obj.pk}"

        field = MyField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert label.icon.startswith("icon-")

    def test_description_from_instance_method_override(self):
        class MyField(FormworkModelChoiceField):
            def description_from_instance(self, obj):
                return obj.email

        field = MyField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert "@example.com" in label.description

    def test_empty_label_is_plain_string(self):
        """The empty label (first choice) is a regular string, not FormworkChoiceLabel."""
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        val, label = choices[0]
        assert val == ""
        assert not isinstance(label, FormworkChoiceLabel)

    def test_from_field_copies_standard_field(self):
        """from_field creates a FormworkModelChoiceField from a standard ModelChoiceField."""
        from django.forms import ModelChoiceField

        original = ModelChoiceField(queryset=User.objects.all(), required=False, empty_label="Pick one")
        converted = FormworkModelChoiceField.from_field(original)
        assert isinstance(converted, FormworkModelChoiceField)
        assert converted.queryset.model is User
        assert converted.required is False
        assert converted.empty_label == "Pick one"
        assert converted.widget.__class__ == original.widget.__class__


@pytest.mark.django_db
class TestFormworkModelMultipleChoiceField:
    @pytest.fixture(autouse=True)
    def _create_users(self):
        User.objects.create_user("alice", "alice@example.com", first_name="Alice")
        User.objects.create_user("bob", "bob@example.com", first_name="Bob")

    def test_choices_yield_formwork_choice_label(self):
        field = FormworkModelMultipleChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[0]
        assert isinstance(label, FormworkChoiceLabel)

    def test_icon_from_instance_kwarg(self):
        field = FormworkModelMultipleChoiceField(
            queryset=User.objects.all(),
            icon_from_instance=lambda u: f"avatar-{u.username}",
        )
        choices = list(field.choices)
        _, label = choices[0]
        assert label.icon.startswith("avatar-")

    def test_no_empty_label(self):
        """Multiple choice fields have no empty label."""
        field = FormworkModelMultipleChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        assert len(choices) == 2  # No empty option

    def test_from_field_copies_standard_field(self):
        from django.forms import ModelMultipleChoiceField

        original = ModelMultipleChoiceField(queryset=User.objects.all(), required=False)
        converted = FormworkModelMultipleChoiceField.from_field(original)
        assert isinstance(converted, FormworkModelMultipleChoiceField)
        assert converted.queryset.model is User
        assert converted.required is False
