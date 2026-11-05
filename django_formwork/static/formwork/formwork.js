/**
 * formwork.js: the formwork bundle.
 *
 * Aggregator that imports the page-global core (morph, dirty-tracking,
 * native-validation disabling) plus each widget's Alpine.data
 * component module.  Load via {% formwork_js %} or import directly
 * from a JS bundler entry (vite, esbuild, webpack, etc.).
 *
 * Three loading paths:
 *
 *   1. {% formwork_js %}: this file as <script type="module">.
 *      One request, everything loaded.
 *
 *   2. {% formwork_core_js %} + {{ form.media }}: the page-global core
 *      from formwork-core.js, per-widget JS via Django's Media class.
 *      Two tags but only the JS the form actually uses is loaded.
 *
 *   3. Bundler import: import this file by its path in the installed
 *      package (django_formwork/static/formwork/formwork.js) from a JS
 *      bundler entry.  The package is not published to npm.  The bundler
 *      resolves the chain and emits a single bundle, so the page needs
 *      no {% formwork_js %} or {{ form.media }}.
 *
 * A browser runs an ES module once per URL, so the paths can be combined:
 * a page that loads both `{% formwork_js %}` and `{% formwork_core_js %}`
 * runs the core once.
 *
 * Prerequisites (loaded by the user, BEFORE this script):
 *   - htmx 4.x
 *   - htmx's alpine-compat extension (`dist/ext/hx-alpine-compat.js`),
 *     after htmx
 *
 * Alpine.js 3.x loads after this script, with `defer`. Module and defer
 * scripts run in document order, so the `alpine:init` listeners exist
 * when Alpine starts.
 */

import "./formwork-core.js";
import "./widgets/select.js";
import "./widgets/select_multiple.js";
import "./widgets/combo_box.js";
import "./widgets/date_picker.js";
import "./widgets/file_dropzone.js";
import "./widgets/image_dropzone.js";
import "./widgets/input_mask.js";
import "./widgets/password_input.js";
import "./widgets/search_input.js";
import "./widgets/stepper_number.js";
import "./widgets/validated_textarea.js";
