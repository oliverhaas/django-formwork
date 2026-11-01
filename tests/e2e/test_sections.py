"""E2e tests for section forms (``formwork/sections.js``).

Two forms save one ``SectionRecord`` through one request queue; a tab
outside them replaces both.
"""

import re
from contextlib import contextmanager

from e2e.models import SectionRecord
from playwright.sync_api import expect

REQUESTING = re.compile(r"\bhtmx-request\b")


@contextmanager
def _swapped(page, form):
    """Wait for the swap of the save that the block triggers."""
    page.evaluate(
        """(form) => {
            window.__fwSwapped = false;
            document.querySelector(form)
                .addEventListener('htmx:after:swap', () => { window.__fwSwapped = true; }, {once: true});
        }""",
        form,
    )
    yield
    page.wait_for_function("window.__fwSwapped === true")


def _pick_city(page, value):
    page.locator("summary#id_city").click()
    panel = page.locator("#id_city_wrapper [x-ref=panel]")
    expect(panel).to_be_visible()
    panel.locator(f'button[data-value="{value}"]').click()


def _hold_the_first_save(page):
    held = []

    def hold(route):
        if route.request.method == "POST" and not held:
            held.append(route)
        else:
            route.continue_()

    page.route("**/sections/**", hold)
    return held


def test_a_change_made_while_a_save_is_held_is_kept_and_saved(sections_page):
    page = sections_page
    held = _hold_the_first_save(page)
    page.evaluate(
        """() => document.querySelector('#general_form').addEventListener('htmx:after:swap', () => {
            window.__nameAfterFirstSave = document.querySelector('#id_name').value;
        }, {once: true})""",
    )

    name = page.locator("#id_name")
    with page.expect_request(lambda request: request.method == "POST"):
        name.fill("Desk")
        name.blur()
    name.fill("Chair")
    name.blur()
    with page.expect_response(lambda response: "name=Chair" in (response.request.post_data or "")):
        held[0].continue_()

    assert page.evaluate("window.__nameAfterFirstSave") == "Chair"
    expect(name).to_have_attribute("value", "Chair")
    assert SectionRecord.objects.get().name == "Chair"


def test_a_tab_opened_while_saves_are_pending_opens_after_them(sections_page):
    page = sections_page
    held = _hold_the_first_save(page)
    sent = []
    page.on("request", lambda request: sent.append(request.method) if "/sections/" in request.url else None)

    with page.expect_request(lambda request: request.method == "POST"):
        _pick_city(page, "ldn")
    page.locator("#id_name").fill("Desk")
    page.locator("#second_tab_button").click()
    with page.expect_response(lambda response: "tab=2" in response.url):
        held[0].continue_()

    expect(page.locator("#second_tab")).to_be_attached()
    assert sent == ["POST", "POST", "GET"]
    record = SectionRecord.objects.get()
    assert (record.name, record.city) == ("Desk", "ldn")


def test_enter_saves_a_text_input(sections_page):
    page = sections_page
    name = page.locator("#id_name")
    name.fill("Desk")

    with page.expect_response(lambda response: response.request.method == "POST") as response_info:
        name.press("Enter")

    assert response_info.value.request.headers.get("hx-request") == "true"
    expect(name).not_to_be_focused()
    assert SectionRecord.objects.get().name == "Desk"


def test_send_changed_posts_only_the_changed_fields(sections_page):
    page = sections_page
    note = page.locator("#id_note")

    with _swapped(page, "#extras_form"), page.expect_request(lambda request: request.method == "POST") as request_info:
        note.fill("Fragile")
        note.blur()

    posted = request_info.value.post_data
    assert "note=Fragile" in posted
    assert "_formwork_section=extras" in posted
    assert "csrfmiddlewaretoken=" in posted
    assert "color=" not in posted
    expect(page.locator("#id_color")).to_have_attribute("value", "red")
    record = SectionRecord.objects.get()
    assert (record.note, record.color) == ("Fragile", "red")


def test_a_save_started_inside_an_indicator_field_shows_the_indicator(sections_page):
    page = sections_page
    held = _hold_the_first_save(page)
    indicator = page.locator("#extras_indicator")
    note = page.locator("#id_note")

    with page.expect_request(lambda request: request.method == "POST"):
        note.fill("Fragile")
        note.blur()
    expect(indicator).to_have_class(REQUESTING)

    with _swapped(page, "#extras_form"):
        held[0].continue_()
    expect(indicator).not_to_have_class(REQUESTING)
