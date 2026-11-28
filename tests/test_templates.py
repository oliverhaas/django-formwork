import json
import re

import jinja2
import pytest
from bs4 import BeautifulSoup
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.utils.html import format_html

from django_formwork.forms import FormworkForm
from django_formwork.renderers import FormworkRenderer, engine
from django_formwork.widgets import Select


def render_html(form):
    return BeautifulSoup(str(form), "html.parser")


class TestFieldsetStructure:
    """Each visible field is wrapped in a DaisyUI fieldset."""

    def test_field_wrapped_in_fieldset(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset is not None

    def test_label_is_fieldset_legend(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        label = soup.find("label", class_="fieldset-legend")
        assert label is not None
        assert "Name" in label.get_text()

    def test_label_has_for_attribute(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        label = soup.find("label", class_="fieldset-legend")
        assert label["for"] == "id_name"

    def test_widget_inside_fieldset(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        inp = fieldset.find("input")
        assert inp is not None

    def test_help_text_in_disclosure_summary(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        soup = render_html(F())
        details = soup.find("details", class_="formwork-disclosure")
        assert details is not None
        summary = details.find("summary", class_="label")
        assert summary is not None
        assert "Enter your name" in summary.get_text()

    def test_help_text_has_id(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        soup = render_html(F())
        helptext = soup.find(id="id_name_helptext")
        assert helptext is not None
        assert "Enter your name" in helptext.get_text()

    def test_help_text_has_leading_info_icon(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        soup = render_html(F())
        summary = soup.find("summary", class_="label")
        icon = summary.find("i", class_="icon-info")
        assert icon is not None
        assert icon.get("aria-hidden") == "true"

    def test_multi_widget_uses_legend(self):
        """RadioSelect fields use <legend> instead of <label>."""

        class F(FormworkForm):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        soup = render_html(F())
        legend = soup.find("legend", class_="fieldset-legend")
        assert legend is not None
        assert "Choice" in legend.get_text()


class TestFieldOrdering:
    """Label -> widget -> errors -> helptext ordering."""

    def test_label_before_widget(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        all_elements = list(soup.descendants)
        label = soup.find("label", class_="fieldset-legend")
        inp = soup.find("input")
        assert all_elements.index(label) < all_elements.index(inp)

    def test_widget_before_helptext(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Help")

        soup = render_html(F())
        all_elements = list(soup.descendants)
        inp = soup.find("input")
        details = soup.find("details", class_="formwork-disclosure")
        assert all_elements.index(inp) < all_elements.index(details)

    def test_errors_before_helptext(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Help")

        form = F(data={"name": ""}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        helptext = soup.find(id="id_name_helptext")
        assert error_div is not None
        assert helptext is not None
        all_elements = list(soup.descendants)
        assert all_elements.index(error_div) < all_elements.index(helptext)


class TestErrorRendering:
    """Errors render as DaisyUI tooltip on the fieldset."""

    def test_errors_rendered_in_container(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        assert error_div is not None
        assert error_div.find("p") is not None

    def test_error_container_has_role_alert(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        assert error_div["role"] == "alert"

    def test_tooltip_wrapper_around_widget_on_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        wrapper = soup.find("div", class_="tooltip")
        assert wrapper is not None
        assert "tooltip-error" in wrapper.get("class", [])
        assert "tooltip-bottom" in wrapper.get("class", [])
        # Widget is inside the tooltip wrapper
        assert wrapper.find("input") is not None

    def test_no_tooltip_wrapper_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        wrapper = soup.find("div", class_="tooltip")
        assert wrapper is None

    def test_no_errors_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        assert error_div is None

    def test_multiple_errors_in_single_container(self):
        class F(FormworkForm):
            email = forms.EmailField(min_length=20)

        form = F(data={"email": "bad"}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        errors = error_div.find_all("p")
        assert len(errors) >= 2


class TestInlineErrorRendering:
    """Errors render as a red help-text-style row when Meta.error_display = "inline"."""

    def test_no_tooltip_wrapper(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        assert soup.find("div", class_="tooltip") is None

    def test_error_row_has_role_alert_and_id(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        error = soup.find(id="id_name_error")
        assert error is not None
        assert error["role"] == "alert"
        # text-error stays off the summary so its [more]/[less] ::after keeps
        # the muted .label color.
        row = error.find_parent("span", class_="formwork-disclosure-row")
        assert "text-error" in row.get("class", [])
        summary = error.find_parent("summary")
        assert "text-error" not in summary.get("class", [])

    def test_error_row_has_leading_icon(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        summary = soup.find(id="id_name_error").find_parent("summary")
        # An X-in-circle error glyph, not the "!"-in-circle alert (which is
        # near-identical to the info icon the help text uses at 16px). The X
        # reads as "invalid/failed" and stays distinct from help, without
        # borrowing a warning triangle to mean "error".
        icon = summary.find("i", class_="icon-circle-x")
        assert icon is not None
        assert icon.get("aria-hidden") == "true"

    def test_disclosure_has_formwork_errors_hook(self):
        # .formwork-errors is what disableNativeValidation() keys off, so inline
        # mode reaches parity with tooltip mode: once a server error is showing,
        # native validation turns off and later errors route to the server.
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        disclosure = soup.find(id="id_name_disclosure")
        assert "formwork-errors" in disclosure.get("class", [])

    def test_multiple_errors_joined_in_single_row(self):
        class F(FormworkForm):
            email = forms.EmailField(min_length=20)

        form = F(data={"email": "bad"}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        error = soup.find(id="id_email_error")
        assert error.find_all("p") == []
        assert len(form.errors["email"]) >= 2
        for message in form.errors["email"]:
            assert message in error.get_text()

    def test_help_text_row_inside_summary_when_collapsed(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        helptext = soup.find(id="id_name_helptext")
        assert helptext is not None
        assert "Enter your name" in helptext.get_text()
        # Help lives inside the <summary> so the [less] ::after can follow it
        # at the bottom and stay clickable; CSS hides the row while closed but
        # keeps it in the DOM for aria-describedby and htmx morphs.
        assert helptext.find_parent("summary") is not None
        details = helptext.find_parent("details")
        assert details is not None
        assert not details.has_attr("open")
        assert "formwork-disclosure-body" in helptext.get("class", [])

    def test_no_body_or_button_when_error_has_no_help_text(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        disclosure = soup.find(id="id_name_disclosure")
        # No help text -> nothing to reveal, so no body. The [more]/[less]
        # affordance is a CSS ::after gated on data-expandable, which
        # measureDisclosures sets client-side only when the summary overflows;
        # the server renders neither a button nor a body.
        assert disclosure.find("button") is None
        assert disclosure.find(class_="formwork-disclosure-body") is None


class TestNonFieldErrors:
    """Non-field errors use DaisyUI alert component."""

    def test_non_field_errors_rendered(self):
        class F(FormworkForm):
            name = forms.CharField()

            def clean(self):
                raise forms.ValidationError("Form-level error")

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        alert = soup.find("div", class_="alert")
        assert alert is not None
        assert "alert-error" in alert.get("class", [])
        assert "Form-level error" in alert.get_text()


class TestAriaAttributes:
    """Django's built-in aria attributes are preserved."""

    def test_aria_invalid_on_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"aria-invalid": "true"})
        assert inp is not None

    def test_no_aria_invalid_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        assert inp.get("aria-invalid") is None

    def test_aria_describedby_for_help_text(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Your name")

        soup = render_html(F())
        inp = soup.find("input", {"name": "name"})
        assert inp is not None
        assert "id_name_helptext" in (inp.get("aria-describedby") or "")

    def test_aria_describedby_targets_exist(self):
        """Every id referenced by aria-describedby must point to a real element.

        Django bakes ``aria-describedby="{auto_id}_error"`` onto the widget, so
        the error container's id has to match it or the reference dangles for
        screen readers.
        """

        class F(FormworkForm):
            name = forms.CharField(help_text="Your name")

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        described = (inp.get("aria-describedby") or "").split()
        assert described, "expected aria-describedby on an errored field"
        for ref in described:
            assert soup.find(id=ref) is not None, f"aria-describedby points to missing #{ref}"

    def test_aria_describedby_targets_exist_in_inline_mode(self):
        """The collapsed <details> body help text stays in the DOM so aria-describedby resolves."""

        class F(FormworkForm):
            name = forms.CharField(help_text="Your name")

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        described = (inp.get("aria-describedby") or "").split()
        assert described, "expected aria-describedby on an errored field"
        for ref in described:
            assert soup.find(id=ref) is not None, f"aria-describedby points to missing #{ref}"


class TestHiddenFields:
    """Hidden fields render without fieldset wrapper."""

    def test_hidden_field_rendered(self):
        class F(FormworkForm):
            visible = forms.CharField()
            hidden = forms.CharField(widget=forms.HiddenInput)

        soup = render_html(F())
        hidden_input = soup.find("input", {"type": "hidden", "name": "hidden"})
        assert hidden_input is not None

    def test_hidden_field_not_in_fieldset(self):
        class F(FormworkForm):
            visible = forms.CharField()
            hidden = forms.CharField(widget=forms.HiddenInput)

        soup = render_html(F())
        fieldsets = soup.find_all("fieldset", class_="fieldset")
        legends = [fs.find(["legend", "label"], class_="fieldset-legend") for fs in fieldsets]
        legend_texts = [leg.get_text() for leg in legends if leg]
        assert not any("Hidden" in t for t in legend_texts)


class TestMorphingIds:
    """All elements have stable IDs for htmx morph matching."""

    def test_fieldset_has_id(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_name_field"

    def test_fieldset_id_uses_auto_id(self):
        class F(FormworkForm):
            email = forms.EmailField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_email_field"

    def test_fieldset_id_with_prefix(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F(prefix="contact"))
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_contact-name_field"

    def test_errors_div_has_id_on_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        errors = soup.find("div", class_="tooltip-content")
        assert errors["id"] == "id_name_error"

    def test_non_field_errors_have_no_fixed_id(self):
        """Two forms on one page must not repeat an id."""

        class F(FormworkForm):
            name = forms.CharField()

            def clean(self):
                raise forms.ValidationError("Form-level error")

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        alert = soup.find("div", class_="alert")
        assert not alert.has_attr("id")

    def test_use_fieldset_branch_has_ids(self):
        """RadioSelect fields use <legend> and use_fieldset=True branch."""

        class F(FormworkForm):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        form = F(data={}, error_display="tooltip")
        form.is_valid()
        soup = render_html(form)
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_choice_field"
        errors = soup.find("div", class_="tooltip-content")
        assert errors["id"] == "id_choice_error"

    def test_no_tooltip_id_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        tooltip = soup.find("div", class_="tooltip")
        assert tooltip is None


class TestTemplateTags:
    """formwork_css / formwork_js emit link and script tags for the static assets."""

    def test_formwork_css_tag_is_deprecated(self):
        template = Template("{% load formwork %}{% formwork_css %}")
        with pytest.warns(DeprecationWarning, match="Tailwind"):
            html = template.render(Context())
        assert "formwork/formwork.css" in html

    def test_formwork_js_tag(self):
        template = Template("{% load formwork %}{% formwork_js %}")
        html = template.render(Context())
        assert "<script" in html
        assert "formwork/formwork.js" in html


def test_formwork_head_links_the_stylesheets_then_loads_htmx_formwork_and_alpine_in_order():
    """htmx and its Alpine bridge run before formwork's modules, and Alpine after them."""
    template = Template('{% load formwork %}{% formwork_head "dist.css" "https://cdn.example.com/a.css" %}')

    soup = BeautifulSoup(template.render(Context()), "html.parser")

    assert [link["href"] for link in soup.find_all("link")] == ["/static/dist.css", "https://cdn.example.com/a.css"]
    scripts = soup.find_all("script")
    names = [re.search(r"htmx\.min|hx-alpine-compat|formwork\.js|alpinejs", script["src"])[0] for script in scripts]
    assert names == ["htmx.min", "hx-alpine-compat", "formwork.js", "alpinejs"]
    assert (scripts[2].get("type"), scripts[3].has_attr("defer")) == ("module", True)


class _ChangedForm(FormworkForm):
    name = forms.CharField(initial="Ada")
    city = forms.CharField(initial="Oslo")
    age = forms.IntegerField(initial=30, min_value=0)
    upload = forms.FileField(required=False)


@pytest.mark.parametrize(("field", "marked"), [("name", True), ("city", False), ("age", True), ("upload", False)])
def test_a_failed_save_keeps_the_mark_on_each_changed_field(field, marked):
    """A file input renders empty again, so it keeps no mark."""
    form = _ChangedForm(
        data={"name": "Grace", "city": "Oslo", "age": "-1"},
        files={"upload": SimpleUploadedFile("notes.txt", b"x")},
    )
    form.is_valid()

    fieldset = BeautifulSoup(str(form[field].as_field_group()), "html.parser").find("fieldset")

    assert fieldset.has_attr("data-formwork-changed") is marked


class _ChoicesChangedForm(FormworkForm):
    notify = forms.ChoiceField(choices=[("email", "Email"), ("sms", "SMS")], widget=forms.RadioSelect, initial="email")
    toppings = forms.MultipleChoiceField(
        choices=[("cheese", "Cheese"), ("olives", "Olives")],
        widget=forms.CheckboxSelectMultiple,
        initial=["cheese"],
        required=False,
    )
    agree = forms.BooleanField(initial=True, required=False)
    age = forms.IntegerField(min_value=0)


@pytest.mark.parametrize(
    ("field", "data", "initial"),
    [
        ("notify", {"notify": "sms"}, ["email"]),
        ("toppings", {"notify": "email", "toppings": ["olives"]}, ["cheese"]),
        ("agree", {"notify": "email"}, ["on"]),
    ],
)
def test_a_failed_save_sends_the_options_a_changed_field_had_checked(field, data, initial):
    form = _ChoicesChangedForm(data={"age": "-1", **data})
    form.is_valid()

    fieldset = BeautifulSoup(str(form[field].as_field_group()), "html.parser").find("fieldset")

    assert json.loads(fieldset["data-formwork-initial"]) == initial


class _LabelLinks:
    def label_links(self, name, value, renderer=None):
        return format_html('<a href="/{}/{}/">Edit</a>', name, value)


@pytest.mark.parametrize("widget", [forms.TextInput, forms.RadioSelect])
def test_a_widget_puts_its_label_links_in_the_label_row_outside_the_label(widget):
    """Outside the label or legend, so the links stay out of the field's name."""

    class F(FormworkForm):
        venue = forms.ChoiceField(choices=[("hall", "Hall")], widget=type("Linked", (_LabelLinks, widget), {}))

    fieldset = BeautifulSoup(str(F(initial={"venue": "hall"})["venue"].as_field_group()), "html.parser").find(
        "fieldset"
    )

    assert [a["href"] for a in fieldset.select(":scope > .formwork-label-links a")] == ["/venue/hall/"]
    assert fieldset.select("label a, legend a") == []


class _Labelled(dict):
    label = "attribute"


@pytest.mark.parametrize(
    ("source", "context", "expected"),
    [
        ("{{ d.a }}", {"d": {"a": "key"}}, "key"),
        ("[{{ d.missing.deeper }}]", {"d": {}}, "[]"),
        ("{{ d.items is callable }}", {"d": {"items": "key"}}, "True"),
        ("{{ d.keys()|join(',') }}", {"d": {"a": 1, "b": 2}}, "a,b"),
        ("{{ d.label }}", {"d": _Labelled(label="key")}, "attribute"),
    ],
)
def test_formwork_templates_read_a_dict_as_jinja_does(source, context, expected):
    stock = jinja2.Environment(undefined=jinja2.ChainableUndefined, autoescape=True)

    rendered = [env.from_string(source).render(context) for env in (engine().env, stock)]

    assert rendered == [expected, expected]


def test_the_globals_of_one_template_stay_out_of_the_others():
    env = engine().env

    page = env.from_string("{{ title }}", globals={"title": "Page"})

    assert page.render() == "Page"
    assert env.from_string("[{{ title }}]").render() == "[]"
    assert "title" not in env.globals


class _PlainForm(forms.Form):
    name = forms.CharField()
    level = forms.ChoiceField(choices=[("junior", "Junior"), ("senior", "Senior")], widget=forms.RadioSelect)
    token = forms.CharField(widget=forms.HiddenInput, required=False)

    def clean(self):
        raise forms.ValidationError("Check the fields below.")


@pytest.mark.parametrize("layout", ["as_p", "as_div", "as_ul", "as_table"])
def test_a_plain_django_form_gets_formwork_markup_in_each_layout(layout):
    form = _PlainForm(data={"name": ""}, renderer=FormworkRenderer())

    soup = BeautifulSoup(str(getattr(form, layout)()), "html.parser")

    assert soup.select(".errorlist") == []
    assert soup.select_one(".alert-error[role=alert]").get_text(strip=True) == "Check the fields below."
    assert soup.select_one("fieldset#id_name_field input[name=name]") is not None
    assert len(soup.select("input[name=token]")) == 1


def test_as_ul_puts_each_field_group_in_a_list_item():
    soup = BeautifulSoup(str(_PlainForm(renderer=FormworkRenderer()).as_ul()), "html.parser")

    items = soup.find_all("li", recursive=False)

    assert [li.select_one("fieldset")["id"] for li in items] == ["id_name_field", "id_level_field"]


def test_as_table_puts_the_label_in_the_row_header_and_the_field_group_beside_it():
    soup = BeautifulSoup(str(_PlainForm(renderer=FormworkRenderer()).as_table()), "html.parser")

    name, level = soup.find_all("tr", recursive=False)

    assert name.select_one("th label")["for"] == "id_name"
    assert name.select_one("th label")["id"] == "id_name_label"
    assert name.select("td label, td legend") == []
    assert level.select_one("th label")["id"] == "id_level_label"
    assert level.select_one("td fieldset")["aria-labelledby"] == "id_level_label"
    assert level.select("td legend") == []


class _ControlForm(FormworkForm):
    name = forms.CharField()
    level = forms.ChoiceField(choices=[("junior", "Junior"), ("senior", "Senior")], widget=forms.RadioSelect)
    role = forms.ChoiceField(choices=[("dev", "Developer"), ("ops", "Operations")], widget=Select)


def test_as_control_names_the_widget_without_a_visible_label():
    soup = BeautifulSoup(str(_ControlForm()["name"].as_control()), "html.parser")

    assert soup.select("label, legend, fieldset") == []
    assert soup.select_one("input[name=name]")["aria-label"] == "Name"


def test_as_control_names_a_choice_group_and_a_dropdown_trigger():
    form = _ControlForm()

    group = BeautifulSoup(str(form["level"].as_control()), "html.parser").select_one("[data-formwork-field]")
    role = BeautifulSoup(str(form["role"].as_control()), "html.parser")

    assert (group["role"], group["aria-label"]) == ("group", "Level")
    label_id = role.select_one("[aria-labelledby]")["aria-labelledby"].split()[0]
    assert role.find(id=label_id).get_text() == "Role"


def test_as_control_shows_the_error_and_the_changed_mark():
    form = _ControlForm(data={"name": "", "level": "senior", "role": "dev"})
    form.is_valid()

    name = BeautifulSoup(str(form["name"].as_control()), "html.parser")
    level = BeautifulSoup(str(form["level"].as_control()), "html.parser").select_one("[data-formwork-field]")

    assert "id_name_error" in name.select_one("input[name=name]")["aria-describedby"]
    assert name.find(id="id_name_error").get_text(strip=True) != ""
    assert level.has_attr("data-formwork-changed")
