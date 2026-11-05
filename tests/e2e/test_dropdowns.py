"""E2e tests for the behaviour Select and SelectMultiple share: placement, paging, read-only state."""

import pytest
from playwright.sync_api import expect

from django_formwork.search import SEARCH_PAGE_SIZE

CITY_COUNT = 24
VIEWPORT = {"width": 1280, "height": 520}


def _open(page, trigger_id):
    page.locator(f"summary#{trigger_id}").click()
    panel = page.locator(f"#{trigger_id}_wrapper [x-ref=panel]")
    expect(panel).to_be_visible()
    return panel


def _row_values(panel):
    return panel.locator("li[role=option] > [data-value]").evaluate_all("els => els.map(el => el.dataset.value)")


def test_select_opens_downward_when_the_list_fits_below(dropdowns_page):
    """More room above than below does not flip a list that fits below."""
    dropdowns_page.set_viewport_size(VIEWPORT)
    dropdowns_page.evaluate("""() => {
        document.body.style.paddingBlock = '100vh';
        const trigger = document.querySelector('summary#id_brand');
        window.scrollBy(0, trigger.getBoundingClientRect().top - window.innerHeight * 0.55);
    }""")
    trigger = dropdowns_page.locator("summary#id_brand").bounding_box()
    panel = _open(dropdowns_page, "id_brand").bounding_box()
    assert trigger is not None
    assert panel is not None
    above = trigger["y"]
    below = VIEWPORT["height"] - trigger["y"] - trigger["height"]
    assert above > below
    assert panel["y"] > trigger["y"] + trigger["height"]
    assert panel["y"] + panel["height"] <= VIEWPORT["height"]


def test_short_select_menu_does_not_scroll(dropdowns_page):
    """The height cap covers the border box, so three rows fit without a scrollbar."""
    panel = _open(dropdowns_page, "id_brand")
    assert panel.evaluate("el => el.scrollHeight <= el.clientHeight")


@pytest.mark.parametrize("name", ["city", "cities"])
def test_load_more_appends_the_next_page_without_repeating_the_selection(dropdowns_page, name):
    """The selection past the first page is listed once: the next page excludes it."""
    panel = _open(dropdowns_page, f"id_{name}")
    rows = panel.locator("li[role=option]")
    expect(rows).to_have_count(SEARCH_PAGE_SIZE + 1)
    panel.get_by_role("button", name="Load more").click()
    expect(rows).to_have_count(CITY_COUNT)
    expect(panel).to_be_visible()
    expect(panel.get_by_role("button", name="Load more")).to_have_count(0)
    values = _row_values(panel)
    assert len(set(values)) == len(values)


def test_attribute_search_swaps_in_rows_beyond_the_seeded_page(dropdowns_page):
    """The server search reaches rows the first page left out."""
    panel = _open(dropdowns_page, "id_city")
    rows = panel.locator("button[data-value]")
    expect(rows.filter(has_text="Singapore")).to_have_count(0)
    panel.locator("input[type=search]").fill("Singapore")
    expect(rows).to_have_count(1)
    expect(rows.filter(has_text="Singapore")).to_have_count(1)


def test_load_more_error_shows_the_alert(dropdowns_page):
    """A failed "Load more" swaps nothing and says so, like a failed search."""
    dropdowns_page.route("**offset=20**", lambda route: route.fulfill(status=500, body="boom"))
    panel = _open(dropdowns_page, "id_city")
    panel.get_by_role("button", name="Load more").click()
    expect(panel.get_by_role("alert")).to_be_visible()
    expect(panel.locator("ul[role=listbox]")).to_be_hidden()


def test_disabled_fieldset_makes_dropdowns_read_only(read_only_page):
    """A disabled fieldset reaches form controls, not the <summary> triggers: CSS and the open guard cover them."""
    for name in ("brand", "city", "cities"):
        expect(read_only_page.locator(f"summary#id_{name}")).to_have_css("pointer-events", "none")
    root = read_only_page.locator("#id_brand_wrapper")
    read_only_page.locator("summary#id_brand").focus()
    read_only_page.keyboard.press("Enter")
    read_only_page.evaluate("document.querySelector('#id_cities_wrapper').open = true")
    for wrapper in ("#id_brand_wrapper", "#id_cities_wrapper"):
        expect(read_only_page.locator(wrapper)).not_to_have_attribute("open", "")
        expect(read_only_page.locator(f"{wrapper} [x-ref=panel]")).to_be_hidden()
    assert root.evaluate("el => el.querySelector('input[type=hidden]').matches(':disabled')")


def _add_project_dropdown(page):
    """A project's own DaisyUI dropdown next to the formwork widgets."""
    page.evaluate("""() => {
        const host = document.createElement('div');
        host.innerHTML = `
            <details class="dropdown" id="project_menu" open>
                <summary>Menu</summary>
                <div class="dropdown-content"><input id="project_input"></div>
            </details>`;
        document.body.append(host);
    }""")


def test_project_dropdown_input_keeps_its_focus_ring(dropdowns_page):
    _add_project_dropdown(dropdowns_page)
    dropdowns_page.locator("#project_input").focus()
    outline = dropdowns_page.locator("#project_input").evaluate("el => getComputedStyle(el).outlineStyle")
    assert outline != "none"


def test_project_details_dropdown_gets_no_click_overlay(dropdowns_page):
    _add_project_dropdown(dropdowns_page)
    position = dropdowns_page.locator("#project_menu > summary").evaluate(
        "el => getComputedStyle(el, '::before').position",
    )
    assert position != "fixed"
