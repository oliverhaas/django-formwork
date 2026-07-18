"""Tests for editable table rendering: ``form.as_row`` / ``formset.as_rows`` and row saving."""

from __future__ import annotations

import pytest
from django.test import RequestFactory
from e2e.models import UniqueCode

from django_formwork import FormworkModelForm, FormworkRowSaveMixin, formwork_modelformset_factory
from django_formwork.tables import PREFIX_INPUT_NAME

pytestmark = pytest.mark.django_db


class CodeRowForm(FormworkModelForm):
    class Meta:
        model = UniqueCode
        fields = ["code", "label"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["label"].disabled = True


def test_as_row_renders_tbody_with_autosave_wiring():
    obj = UniqueCode.objects.create(code="A", label="alpha")
    html = CodeRowForm(instance=obj).as_row(save_url="/save/")

    assert html.startswith("<tbody")
    assert 'hx-post="/save/"' in html
    assert 'hx-swap="outerMorph"' in html
    assert f'name="{PREFIX_INPUT_NAME}"' in html
    assert 'name="code"' in html
    assert 'name="label"' not in html
    assert "alpha" in html


def test_as_row_without_save_url_is_static():
    obj = UniqueCode.objects.create(code="A", label="alpha")
    html = CodeRowForm(instance=obj).as_row()
    assert "hx-post" not in html
    assert f'name="{PREFIX_INPUT_NAME}"' not in html


def test_as_rows_renders_table_with_header_and_one_tbody_per_row():
    UniqueCode.objects.create(code="A", label="alpha")
    UniqueCode.objects.create(code="B", label="beta")
    formset_cls = formwork_modelformset_factory(UniqueCode, form=CodeRowForm, extra=0)
    formset = formset_cls(queryset=UniqueCode.objects.order_by("code"))

    html = formset.as_rows(save_url="/save/")

    assert html.count("<thead>") == 1
    assert "<th>Code</th>" in html
    assert html.count("<tbody") == 2
    assert "alpha" in html and "beta" in html


def test_row_save_updates_only_editable_fields():
    obj = UniqueCode.objects.create(code="A", label="alpha")

    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm

    request = RequestFactory().post(
        "/save/",
        {"code": "Z", "label": "IGNORED", "id": str(obj.pk), PREFIX_INPUT_NAME: ""},
    )
    response = SaveView().post(request)

    obj.refresh_from_db()
    assert obj.code == "Z"
    assert obj.label == "alpha"
    assert b"<tbody" in response.content
    assert b"Z" in response.content


def test_row_save_malformed_pk_raises_404_not_500():
    from django.http import Http404

    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm

    request = RequestFactory().post(
        "/save/",
        {"code": "Z", "id": "not-a-number", PREFIX_INPUT_NAME: ""},
    )
    with pytest.raises(Http404):
        SaveView().post(request)


def test_row_save_rerenders_pk_so_the_next_edit_finds_it():
    # A prefixed (formset) row saved once must re-render its pk, or the next autosave 404s / KeyErrors.
    obj = UniqueCode.objects.create(code="A", label="alpha")

    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm

    request = RequestFactory().post(
        "/save/",
        {"form-0-code": "Z", "form-0-id": str(obj.pk), PREFIX_INPUT_NAME: "form-0"},
    )
    response = SaveView().post(request)

    assert b'name="form-0-id"' in response.content
    assert f'value="{obj.pk}"'.encode() in response.content
