"""Tests for editable table rendering: ``form.as_row`` / ``formset.as_rows`` and row saving."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory
from e2e.models import UniqueCode

from django_formwork import (
    DisplayField,
    FormworkForm,
    FormworkModelForm,
    FormworkRowSaveMixin,
    formwork_modelformset_factory,
)
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

    soup = BeautifulSoup(formset.as_rows(save_url="/save/"), "html.parser")

    assert "Code" in soup.thead.get_text()
    assert len(soup.select("table > tbody")) == 2
    assert "alpha" in soup.get_text() and "beta" in soup.get_text()


def test_disabled_multiple_choice_cell_shows_the_chosen_labels():
    class TagsForm(FormworkForm):
        tags = forms.MultipleChoiceField(choices=[("a", "Apples"), ("b", "Bananas")], disabled=True)

    html = TagsForm(initial={"tags": ["a", "b"]}).as_row()

    assert "Apples, Bananas" in html


def test_a_display_column_shows_the_value_of_its_source_as_text():
    UniqueCode.objects.create(code="A", label="alpha")
    form = type("CodeForm", (CodeRowForm,), {"summary": DisplayField(source=lambda obj: [obj.code, obj.label])})
    formset = formwork_modelformset_factory(UniqueCode, form=form, extra=0)(queryset=UniqueCode.objects.all())

    cell = BeautifulSoup(formset.as_rows(), "html.parser").find("td", attrs={"data-field": "summary"})

    assert cell.get_text(strip=True) == "A, alpha"
    assert cell.find("input") is None


def test_an_app_listed_first_overrides_the_row_template(settings, tmp_path, monkeypatch):
    app = tmp_path / "row_override"
    override = app / "jinja2" / "formwork" / "tables" / "row.html"
    override.parent.mkdir(parents=True)
    (app / "__init__.py").write_text("")
    override.write_text("<tbody>project row</tbody>")
    monkeypatch.syspath_prepend(tmp_path)
    settings.INSTALLED_APPS = ["row_override", *settings.INSTALLED_APPS]

    html = CodeRowForm(instance=UniqueCode.objects.create(code="A")).as_row()

    assert "project row" in html


def test_a_django_template_renders_the_rows_of_a_form_that_names_one(settings, tmp_path):
    (tmp_path / "rows").mkdir()
    (tmp_path / "rows" / "code.html").write_text("<tbody>{{ row.form.code.value }} in a project row</tbody>")
    settings.TEMPLATES = [{**settings.TEMPLATES[0], "DIRS": [tmp_path]}]

    class ProjectRowForm(CodeRowForm):
        template_name_row = "rows/code.html"

    html = ProjectRowForm(instance=UniqueCode.objects.create(code="A")).as_row()

    assert "A in a project row" in html


def test_row_save_updates_only_editable_fields():
    obj = UniqueCode.objects.create(code="A", label="alpha")

    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm
        queryset = UniqueCode.objects.all()

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
    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm
        queryset = UniqueCode.objects.all()

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
        queryset = UniqueCode.objects.all()

    request = RequestFactory().post(
        "/save/",
        {"form-0-code": "Z", "form-0-id": str(obj.pk), PREFIX_INPUT_NAME: "form-0"},
    )
    response = SaveView().post(request)

    assert b'name="form-0-id"' in response.content
    assert f'value="{obj.pk}"'.encode() in response.content


def test_row_save_cannot_reach_a_row_outside_the_queryset():
    obj = UniqueCode.objects.create(code="A", label="alpha")

    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm
        queryset = UniqueCode.objects.exclude(pk=obj.pk)

    request = RequestFactory().post("/save/", {"code": "Z", "id": str(obj.pk), PREFIX_INPUT_NAME: ""})
    with pytest.raises(Http404):
        SaveView().post(request)

    obj.refresh_from_db()
    assert obj.code == "A"


def test_row_save_without_a_queryset_is_rejected():
    obj = UniqueCode.objects.create(code="A", label="alpha")

    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm

    request = RequestFactory().post("/save/", {"code": "Z", "id": str(obj.pk), PREFIX_INPUT_NAME: ""})
    with pytest.raises(ImproperlyConfigured, match="queryset"):
        SaveView().post(request)


class AttachmentRowForm(CodeRowForm):
    attachment = forms.FileField()


def test_row_save_passes_uploaded_files_to_the_form():
    obj = UniqueCode.objects.create(code="A", label="alpha")

    class SaveView(FormworkRowSaveMixin):
        form_class = AttachmentRowForm
        queryset = UniqueCode.objects.all()

    upload = SimpleUploadedFile("note.txt", b"hi")
    request = RequestFactory().post(
        "/save/",
        {"code": "Z", "id": str(obj.pk), PREFIX_INPUT_NAME: "", "attachment": upload},
    )
    SaveView().post(request)

    obj.refresh_from_db()
    assert obj.code == "Z"


class HelpRowForm(FormworkModelForm):
    class Meta:
        model = UniqueCode
        fields = ["code", "label"]
        help_texts = {"label": "Shown in lists"}


CodeFormSet = formwork_modelformset_factory(UniqueCode, form=HelpRowForm, extra=0, can_delete=True)


def posted_inputs(html):
    soup = BeautifulSoup(html, "html.parser")
    inputs = [field for field in soup.find_all("input") if not field.find_parent("template")]
    return {
        field["name"]: field.get("value", "")
        for field in inputs
        if field.get("type") != "checkbox" or field.has_attr("checked")
    }


def test_as_rows_posts_back_as_a_valid_formset():
    UniqueCode.objects.create(code="A", label="alpha")
    queryset = UniqueCode.objects.all()

    formset = CodeFormSet(posted_inputs(CodeFormSet(queryset=queryset).as_rows()), queryset=queryset)

    assert formset.is_valid(), formset.errors


@pytest.mark.parametrize(
    ("attrs", "save_url", "can_add"),
    [({}, "", True), ({}, "/save/", False), ({"can_add": False}, "", False), ({"edit_only": True}, "", False)],
)
def test_add_another_needs_a_formset_that_grows_on_one_save(attrs, save_url, can_add):
    formset = type("Rows", (CodeFormSet,), attrs)(queryset=UniqueCode.objects.none())

    soup = BeautifulSoup(formset.as_rows(save_url), "html.parser")

    template = soup.find("template")
    assert (
        template is not None and template.find("input", attrs={"name": "form-__prefix__-code"}) is not None
    ) is can_add
    assert ("Add another" in soup.get_text()) is can_add


def test_a_saved_row_has_a_delete_toggle_and_a_new_row_a_remove_button():
    UniqueCode.objects.create(code="A")
    formset = formwork_modelformset_factory(UniqueCode, form=HelpRowForm, extra=1, can_delete=True)(
        queryset=UniqueCode.objects.all()
    )

    soup = BeautifulSoup(formset.as_rows(), "html.parser")

    saved, new = soup.select("table > tbody")
    assert saved.find("input", attrs={"name": "form-0-DELETE", "type": "checkbox"}) is not None
    assert new.find("input", attrs={"name": "form-1-DELETE"}) is None
    assert new.find("button", attrs={"aria-label": "Remove"}) is not None
    assert "Delete" not in soup.thead.get_text()


def test_a_required_column_has_the_asterisk_and_help_text_shows_in_the_header():
    formset = CodeFormSet(queryset=UniqueCode.objects.none())

    code, label = BeautifulSoup(formset.as_rows(), "html.parser").thead.find_all("th")[:2]

    assert code.find(string="*") is not None
    assert label.find(string="*") is None
    assert label.find(attrs={"data-tip": "Shown in lists"}) is not None


def test_an_invalid_row_keeps_its_changed_marks_and_describes_the_error():
    UniqueCode.objects.create(code="A", label="alpha")
    queryset = UniqueCode.objects.all()
    data = {**posted_inputs(CodeFormSet(queryset=queryset).as_rows()), "form-0-code": ""}
    formset = CodeFormSet(data, queryset=queryset)
    assert not formset.is_valid()

    soup = BeautifulSoup(formset.as_rows(), "html.parser")

    code = soup.find("td", attrs={"data-field": "code"})
    label = soup.find("td", attrs={"data-field": "label"})
    assert code.has_attr("data-formwork-changed")
    assert not label.has_attr("data-formwork-changed")
    error = code.find(attrs={"role": "tooltip"})
    assert error["id"] in code.find("input", attrs={"name": "form-0-code"})["aria-describedby"].split()
    assert "required" in error.get_text()


@pytest.mark.parametrize(("code", "marked"), [("Z", False), ("", True)])
def test_row_save_drops_the_changed_marks_only_when_the_row_saved(code, marked):
    obj = UniqueCode.objects.create(code="A", label="alpha")

    class SaveView(FormworkRowSaveMixin):
        form_class = CodeRowForm
        queryset = UniqueCode.objects.all()

    response = SaveView().post(
        RequestFactory().post("/save/", {"code": code, "id": str(obj.pk), PREFIX_INPUT_NAME: ""})
    )

    assert (b"data-formwork-changed" in response.content) is marked


def test_formset_media_loads_the_table_script():
    formset = CodeFormSet(queryset=UniqueCode.objects.none())

    assert "formwork/tables.js" in str(formset.media)
