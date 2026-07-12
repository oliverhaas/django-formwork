/**
 * formwork.js — formwork bundle.
 *
 * Aggregator that imports the page-global core (morph, dirty-tracking,
 * native-validation disabling) plus each widget's Alpine.data
 * component module.  Load via {% formwork_js %} or import directly
 * from a JS bundler entry (vite, esbuild, webpack, etc.).
 *
 * Three loading paths:
 *
 *   1. {% formwork_js %} — this file as <script type="module">.
 *      One request, everything loaded.
 *
 *   2. {% formwork_core_js %} + {{ form.media }} — page-global core
 *      from formwork-core.js, per-widget JS via Django's Media class.
 *      Two tags but only the JS the form actually uses is loaded.
 *
 *   3. Bundler import — `import "django-formwork/formwork.js"` from a
 *      JS bundler entry.  The bundler resolves the chain and emits a
 *      single bundle.  No {% formwork_js %} / {{ form.media }} needed.
 *
 * ES module URL deduplication makes the paths safely composable: if you
 * accidentally load both `{% formwork_js %}` and `{% formwork_core_js %}`,
 * the core only executes once.
 *
 * Prerequisites (loaded by the user, BEFORE this script):
 *   - htmx 4.x
 *   - Alpine.js 3.x (if using Alpine-powered widgets)
 */

import "./formwork-core.js";
import "./widgets/search_select.js";
import "./widgets/multi_select.js";
import "./widgets/combo_box.js";
import "./widgets/date_picker.js";
import "./widgets/drop_zone.js";
import "./widgets/image_upload.js";
import "./widgets/input_mask.js";
import "./widgets/input_number.js";
import "./widgets/otp_input.js";
import "./widgets/password_reveal.js";
import "./widgets/validated_textarea.js";
