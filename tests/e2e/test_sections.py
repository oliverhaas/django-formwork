"""E2e tests for several forms on one page that each save their own fields of one row.

Each form posts itself on change or submit and morphs its answer in. Both share one
``body:queue all`` queue, and a tab outside them replaces both.
"""

from e2e.models import SectionRecord
from playwright.sync_api import expect


def _is_post(request):
    return request.method == "POST"


def _hold_the_first_save(page):
    held = []

    def hold(route):
        if route.request.method == "POST" and not held:
            held.append(route)
        else:
            route.continue_()

    page.route("**/sections/**", hold)
    return held


def _edit(page, selector, value):
    field = page.locator(selector)
    field.fill(value)
    field.blur()


def _pick_city(page, value):
    page.locator("summary#id_city").click()
    panel = page.locator("#id_city_wrapper [x-ref=panel]")
    expect(panel).to_be_visible()
    panel.locator(f'button[data-value="{value}"]').click()


def test_a_change_made_while_a_save_is_held_is_kept_and_saved(sections_page):
    page = sections_page
    held = _hold_the_first_save(page)
    page.evaluate(
        """() => document.querySelector('#general_form').addEventListener('htmx:after:swap', () => {
            window.__nameAfterFirstSave = document.querySelector('#id_name').value;
        }, {once: true})""",
    )

    with page.expect_request(_is_post):
        _edit(page, "#id_name", "Desk")
    _edit(page, "#id_name", "Chair")
    with page.expect_response(lambda response: "name=Chair" in (response.request.post_data or "")):
        held[0].continue_()

    assert page.evaluate("window.__nameAfterFirstSave") == "Chair"
    expect(page.locator("#id_name")).to_have_attribute("value", "Chair")
    assert SectionRecord.objects.get().name == "Chair"


def test_a_change_in_each_form_while_a_save_is_held_saves_both(sections_page):
    page = sections_page
    held = _hold_the_first_save(page)

    with page.expect_request(_is_post):
        _edit(page, "#id_name", "Desk")
    _edit(page, "#id_note", "Fragile")
    with page.expect_response(lambda response: "note=Fragile" in (response.request.post_data or "")):
        held[0].continue_()

    expect(page.locator("#id_name")).to_have_attribute("value", "Desk")
    expect(page.locator("#id_note")).to_have_attribute("value", "Fragile")
    record = SectionRecord.objects.get()
    assert (record.name, record.note) == ("Desk", "Fragile")


def test_leaving_while_a_save_waits_in_the_queue_asks_first(sections_page, live_server):
    page = sections_page
    held = _hold_the_first_save(page)
    dialogs = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog.type), dialog.dismiss()))

    with page.expect_request(_is_post):
        _edit(page, "#id_name", "Desk")
    _edit(page, "#id_note", "Fragile")
    page.locator("#leave_link").click()

    assert dialogs == ["beforeunload"]
    expect(page).to_have_url(f"{live_server.url}/sections/")

    with page.expect_response(lambda response: "note=Fragile" in (response.request.post_data or "")):
        held[0].continue_()
    page.locator("#leave_link").click()

    expect(page).to_have_url(f"{live_server.url}/basic/")
    assert dialogs == ["beforeunload"]
    record = SectionRecord.objects.get()
    assert (record.name, record.note) == ("Desk", "Fragile")


def test_a_tab_that_replaces_the_forms_leaves_their_saves_to_finish(sections_page, live_server):
    page = sections_page
    held = _hold_the_first_save(page)
    dialogs = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog.type), dialog.dismiss()))

    with page.expect_request(_is_post):
        _pick_city(page, "ldn")
    page.locator("#id_name").fill("Desk")
    page.locator("#second_tab_button").click()
    expect(page.locator("#second_tab")).to_be_attached()
    with page.expect_response(lambda response: "name=Desk" in (response.request.post_data or "")):
        held[0].continue_()

    expect(page.locator("#second_tab")).to_be_attached()
    record = SectionRecord.objects.get()
    assert (record.name, record.city) == ("Desk", "ldn")
    page.locator("#leave_link").click()
    expect(page).to_have_url(f"{live_server.url}/basic/")
    assert dialogs == []


def test_enter_in_a_form_with_one_text_field_saves_without_leaving(sections_page, live_server):
    page = sections_page
    methods = []
    page.on("request", lambda request: methods.append(request.method))
    note = page.locator("#id_note")
    note.fill("Fragile")

    with page.expect_response(lambda response: "note=Fragile" in (response.request.post_data or "")):
        note.press("Enter")

    expect(note).to_have_attribute("value", "Fragile")
    assert "GET" not in methods
    expect(page).to_have_url(f"{live_server.url}/sections/")
    assert SectionRecord.objects.get().note == "Fragile"
