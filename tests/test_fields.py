"""Tests for ChoiceLabel, FormworkModelChoiceField, and FormworkModelMultipleChoiceField."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, User

from django_formwork.fields import (
    ChoiceLabel,
    FormworkModelChoiceField,
    FormworkModelMultipleChoiceField,
)


class TestChoiceLabel:
    def test_str_returns_label(self):
        label = ChoiceLabel("New York", icon="building", description="East Coast")
        assert str(label) == "New York"

    def test_icon_attribute(self):
        label = ChoiceLabel("New York", icon="building")
        assert label.icon == "building"

    def test_description_attribute(self):
        label = ChoiceLabel("New York", description="East Coast")
        assert label.description == "East Coast"

    def test_defaults_empty_strings(self):
        label = ChoiceLabel("New York")
        assert label.icon == ""
        assert label.description == ""

    def test_equality_by_str(self):
        """ChoiceLabel compares equal to its string representation."""
        label = ChoiceLabel("New York", icon="building")
        assert label == "New York"

    def test_repr(self):
        label = ChoiceLabel("NYC", icon="building", description="East Coast")
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

    def test_choices_yield_formwork_choice_label(self):
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert isinstance(label, ChoiceLabel)

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
        """The empty label (first choice) is a regular string, not ChoiceLabel."""
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        val, label = choices[0]
        assert val == ""
        assert not isinstance(label, ChoiceLabel)

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

    def test_from_field_preserves_limit_choices_to_and_initial(self):
        """from_field carries over limit_choices_to and initial, not just the basics."""
        from django.forms import ModelChoiceField

        original = ModelChoiceField(
            queryset=User.objects.all(),
            limit_choices_to={"is_active": True},
            initial=1,
        )
        converted = FormworkModelChoiceField.from_field(original)
        assert converted.get_limit_choices_to() == {"is_active": True}
        assert converted.initial == 1


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
        assert isinstance(label, ChoiceLabel)

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


def test_from_field_preserves_empty_label_for_blank_radio_select():
    """from_field keeps the empty choice of a blank=True RadioSelect field."""
    # Regression: blank was read off the source field (always False there),
    # so the RadioSelect branch forced empty_label to None.
    from django.forms import ModelChoiceField, RadioSelect

    original = ModelChoiceField(queryset=User.objects.all(), widget=RadioSelect, blank=True)
    converted = FormworkModelChoiceField.from_field(original)
    assert converted.empty_label is not None


def test_meta_widgets_radio_select_keeps_empty_choice_for_blank_fk():
    """A blank=True FK swapped by the metaclass keeps its empty choice under RadioSelect."""
    from django.forms import RadioSelect
    from e2e.models import DirtyTrackedData

    from django_formwork.forms import FormworkModelForm

    class _Form(FormworkModelForm):
        class Meta:
            model = DirtyTrackedData
            fields = ["name", "email", "region"]
            widgets = {"region": RadioSelect}

    field = _Form.base_fields["region"]
    assert isinstance(field, FormworkModelChoiceField)
    assert field.empty_label is not None


@pytest.mark.django_db
class TestFormworkModelFormMetaclass:
    def test_auto_swaps_model_choice_field(self):
        from django_formwork.forms import FormworkModelForm

        class F(FormworkModelForm):
            class Meta:
                model = User
                fields = ["groups"]

        field = F.base_fields["groups"]
        assert isinstance(field, FormworkModelMultipleChoiceField)

    def test_preserves_explicit_formwork_field(self):
        from django_formwork.forms import FormworkModelForm

        class F(FormworkModelForm):
            groups = FormworkModelMultipleChoiceField(
                queryset=Group.objects.all(),
                icon_from_instance=lambda g: f"icon-{g.name}",
            )

            class Meta:
                model = User
                fields = ["groups"]

        field = F.base_fields["groups"]
        assert isinstance(field, FormworkModelMultipleChoiceField)
        Group.objects.create(name="editors")
        choices = list(field.choices)
        _, label = choices[0]
        assert label.icon == "icon-editors"

    def test_preserves_other_subclass(self):
        """A custom ModelChoiceField subclass (not ours) is left untouched."""
        from django.forms import ModelMultipleChoiceField

        from django_formwork.forms import FormworkModelForm

        class CustomField(ModelMultipleChoiceField):
            pass

        class F(FormworkModelForm):
            groups = CustomField(queryset=Group.objects.all())

            class Meta:
                model = User
                fields = ["groups"]

        field = F.base_fields["groups"]
        assert type(field) is CustomField

    def test_preserves_widget(self):
        """The original widget from Meta.widgets is preserved after the swap."""
        from django_formwork.forms import FormworkModelForm
        from django_formwork.widgets import MultiSelect

        class F(FormworkModelForm):
            class Meta:
                model = User
                fields = ["groups"]
                widgets = {"groups": MultiSelect()}

        field = F.base_fields["groups"]
        assert isinstance(field, FormworkModelMultipleChoiceField)
        assert isinstance(field.widget, MultiSelect)

    def test_non_model_fields_untouched(self):
        """Regular CharField, etc. are not affected by the metaclass."""
        from django import forms

        from django_formwork.forms import FormworkModelForm

        class F(FormworkModelForm):
            extra = forms.CharField()

            class Meta:
                model = User
                fields = ["groups"]

        assert type(F.base_fields["extra"]) is forms.CharField
