/**
 * formwork.js — idiomorph morph configuration for django-formwork.
 *
 * Wraps Idiomorph.morph() to preserve Alpine.js reactive state and
 * <details> open/closed state during full-form morphing.
 *
 * Include this script on pages that use htmx morph swaps with formwork
 * forms:
 *
 *   {% load formwork %}
 *   {% formwork_js %}
 *
 * Prerequisites (loaded by the user, BEFORE this script):
 *   - htmx 2.x with the idiomorph extension, OR htmx 4.x (built-in)
 *   - Alpine.js 3.x (if using Alpine-powered widgets)
 */
(function () {
  "use strict";

  if (typeof Idiomorph === "undefined") {
    return;
  }

  var origMorph = Idiomorph.morph;

  Idiomorph.morph = function (target, newContent, config) {
    config = config || {};

    // Preserve the focused input's current value during morph.
    config.ignoreActiveValue = true;

    // Install callbacks to protect Alpine state and <details> state.
    config.callbacks = config.callbacks || {};
    var orig = config.callbacks.beforeAttributeUpdated;

    config.callbacks.beforeAttributeUpdated = function (
      attrName,
      element,
      updateType
    ) {
      // Block x-data attribute changes — prevents Alpine.js from
      // re-parsing and resetting reactive state on morph.
      if (attrName === "x-data") {
        return false;
      }

      // Block open attribute changes on <details> — preserves
      // dropdown open/closed state across morphs.
      if (attrName === "open" && element.tagName === "DETAILS") {
        return false;
      }

      // Delegate to any previously installed callback.
      if (typeof orig === "function") {
        return orig(attrName, element, updateType);
      }
    };

    return origMorph.call(this, target, newContent, config);
  };
})();
