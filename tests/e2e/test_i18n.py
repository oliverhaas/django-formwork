"""E2e tests for a translated page: the client-side counts use the plural forms the server sends."""

from playwright.sync_api import expect


def test_select_multiple_count_stays_translated_when_the_selection_changes(translated_page):
    text = translated_page.locator("summary#id_colors [x-html]")
    expect(text).to_have_text("⟦4 selected⟧")
    translated_page.locator("summary#id_colors").click()
    translated_page.locator('#id_colors_wrapper input[value="black"]').dispatch_event("click")
    expect(text).to_have_text("Red, Green, Blue")
    translated_page.locator('#id_colors_wrapper input[value="white"]').dispatch_event("click")
    expect(text).to_have_text("⟦4 selected⟧")


def test_file_dropzone_count_and_size_are_translated(translated_page):
    inp = translated_page.locator('input[name="files"]')
    zone = translated_page.locator("#id_files_dropzone")
    inp.set_input_files(
        [
            {"name": "a.txt", "mimeType": "text/plain", "buffer": b"a"},
            {"name": "b.txt", "mimeType": "text/plain", "buffer": b"b"},
        ],
    )
    expect(zone.locator(".dropzone-file-name")).to_have_text("⟦2 files selected⟧")
    inp.set_input_files([{"name": "c.txt", "mimeType": "text/plain", "buffer": b"c" * 1536}])
    expect(zone.locator(".dropzone-file-size")).to_have_text("1,5 KB")
