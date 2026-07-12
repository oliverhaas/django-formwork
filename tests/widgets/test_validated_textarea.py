"""Tests for ValidatedTextarea widget.

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: HTML structure, htmx attrs, Alpine bindings
    3. integration — form integration: fieldset wrapping, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: renders, typing, validation response, highlights
    6. e2e         — error flow: error messages appear, clear, persist while typing
    7. e2e         — morph resilience: typed content preserved across htmx morphs
    8. screenshot  — visual states: default, with-content, with-error-highlights
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ValidatedTextarea

from .conftest import assert_html_equivalent, render_form, render_widget


class ValidatedTextareaForm(FormworkForm):
    """Form fixture for ValidatedTextarea integration tests."""

    content = forms.CharField(
        widget=ValidatedTextarea(validate_url="/validate/"),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────────


@pytest.mark.unit
def test_instantiation_default_no_validate_url():
    """ValidatedTextarea can be instantiated without a validate_url."""
    widget = ValidatedTextarea()
    assert widget.validate_url is None


@pytest.mark.unit
def test_instantiation_with_validate_url():
    """ValidatedTextarea stores the validate_url."""
    widget = ValidatedTextarea(validate_url="/validate/")
    assert widget.validate_url == "/validate/"


@pytest.mark.unit
def test_attrs_passthrough():
    """User-supplied attrs are passed to the underlying Textarea."""
    widget = ValidatedTextarea(validate_url="/validate/", attrs={"rows": "5"})
    assert widget.attrs.get("rows") == "5"


@pytest.mark.unit
def test_get_context_validate_url():
    """get_context exposes validate_url in widget context."""
    widget = ValidatedTextarea(validate_url="/validate/")
    ctx = widget.get_context("content", "", {"id": "id_content"})
    assert ctx["widget"]["validate_url"] == "/validate/"


@pytest.mark.unit
def test_get_context_validate_url_none():
    """get_context exposes validate_url=None when not set."""
    widget = ValidatedTextarea()
    ctx = widget.get_context("content", "", {"id": "id_content"})
    assert ctx["widget"]["validate_url"] is None


@pytest.mark.unit
def test_get_context_aria_invalid():
    """get_context exposes aria_invalid from widget attrs."""
    widget = ValidatedTextarea(validate_url="/validate/")
    ctx = widget.get_context("content", "", {"id": "id_content", "aria-invalid": "true"})
    assert ctx["widget"]["aria_invalid"] == "true"


@pytest.mark.unit
def test_get_context_aria_invalid_absent():
    """get_context exposes aria_invalid=None when not in attrs."""
    widget = ValidatedTextarea(validate_url="/validate/")
    ctx = widget.get_context("content", "", {"id": "id_content"})
    assert ctx["widget"]["aria_invalid"] is None


@pytest.mark.unit
def test_value_from_datadict_returns_string():
    """value_from_datadict returns the submitted string value."""
    widget = ValidatedTextarea()
    data = QueryDict("content=hello+world")
    result = widget.value_from_datadict(data, {}, "content")
    assert result == "hello world"


@pytest.mark.unit
def test_value_from_datadict_missing_key():
    """value_from_datadict returns None when key is absent."""
    widget = ValidatedTextarea()
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "content")
    assert result is None


@pytest.mark.unit
def test_value_from_datadict_empty_string():
    """value_from_datadict returns empty string for empty submitted value."""
    widget = ValidatedTextarea()
    data = QueryDict("content=")
    result = widget.value_from_datadict(data, {}, "content")
    assert result == ""


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────────


@pytest.mark.unit
def test_renders_plain_textarea_without_validate_url():
    """Without validate_url, renders a plain textarea (no overlay structure)."""
    widget = ValidatedTextarea()
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea is not None
    assert textarea["name"] == "content"
    assert soup.find("div", class_="validated-textarea") is None


@pytest.mark.unit
def test_renders_overlay_with_validate_url():
    """With validate_url, renders the outer validated-textarea wrapper div."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    wrapper = soup.find("div", class_="validated-textarea")
    assert wrapper is not None


@pytest.mark.unit
def test_highlights_div_present():
    """With validate_url, a highlights div with correct id and aria-hidden is rendered."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    highlights = soup.find("div", class_="validated-textarea-highlights")
    assert highlights is not None
    assert highlights["id"] == "id_content_highlights"
    assert highlights["aria-hidden"] == "true"


@pytest.mark.unit
def test_textarea_inside_overlay():
    """With validate_url, the textarea is nested inside the overlay wrapper."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    wrapper = soup.find("div", class_="validated-textarea")
    textarea = wrapper.find("textarea")
    assert textarea is not None
    assert textarea["name"] == "content"
    assert textarea["id"] == "id_content"


@pytest.mark.unit
def test_errors_tooltip_present():
    """With validate_url, error tooltip with correct ids is rendered."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    tooltip = soup.find("div", class_="validated-textarea-tooltip")
    assert tooltip is not None
    assert tooltip["id"] == "id_content_vttooltip"
    errors = tooltip.find("div", class_="formwork-errors")
    assert errors is not None
    assert errors["id"] == "id_content_error"
    assert errors["role"] == "alert"


@pytest.mark.unit
def test_htmx_attrs_hx_post():
    """Textarea carries hx-post pointing to validate_url."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea["hx-post"] == "/validate/"


@pytest.mark.unit
def test_htmx_attrs_hx_trigger():
    """Textarea hx-trigger includes input changed with debounce."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert "input changed delay:500ms" in textarea["hx-trigger"]


@pytest.mark.unit
def test_htmx_attrs_hx_target():
    """Textarea hx-target points to the highlights div."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea["hx-target"] == "#id_content_highlights"


@pytest.mark.unit
def test_htmx_attrs_hx_swap():
    """Textarea hx-swap is innerHTML."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_htmx_params_none():
    """Textarea hx-params is 'none' so only manually-injected params are sent."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea["hx-params"] == "none"


@pytest.mark.unit
def test_htmx_config_request_text_param():
    """hx-on::config:request injects text=this.value."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    config = textarea["hx-on::config:request"]
    assert "event.detail.ctx.request.body.set('text', this.value)" in config


@pytest.mark.unit
def test_htmx_config_request_field_name():
    """hx-on::config:request injects field_name param."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    config = textarea["hx-on::config:request"]
    assert "event.detail.ctx.request.body.set('field_name', 'content')" in config


@pytest.mark.unit
def test_htmx_config_request_errors_id():
    """hx-on::config:request injects errors_id param."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    config = textarea["hx-on::config:request"]
    assert "event.detail.ctx.request.body.set('errors_id', 'id_content_error')" in config


@pytest.mark.unit
def test_alpine_x_data_present():
    """With validate_url, the wrapper binds to the formworkValidatedTextarea component."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper is not None
    assert wrapper["x-data"] == "formworkValidatedTextarea"


@pytest.mark.unit
def test_x_data_has_errors_false_without_errors():
    """data-has-errors initialises hasErrors to false when no aria-invalid attr is present."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper["data-has-errors"] == "false"


@pytest.mark.unit
def test_x_data_has_errors_true_with_aria_invalid():
    """data-has-errors initialises hasErrors to true when aria-invalid='true' is passed."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content", "aria-invalid": "true"})
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper["data-has-errors"] == "true"


@pytest.mark.unit
def test_scroll_sync():
    """Textarea carries a @scroll handler for synchronising the highlights div scroll."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea.has_attr("@scroll")


@pytest.mark.unit
def test_no_input_handler_clears_highlights():
    """Highlights are only updated by htmx response, not an @input handler."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert not textarea.has_attr("@input")


@pytest.mark.unit
def test_no_htmx_without_validate_url():
    """Without validate_url, no hx-post attribute is rendered."""
    widget = ValidatedTextarea()
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert not textarea.has_attr("hx-post")


@pytest.mark.unit
def test_preserves_value():
    """The submitted value appears as textarea text content."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", value="hello world", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea.string == "hello world"


@pytest.mark.unit
def test_preserves_value_in_highlights():
    """The value also appears in the highlights div for visual overlay."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", value="hello world", attrs={"id": "id_content"})
    highlights = soup.find("div", class_="validated-textarea-highlights")
    assert "hello world" in highlights.get_text()


@pytest.mark.unit
def test_preserves_attrs():
    """User attrs (e.g. rows) are forwarded to the rendered textarea."""
    widget = ValidatedTextarea(validate_url="/validate/", attrs={"rows": "5"})
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea["rows"] == "5"


@pytest.mark.unit
def test_wrapper_has_id():
    """The outer wrapper div has an id derived from the widget id."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    wrapper = soup.find("div", class_="validated-textarea")
    assert wrapper["id"] == "id_content_vtextarea"


@pytest.mark.unit
def test_aria_invalid_not_static_on_textarea():
    """aria-invalid is NOT a static HTML attr — it is controlled by Alpine."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert not textarea.has_attr("aria-invalid")


@pytest.mark.unit
def test_aria_invalid_alpine_binding_present():
    """Textarea has a :aria-invalid Alpine binding for reactive error styling."""
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea.has_attr(":aria-invalid")


@pytest.mark.unit
def test_textarea_has_after_swap_handler():
    """Textarea carries hx-on::after:swap to update hasErrors after htmx response.

    htmx 4 fires after:swap on the source (textarea) once all main+OOB swaps
    have completed, so the handler reads the up-to-date errors div content.
    """
    widget = ValidatedTextarea(validate_url="/validate/")
    soup = render_widget(widget, name="content", attrs={"id": "id_content"})
    textarea = soup.find("textarea")
    assert textarea.has_attr("hx-on::after:swap")
    assert "hasErrors" in textarea["hx-on::after:swap"]


# ─── Level 3: Form integration ───────────────────────────────────────────────


@pytest.mark.integration
def test_renders_via_form(renderer):
    """ValidatedTextarea renders correctly when used inside a FormworkForm."""
    form = ValidatedTextareaForm()
    soup = render_form(form, renderer=renderer)
    textarea = soup.find("textarea", attrs={"name": "content"})
    assert textarea is not None


@pytest.mark.integration
def test_form_wraps_in_fieldset(renderer):
    """Field template wraps the widget in a fieldset with a stable id."""
    form = ValidatedTextareaForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_content_field")
    assert fieldset is not None


@pytest.mark.integration
def test_form_error_state(renderer):
    """Bound form with errors renders the error tooltip."""
    form = ValidatedTextareaForm(data={"content": ""})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_content_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = ValidatedTextareaForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    textarea = soup.find("textarea", attrs={"name": "cfg-content"})
    assert textarea is not None
    assert textarea["id"] == "id_cfg-content"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────────


@pytest.mark.integration
def test_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """ValidatedTextarea produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(ValidatedTextareaForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(ValidatedTextareaForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────────


@pytest.mark.e2e
def test_renders_on_page(textarea_page):
    """ValidatedTextarea wrapper is visible on the /textarea/ page."""
    wrapper = textarea_page.locator(".validated-textarea")
    assert wrapper.is_visible()


@pytest.mark.e2e
def test_has_overlay(textarea_page):
    """A single highlights div is present on the page."""
    highlights = textarea_page.locator(".validated-textarea-highlights")
    assert highlights.count() == 1


@pytest.mark.e2e
def test_has_errors_tooltip(textarea_page):
    """An errors container inside the tooltip is present on the page."""
    tooltip = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
    assert tooltip.count() == 1


@pytest.mark.e2e
def test_clean_text_no_marks(textarea_page):
    """Clean text produces no mark elements in the highlights div."""
    textarea_page.evaluate(
        """(text) => {
        const textarea = document.querySelector('textarea[name="bio"]');
        textarea.value = text;
        const url = textarea.getAttribute('hx-post');
        const highlightsId = textarea.getAttribute('hx-target');
        const params = new URLSearchParams();
        params.append('text', text);
        params.append('field_name', 'bio');
        params.append('errors_id', textarea.id + '_error');
        fetch(url, {method: 'POST', body: params})
            .then(r => r.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString('<div>' + html + '</div>', 'text/html');
                const oob = doc.querySelector('[hx-swap-oob]');
                const errorsTarget = document.getElementById(textarea.id + '_error');
                if (oob && errorsTarget) {
                    errorsTarget.innerHTML = oob.innerHTML;
                    oob.remove();
                }
                const target = document.querySelector(highlightsId);
                const remaining = doc.body.firstChild;
                target.innerHTML = remaining.innerHTML;
            });
    }""",
        "Hello world",
    )
    textarea_page.wait_for_timeout(500)
    marks = textarea_page.locator(".validated-textarea-highlights mark")
    assert marks.count() == 0


@pytest.mark.e2e
def test_bad_text_shows_marks(textarea_page):
    """Text containing a flagged word produces a <mark> element in the highlights."""
    from playwright.sync_api import expect

    textarea_page.evaluate(
        """(text) => {
        const textarea = document.querySelector('textarea[name="bio"]');
        textarea.value = text;
        const url = textarea.getAttribute('hx-post');
        const highlightsId = textarea.getAttribute('hx-target');
        const params = new URLSearchParams();
        params.append('text', text);
        params.append('field_name', 'bio');
        params.append('errors_id', textarea.id + '_error');
        fetch(url, {method: 'POST', body: params})
            .then(r => r.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString('<div>' + html + '</div>', 'text/html');
                const oob = doc.querySelector('[hx-swap-oob]');
                const errorsTarget = document.getElementById(textarea.id + '_error');
                if (oob && errorsTarget) {
                    errorsTarget.innerHTML = oob.innerHTML;
                    oob.remove();
                }
                const target = document.querySelector(highlightsId);
                const remaining = doc.body.firstChild;
                target.innerHTML = remaining.innerHTML;
            });
    }""",
        "This has a badword in it",
    )
    textarea_page.wait_for_timeout(500)
    marks = textarea_page.locator(".validated-textarea-highlights mark")
    expect(marks).to_have_count(1, timeout=3000)
    assert marks.first.text_content() == "badword"


# ─── Level 6: E2e error flow ─────────────────────────────────────────────────


def _trigger_validation(page, text):
    """Trigger htmx validation POST via fetch (bypasses htmx debounce)."""
    page.evaluate(
        """(text) => {
        const textarea = document.querySelector('textarea[name="bio"]');
        textarea.value = text;
        const url = textarea.getAttribute('hx-post');
        const highlightsId = textarea.getAttribute('hx-target');
        const params = new URLSearchParams();
        params.append('text', text);
        params.append('field_name', 'bio');
        params.append('errors_id', textarea.id + '_error');
        fetch(url, {method: 'POST', body: params})
            .then(r => r.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString('<div>' + html + '</div>', 'text/html');
                const oob = doc.querySelector('[hx-swap-oob]');
                const errorsTarget = document.getElementById(textarea.id + '_error');
                if (oob && errorsTarget) {
                    errorsTarget.innerHTML = oob.innerHTML;
                    oob.remove();
                }
                const target = document.querySelector(highlightsId);
                const remaining = doc.body.firstChild;
                target.innerHTML = remaining.innerHTML;
            });
    }""",
        text,
    )


@pytest.mark.e2e
def test_error_messages_appear(textarea_page):
    """Multiple flagged words produce multiple error messages."""
    from playwright.sync_api import expect

    _trigger_validation(textarea_page, "badword and spam here")
    textarea_page.wait_for_timeout(500)
    errors = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
    messages = errors.locator("p")
    expect(messages).to_have_count(2, timeout=3000)


@pytest.mark.e2e
def test_errors_clear(textarea_page):
    """Error marks disappear when clean text is submitted."""
    from playwright.sync_api import expect

    _trigger_validation(textarea_page, "badword")
    textarea_page.wait_for_timeout(500)
    expect(textarea_page.locator(".validated-textarea-highlights mark")).to_have_count(1, timeout=3000)
    _trigger_validation(textarea_page, "All clean now")
    textarea_page.wait_for_timeout(500)
    expect(textarea_page.locator(".validated-textarea-highlights mark")).to_have_count(0, timeout=3000)


@pytest.mark.e2e
def test_errors_persist_while_typing(textarea_page):
    """Error messages persist while typing; only cleared by server validation response."""
    from playwright.sync_api import expect

    _trigger_validation(textarea_page, "badword")
    textarea_page.wait_for_timeout(500)
    errors = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
    expect(errors.locator("p")).to_have_count(1, timeout=3000)
    # Simulate typing — should NOT clear errors immediately
    textarea_page.evaluate("""
        const ta = document.querySelector('textarea[name="bio"]');
        ta.value = 'fixing the text';
        ta.dispatchEvent(new Event('input', {bubbles: true}));
    """)
    textarea_page.wait_for_timeout(100)
    # Errors should still be present (not cleared until server responds)
    expect(errors.locator("p")).to_have_count(1, timeout=1000)


@pytest.mark.e2e
def test_has_help_text(textarea_page):
    """Help text on the field mentions the invalid words."""
    label = textarea_page.locator("fieldset:has(textarea) .label")
    text = label.text_content()
    assert "badword" in text
    assert "spam" in text


@pytest.mark.e2e
def test_aria_invalid_clears_when_errors_resolve(textarea_page):
    """aria-invalid is set when errors appear and cleared when they resolve."""
    from playwright.sync_api import expect

    ta = textarea_page.locator('textarea[name="bio"]')

    # Type "spam" and trigger htmx validation via input event.
    textarea_page.evaluate("""
        const ta = document.querySelector('textarea[name="bio"]');
        ta.value = 'spam';
        ta.dispatchEvent(new Event('input', {bubbles: true}));
    """)
    # Wait for htmx debounce (500ms) + round trip + settle.
    textarea_page.wait_for_timeout(1500)

    # Errors should be visible and aria-invalid="true" set on textarea.
    errors = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
    expect(errors.locator("p")).to_have_count(1, timeout=3000)
    expect(ta).to_have_attribute("aria-invalid", "true")

    # Clear the textarea and trigger validation again.
    textarea_page.evaluate("""
        const ta = document.querySelector('textarea[name="bio"]');
        ta.value = '';
        ta.dispatchEvent(new Event('input', {bubbles: true}));
    """)
    # Wait for htmx debounce (500ms) + round trip + settle.
    textarea_page.wait_for_timeout(1500)

    # Errors should be gone and aria-invalid="false" on textarea.
    expect(errors.locator("p")).to_have_count(0, timeout=3000)
    expect(ta).to_have_attribute("aria-invalid", "false")


# ─── Level 7: E2e morph resilience ───────────────────────────────────────────


@pytest.mark.e2e
def test_morph_preserves_value(textarea_page):
    """Typed content is preserved across an htmx form morph."""
    from tests.e2e.conftest import submit

    ta = textarea_page.locator('textarea[name="bio"]')
    ta.fill("Some bio text")
    submit(textarea_page)
    assert ta.input_value() == "Some bio text"


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────────
#
# Scaffolding only — these tests produce PNG artifacts in `test-results/`
# for manual review.  True baseline comparison requires a visual-regression
# plugin (e.g. `pytest-playwright-visual`) as a follow-up.


@pytest.mark.screenshot
def test_screenshot_default(textarea_page, assert_screenshot):
    """Visual snapshot: ValidatedTextarea in default (empty) state."""
    wrapper = textarea_page.locator(".validated-textarea").first
    assert_screenshot(wrapper, "validated-textarea-default.png")


@pytest.mark.screenshot
def test_screenshot_with_content(textarea_page, assert_screenshot):
    """Visual snapshot: ValidatedTextarea after typing clean content."""
    textarea_page.locator('textarea[name="bio"]').fill("Some clean text here.")
    wrapper = textarea_page.locator(".validated-textarea").first
    assert_screenshot(wrapper, "validated-textarea-with-content.png")


@pytest.mark.screenshot
def test_screenshot_with_error_highlights(textarea_page, assert_screenshot):
    """Visual snapshot: ValidatedTextarea showing error highlights."""
    from playwright.sync_api import expect

    _trigger_validation(textarea_page, "badword and spam here")
    textarea_page.wait_for_timeout(500)
    expect(textarea_page.locator(".validated-textarea-highlights mark")).to_have_count(2, timeout=3000)
    wrapper = textarea_page.locator(".validated-textarea").first
    assert_screenshot(wrapper, "validated-textarea-with-error-highlights.png")
