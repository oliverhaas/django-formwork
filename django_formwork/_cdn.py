"""The htmx and Alpine.js builds that formwork loads from their CDNs, in the versions its tests run."""

_HTMX = "https://unpkg.com/htmx.org@4.0.2/dist"

#: htmx and its Alpine bridge, which a morph needs to keep what Alpine wrote.
HTMX_SCRIPTS = (f"{_HTMX}/htmx.min.js", f"{_HTMX}/ext/hx-alpine-compat.min.js")
HTMX_PRELOAD_SCRIPT = f"{_HTMX}/ext/hx-preload.min.js"
ALPINE_SCRIPT = "https://cdn.jsdelivr.net/npm/alpinejs@3.17.5/dist/cdn.min.js"
