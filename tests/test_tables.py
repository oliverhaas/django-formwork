"""Tests for editable table rendering: ``form.as_row`` / ``formset.as_rows`` and row saving."""

from __future__ import annotations

import datetime as dt
from urllib.parse import parse_qs, urlsplit

import jinja2
import pytest
from admin_app.models import Category, Item, Tag
from bs4 import BeautifulSoup
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.http import Http404
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils.datastructures import MultiValueDict
from django.utils.html import format_html
from e2e.models import City, Region, UniqueCode

from django_formwork import (
    DateRange,
    DateRangeField,
    DisplayField,
    FormworkBaseModelFormSet,
    FormworkCellMixin,
    FormworkForm,
    FormworkModelForm,
    FormworkRowSaveMixin,
    formwork_modelformset_factory,
)
from django_formwork.forms import PREFIX_INPUT_NAME
from django_formwork.renderers import engine
from django_formwork.widgets import ChoiceLabel, ComboBox, ComboBoxMultiple, Select, SelectMultiple

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


def test_row_url_gives_a_row_an_open_link():
    first = UniqueCode.objects.create(code="A")
    UniqueCode.objects.create(code="B")

    class LinkedRows(CodeFormSet):
        can_add = False
        can_delete = False

        def row_url(self, form):
            return f"/codes/{form.instance.pk}/" if form.instance == first else ""

    html = LinkedRows(queryset=UniqueCode.objects.order_by("code")).as_rows()

    linked, plain = BeautifulSoup(html, "html.parser").select("table > tbody")
    assert linked.find("a", attrs={"aria-label": "Open"})["href"] == f"/codes/{first.pk}/"
    assert plain.find("a", attrs={"aria-label": "Open"}) is None


class DetailedRows(formwork_modelformset_factory(UniqueCode, form=CodeRowForm, extra=0)):
    def row_details(self, form):
        return form.instance.label or None


def test_row_details_open_under_their_row_and_a_row_without_any_keeps_the_column():
    UniqueCode.objects.create(code="A", label="alpha")
    UniqueCode.objects.create(code="B")

    soup = BeautifulSoup(DetailedRows(queryset=UniqueCode.objects.order_by("code")).as_rows(), "html.parser")

    detailed, plain = soup.select("table > tbody")
    toggle = detailed.select_one("details[data-row-toggle] summary")
    assert detailed.find(id=toggle["aria-controls"]).get_text(strip=True) == "alpha"
    assert plain.select("[data-row-toggle], [data-row-details]") == []
    assert len(soup.thead.find_all("th")) == len(plain.tr.find_all("td"))


@pytest.mark.parametrize(
    ("label", "bold"), [("<b>alpha</b>", False), (format_html("<b>{}</b>", "alpha"), True)], ids=["text", "html"]
)
def test_row_details_show_as_text_unless_marked_safe(label, bold):
    UniqueCode.objects.create(code="A")

    class Rows(DetailedRows):
        def row_details(self, form):
            return label

    details = BeautifulSoup(Rows(queryset=UniqueCode.objects.all()).as_rows(), "html.parser").select_one(
        "[data-row-details]"
    )

    assert (details.find("b") is not None) is bold


def test_an_autosaved_table_has_no_row_details():
    UniqueCode.objects.create(code="A", label="alpha")

    html = DetailedRows(queryset=UniqueCode.objects.all()).as_rows(save_url="/save/")

    assert BeautifulSoup(html, "html.parser").select("[data-row-toggle], [data-row-details]") == []


def test_as_rows_renders_a_plain_model_form():
    class PlainForm(forms.ModelForm):
        class Meta:
            model = UniqueCode
            fields = ["code"]

    UniqueCode.objects.create(code="A")
    formset = formwork_modelformset_factory(UniqueCode, form=PlainForm, extra=0)(queryset=UniqueCode.objects.all())

    cell = BeautifulSoup(formset.as_rows(), "html.parser").find("td", attrs={"data-field": "code"})

    assert cell.find("input")["value"] == "A"


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
    (tmp_path / "rows" / "code.html").write_text("<tbody>{{ form.code.value }} in a project row</tbody>")
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


class CityRowForm(FormworkModelForm):
    class Meta:
        model = City
        fields = ["name", "region"]
        widgets = {"region": Select()}


CityFormSet = formwork_modelformset_factory(City, form=CityRowForm, extra=1)


class CityCell(FormworkCellMixin):
    formset_class = CityFormSet
    queryset = City.objects.all()


@pytest.fixture
def cities():
    north, south = Region.objects.create(name="North"), Region.objects.create(name="South")
    return [City.objects.create(name="Aberdeen", region=north), City.objects.create(name="Brighton", region=south)]


def _cell(view, **query):
    return BeautifulSoup(view().get(RequestFactory().get("/cells/", query)).content, "html.parser")


def test_as_rows_with_a_cell_url_renders_the_selects_of_the_saved_rows_as_stubs(cities):
    html = CityFormSet(queryset=City.objects.all()).as_rows(cell_url="/cells/?table=cities")

    soup = BeautifulSoup(html, "html.parser")
    stubs = [parse_qs(urlsplit(stub["data-formwork-stub"]).query) for stub in soup.select("[data-formwork-stub]")]
    assert stubs == [
        {"table": ["cities"], "field": ["region"], "pk": [str(city.pk)], "prefix": [f"form-{index}"]}
        for index, city in enumerate(cities)
    ]
    assert soup.select_one("[x-data=formworkSelect] [name=form-2-region]") is not None


@pytest.mark.parametrize("cell_url", ["", "/cells/"])
def test_as_rows_runs_the_same_queries_for_more_rows(cities, cell_url):
    def queries():
        formset = CityFormSet(queryset=City.objects.all())
        with CaptureQueriesContext(connection) as captured:
            formset.as_rows(cell_url=cell_url)
        return len(captured)

    two_rows = queries()
    for name in ["Cardiff", "Dover", "Exeter"]:
        City.objects.create(name=name, region=Region.objects.create(name=f"{name} region"))

    assert queries() == two_rows


def test_the_select_stubs_of_as_rows_label_a_chosen_row_once_for_all_rows_that_hold_it(cities, monkeypatch):
    labelled = []
    label_from_instance = forms.ModelChoiceField.label_from_instance
    monkeypatch.setattr(
        forms.ModelChoiceField,
        "label_from_instance",
        lambda field, obj: labelled.append(obj) or label_from_instance(field, obj),
    )

    def render():
        labelled.clear()
        soup = BeautifulSoup(CityFormSet(queryset=City.objects.all()).as_rows(cell_url="/cells/"), "html.parser")
        labels = soup.select("[data-formwork-stub] .formwork-autowidth-stack > span:not(.formwork-autowidth)")
        return len(labelled), [label.get_text(strip=True) for label in labels]

    two_rows, _ = render()
    north = cities[0].region
    City.objects.bulk_create(City(name=name, region=north) for name in ["Cardiff", "Dover", "Exeter"])
    five_rows, shown = render()

    assert five_rows == two_rows
    assert shown == ["North", "South", "North", "North", "North"]


def test_the_selects_of_as_rows_copy_every_choice_from_one_list_of_their_column(cities):
    soup = BeautifulSoup(CityFormSet(queryset=City.objects.order_by("pk")).as_rows(), "html.parser")

    selects = soup.select("[x-data=formworkSelect]")
    (source,) = {select.select_one("[role=listbox]").get("data-options") for select in selects}
    labels = [option["data-label"] for option in soup.find("template", id=source).select("[role=option]")]
    assert not soup.select("[x-data=formworkSelect] [role=option]")
    assert {"North", "South"} <= set(labels)
    assert [select["data-value"] for select in selects] == [str(city.region_id) for city in cities] + [""]


class SizeRowForm(CityRowForm):
    size = forms.ChoiceField(choices=[("s", "Small"), ("l", "Large")], widget=Select())


class OwnSizeRowForm(SizeRowForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["size"].choices = [*self.fields["size"].choices, ("own", self.instance.name)]


@pytest.mark.parametrize(
    ("form", "own", "copied"),
    [(SizeRowForm, [], ["Small", "Large"]), (OwnSizeRowForm, ["Small", "Large", "Brighton"], [])],
)
def test_the_selects_of_fixed_choices_copy_them_from_their_column_unless_a_row_can_change_them(
    cities, form, own, copied
):
    formset = formwork_modelformset_factory(City, form=form, extra=0)(queryset=City.objects.order_by("pk"))

    soup = BeautifulSoup(formset.as_rows(), "html.parser")

    assert [option["data-label"] for option in soup.select("[data-name=form-1-size] [role=option]")] == own
    templates = soup.find_all("template", id="form-size-options")
    assert [option["data-label"] for template in templates for option in template.select("[role=option]")] == copied


def test_a_cell_answers_with_the_full_select_for_the_value_its_stub_holds(cities):
    south = cities[1].region

    soup = _cell(CityCell, field="region", pk=cities[0].pk, prefix="form-0", **{"form-0-region": south.pk})

    value = soup.select_one("[x-data=formworkSelect] input[type=hidden]")
    assert (value["name"], value["value"]) == ("form-0-region", str(south.pk))


class NorthOnlyFormSet(FormworkBaseModelFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields["region"].queryset = Region.objects.filter(name="North")


def test_a_cell_gives_its_row_the_choices_that_a_hook_of_the_formset_gives_it(cities):
    class Cell(CityCell):
        formset_class = formwork_modelformset_factory(City, form=CityRowForm, formset=NorthOnlyFormSet, extra=0)

    soup = _cell(Cell, field="region", pk=cities[1].pk, prefix="form-1")

    labels = {option.get_text(strip=True) for option in soup.select("[role=option]")}
    assert "North" in labels
    assert "South" not in labels


@pytest.mark.parametrize(("field", "pk"), [("country", None), ("region", "not-a-number"), ("region", 0)])
def test_a_cell_of_an_unknown_field_or_of_a_row_outside_the_queryset_is_not_found(cities, field, pk):
    with pytest.raises(Http404):
        _cell(CityCell, field=field, pk=cities[0].pk if pk is None else pk, prefix="form-0")


class TagsRowForm(FormworkModelForm):
    class Meta:
        model = Item
        fields = ["name", "tags"]
        widgets = {"tags": SelectMultiple()}


TagsFormSet = formwork_modelformset_factory(Item, form=TagsRowForm, extra=0)


class TagsCell(FormworkCellMixin):
    formset_class = TagsFormSet
    queryset = Item.objects.all()


@pytest.fixture
def tagged():
    kitchen = Category.objects.create(name="Kitchen", slug="kitchen")
    tags = [Tag.objects.create(name=name) for name in ("eco", "new", "sale", "used")]
    for name, count in [("Kettle", 0), ("Lamp", 2), ("Toaster", 4)]:
        Item.objects.create(name=name, category=kitchen).tags.set(tags[:count])
    return tags


def _rows(*, cell_url=""):
    formset = TagsFormSet(queryset=Item.objects.order_by("pk").prefetch_related("tags"))
    return BeautifulSoup(formset.as_rows(cell_url=cell_url), "html.parser")


def _closed(soup, selector):
    elements = soup.select(selector)
    for tag in [*elements, *(child for element in elements for child in element.find_all())]:
        tag.attrs = {
            name: value for name, value in tag.attrs.items() if not name.startswith((":", "x-", "@", "aria-controls"))
        }
    return [str(element) for element in elements]


def test_the_select_multiple_stubs_of_as_rows_show_the_closed_toggles_of_the_full_selects(tagged):
    stubs = _rows(cell_url="/cells/")

    assert len(stubs.select("[data-formwork-stub]:has([name$=-tags])")) == 3
    toggles = "details:has([name$=-tags]) > summary"
    assert len(set(_closed(stubs, toggles))) == 3
    assert _closed(stubs, toggles) == _closed(_rows(), toggles)


@pytest.mark.parametrize("cell_url", ["", "/cells/"])
def test_the_select_multiples_of_as_rows_post_the_values_of_their_rows(tagged, cell_url):
    data = MultiValueDict()
    for element in _rows(cell_url=cell_url).select("input[name]"):
        if element.find_parent("template") or (element.get("type") == "checkbox" and not element.has_attr("checked")):
            continue
        data.appendlist(element["name"], element.get("value", ""))

    formset = TagsFormSet(data, queryset=Item.objects.order_by("pk"))

    assert formset.is_valid()
    assert not formset.has_changed()


@pytest.mark.parametrize("cell_url", ["", "/cells/"])
def test_the_select_multiples_of_as_rows_run_the_same_queries_for_more_rows(tagged, cell_url):
    def queries():
        with CaptureQueriesContext(connection) as captured:
            _rows(cell_url=cell_url)
        return len(captured)

    three_rows = queries()
    for name in ["Grill", "Iron"]:
        Item.objects.create(name=name, category=Category.objects.get()).tags.set(tagged[1:])

    assert queries() == three_rows


def test_a_select_multiple_cell_answers_with_the_full_select_for_the_values_its_stub_holds(tagged):
    lamp = Item.objects.get(name="Lamp")
    eco, _new, sale, used = tagged

    soup = _cell(TagsCell, field="tags", pk=lamp.pk, prefix="form-1", **{"form-1-tags": ["", sale.pk, used.pk]})

    checked = soup.select("[x-data=formworkSelectMultiple] input[type=checkbox][checked]")
    assert [box["value"] for box in checked] == [str(sale.pk), str(used.pk)]
    assert eco.name in soup.select_one(".formwork-autowidth").get_text()


class DoverRowForm(SizeRowForm):
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("name") == "Dover":
            self.add_error("region", "No ferries.")
        return cleaned_data


class NamedSelect(Select):
    template_name = "cells/named.html"


class NamedSelectRowForm(CityRowForm):
    class Meta(CityRowForm.Meta):
        widgets = {"region": NamedSelect()}


@pytest.fixture
def towns(cities):
    north = cities[0].region
    City.objects.bulk_create(City(name=name, region=north) for name in ["Cardiff", "Dover", "Exeter"])


@pytest.fixture
def more_tagged(tagged):
    category = Category.objects.get()
    Item.objects.create(name="Grill", category=category, price=5, is_featured=True).tags.set(tagged[:2])
    Item.objects.create(name="Iron", category=category, price=5)


def _posted_cities(form=DoverRowForm):
    rows = list(City.objects.order_by("pk"))
    data = {"form-TOTAL_FORMS": len(rows), "form-INITIAL_FORMS": len(rows)}
    for index, city in enumerate(rows):
        data |= {
            f"form-{index}-id": city.pk,
            f"form-{index}-name": city.name,
            f"form-{index}-region": city.region_id,
            f"form-{index}-size": "s",
        }
    formset_class = formwork_modelformset_factory(City, form=form, extra=0)
    return formset_class(data, queryset=City.objects.order_by("pk"))


def _tagged_items():
    return TagsFormSet(queryset=Item.objects.order_by("pk").prefetch_related("tags"))


class StockRowForm(FormworkModelForm):
    class Meta:
        model = Item
        fields = ["name", "price", "is_featured"]


StockFormSet = formwork_modelformset_factory(Item, form=StockRowForm, extra=0)


def _stock():
    return StockFormSet(queryset=Item.objects.order_by("pk"))


@pytest.mark.parametrize("cell_url", ["", "/cells/"])
@pytest.mark.parametrize("rows", [_posted_cities, _tagged_items, _stock])
def test_the_columns_of_as_rows_render_the_html_of_rows_rendered_one_by_one(
    towns, more_tagged, monkeypatch, rows, cell_url
):
    cached = str(rows().as_rows(cell_url=cell_url))

    monkeypatch.setattr("django_formwork.formsets.cache_cells", lambda formset: None)

    assert str(rows().as_rows(cell_url=cell_url)) == cached


@pytest.mark.parametrize("cell_url", ["", "/cells/"])
@pytest.mark.parametrize("posted", [False, True])
def test_the_selects_of_as_rows_build_the_widget_of_a_value_once_for_all_rows_that_hold_it(
    cities, monkeypatch, cell_url, posted
):
    built = []
    for method in ("get_context", "get_stub_context"):
        original = getattr(Select, method)
        monkeypatch.setattr(
            Select, method, lambda select, *args, _original=original: built.append(args) or _original(select, *args)
        )

    def render():
        built.clear()
        formset = _posted_cities(SizeRowForm) if posted else CityFormSet(queryset=City.objects.all())
        formset.as_rows(cell_url=cell_url)
        return len(built)

    two_rows = render()
    north = cities[0].region
    City.objects.bulk_create(City(name=name, region=north) for name in ["Cardiff", "Dover", "Exeter"])

    assert render() == two_rows


@pytest.mark.parametrize("widget", [forms.NumberInput, forms.CheckboxInput])
def test_the_number_and_checkbox_columns_of_as_rows_build_the_widget_of_a_value_once(tagged, monkeypatch, widget):
    built = []
    original = widget.get_context
    monkeypatch.setattr(widget, "get_context", lambda self, *args: built.append(args) or original(self, *args))

    def render():
        built.clear()
        _stock().as_rows()
        return len(built)

    three_rows = render()
    Item.objects.create(name="Grill", category=Category.objects.get())

    assert render() == three_rows


class MandatoryRowForm(StockRowForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.name == "Toaster":
            self.mandatory.add("is_featured")


class MandatoryFormSet(formwork_modelformset_factory(Item, form=MandatoryRowForm, extra=0)):
    def get_form_kwargs(self, index):
        return {**super().get_form_kwargs(index), "use_required_attribute": True}


def test_the_rows_of_a_column_mark_the_field_where_their_form_makes_it_mandatory(tagged):
    soup = BeautifulSoup(MandatoryFormSet(queryset=Item.objects.order_by("pk")).as_rows(), "html.parser")

    assert [box.get("aria-required") for box in soup.select("input[name$=-is_featured]")] == [None, None, "true"]


@pytest.mark.parametrize(
    "name",
    [
        "widget.name|upper if widget.selected_label == 'South' else widget.name",
        "widget.name|tojson if widget.selected_label == 'South' else widget.name",
        "widget.name|replace('-', '_')",
    ],
)
def test_a_select_whose_template_changes_its_name_renders_the_name_of_each_row(towns, monkeypatch, name):
    env = engine().env
    template = jinja2.DictLoader({"cells/named.html": f"<i data-name>{{{{ {name} }}}}</i>"})
    monkeypatch.setattr(env, "loader", jinja2.ChoiceLoader([template, env.loader]))
    formset_class = formwork_modelformset_factory(City, form=NamedSelectRowForm, extra=0)

    def names():
        html = formset_class(queryset=City.objects.order_by("pk")).as_rows()
        return [tag.get_text() for tag in BeautifulSoup(html, "html.parser").select("i[data-name]")]

    cached = names()
    monkeypatch.setattr("django_formwork.formsets.cache_cells", lambda formset: None)

    assert cached == names()
    assert len(set(cached)) == City.objects.count()


class PeriodRowForm(FormworkModelForm):
    period = DateRangeField(required=False)

    class Meta:
        model = Item
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        released = self.instance.released
        self.initial["period"] = DateRange(released, released and released + dt.timedelta(days=6))


PeriodFormSet = formwork_modelformset_factory(Item, form=PeriodRowForm, extra=0)


class PeriodCell(FormworkCellMixin):
    formset_class = PeriodFormSet
    queryset = Item.objects.all()


@pytest.fixture
def released():
    kitchen = Category.objects.create(name="Kitchen", slug="kitchen")
    return [
        Item.objects.create(name=name, category=kitchen, released=day)
        for name, day in [("Kettle", None), ("Lamp", dt.date(2026, 3, 4))]
    ]


def _periods(*, cell_url=""):
    return BeautifulSoup(PeriodFormSet(queryset=Item.objects.order_by("pk")).as_rows(cell_url=cell_url), "html.parser")


def test_the_date_range_stubs_of_as_rows_show_the_closed_fields_of_the_full_pickers(released):
    stubs = _periods(cell_url="/cells/")

    assert len(stubs.select("[data-formwork-stub] [role=group]")) == 2
    assert _closed(stubs, ".date-range-picker [role=group]") == _closed(_periods(), ".date-range-picker [role=group]")


def test_the_date_range_stubs_of_as_rows_post_the_ranges_of_their_rows(released):
    stubs = _periods(cell_url="/cells/").select("input[name]")

    formset = PeriodFormSet(
        {stub["name"]: stub.get("value", "") for stub in stubs}, queryset=Item.objects.order_by("pk")
    )

    assert formset.is_valid()
    assert not formset.has_changed()


def test_a_date_range_cell_answers_with_the_full_picker_for_the_range_its_stub_holds(released):
    query = {"form-1-period_0": "2026-05-01", "form-1-period_1": "2026-05-09"}

    soup = _cell(PeriodCell, field="period", pk=released[1].pk, prefix="form-1", **query)

    picker = soup.select_one("[x-data=formworkDateRangePicker]")
    assert (picker["data-start"], picker["data-end"]) == ("2026-05-01", "2026-05-09")


_NAMES = [ChoiceLabel("Lamp", icon="\U0001f4a1"), "Kettle", "Toaster"]


class NamedRowForm(FormworkModelForm):
    class Meta:
        model = Item
        fields = ["name", "notes"]
        widgets = {"name": ComboBox(suggestions=_NAMES), "notes": ComboBoxMultiple(suggestions=_NAMES)}


NamedFormSet = formwork_modelformset_factory(Item, form=NamedRowForm, extra=0)


@pytest.fixture
def named():
    kitchen = Category.objects.create(name="Kitchen", slug="kitchen")
    for name, notes in [("Kettle", ""), ("Lamp", "Lamp, Kettle"), ("Sink", "Sink")]:
        Item.objects.create(name=name, category=kitchen, notes=notes)


def _named(*, cell_url=""):
    return BeautifulSoup(NamedFormSet(queryset=Item.objects.order_by("pk")).as_rows(cell_url=cell_url), "html.parser")


def test_the_combo_box_stubs_of_as_rows_size_their_inputs_by_the_suggestions_of_the_full_combo_boxes(named):
    stubs = _named(cell_url="/cells/")

    assert len(stubs.select("[data-formwork-stub].formwork-combobox")) == 6
    copies = ".formwork-combobox > .formwork-autowidth"
    assert _closed(stubs, copies) == _closed(_named(), copies)


def test_the_combo_box_stubs_of_as_rows_post_the_values_of_their_rows(named):
    stubs = _named(cell_url="/cells/").select("input[name]")

    formset = NamedFormSet(
        {stub["name"]: stub.get("value", "") for stub in stubs}, queryset=Item.objects.order_by("pk")
    )

    assert formset.is_valid()
    assert not formset.has_changed()


@pytest.mark.parametrize(
    ("field", "shown"),
    [("name", ["", "\U0001f4a1Lamp", ""]), ("notes", ["", "\U0001f4a1Lamp,\xa0Kettle", "Sink"])],
)
def test_a_combo_box_stub_shows_its_value_with_the_icons_of_its_suggestions(named, field, shown):
    stubs = _named(cell_url="/cells/").select(f".formwork-combobox:has([name$=-{field}])")

    displays = [stub.select_one(".combobox-display") for stub in stubs]

    assert [display.get_text() if display else "" for display in displays] == shown
    assert [bool(stub.select(".text-transparent")) for stub in stubs] == [bool(text) for text in shown]
