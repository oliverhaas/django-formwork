// Draws Chart.js charts in the theme's colors. An element with x-data="chart" holds a Chart.js config
// as JSON in data-chart. A color in the config can name a theme color, with an opacity in percent:
// "--color-primary", "--color-base-content/25". The chart draws again when the theme or the config changes.
// JSON holds no functions, so a tooltip can list its lines per data point: options.plugins.tooltip.titles
// and .footers.
(() => {
  const TOKEN = /^--color-[a-z0-9-]+(\/\d{1,3})?$/;
  const probe = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const charts = new Set();

  // The canvas turns any CSS color, oklch() included, into the RGB that Chart.js can blend.
  function color(token) {
    const [name, alpha] = token.split("/");
    probe.clearRect(0, 0, 1, 1);
    probe.fillStyle = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    probe.fillRect(0, 0, 1, 1);
    const [r, g, b] = probe.getImageData(0, 0, 1, 1).data;
    return `rgba(${r}, ${g}, ${b}, ${alpha === undefined ? 1 : alpha / 100})`;
  }

  function resolve(value) {
    if (typeof value === "string") return TOKEN.test(value) ? color(value) : value;
    if (Array.isArray(value)) return value.map(resolve);
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolve(item)]));
    }
    return value;
  }

  function tooltipLines(config) {
    const tooltip = config.options?.plugins?.tooltip;
    for (const [list, callback] of [["titles", "title"], ["footers", "footer"]]) {
      const lines = tooltip?.[list];
      if (lines) tooltip.callbacks = { ...tooltip.callbacks, [callback]: (items) => lines[items[0].dataIndex] };
    }
    return config;
  }

  function defaults() {
    const { defaults } = window.Chart;
    defaults.color = color("--color-base-content/60");
    defaults.borderColor = color("--color-base-content/10");
    defaults.font.family = getComputedStyle(document.body).fontFamily;
    defaults.font.size = 12;
    defaults.maintainAspectRatio = false;
    // Chart.js reads the keys of this object, so it keeps the object and sets the duration in it.
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) defaults.animation = false;
    else defaults.animation.duration = 400;
    defaults.interaction.mode = "index";
    defaults.interaction.intersect = false;
    // The template has the legend, as text.
    defaults.plugins.legend.display = false;
    Object.assign(defaults.plugins.tooltip, {
      backgroundColor: color("--color-neutral"),
      titleColor: color("--color-neutral-content"),
      bodyColor: color("--color-neutral-content"),
      footerColor: color("--color-neutral-content/70"),
      footerFont: { weight: "normal" },
      padding: 10,
      cornerRadius: 6,
      boxPadding: 4,
      usePointStyle: true,
    });
    defaults.elements.bar.borderRadius = 3;
    defaults.elements.line.borderWidth = 2;
    defaults.elements.line.tension = 0.3;
    defaults.elements.point.radius = 0;
    defaults.elements.point.hoverRadius = 4;
    defaults.elements.arc.borderColor = color("--color-base-100");
    defaults.elements.arc.borderWidth = 2;
    defaults.scale.grid.drawTicks = false;
    defaults.scale.border = { display: false };
    defaults.scale.ticks.padding = 8;
  }

  // Alpine would wrap a chart kept on the component in a proxy, which Chart.js cannot draw with.
  function mount(root) {
    let chart = null;
    let drawn = null;
    const draw = () => {
      chart?.destroy();
      root.replaceChildren(document.createElement("canvas"));
      drawn = root.dataset.chart;
      defaults();
      chart = new window.Chart(root.firstChild, tooltipLines(resolve(JSON.parse(drawn))));
    };
    // A morph of the page can change the config or drop the canvas.
    const observer = new MutationObserver(() => {
      if (root.dataset.chart !== drawn || !root.firstChild) draw();
    });
    observer.observe(root, { attributes: true, attributeFilter: ["data-chart"], childList: true });
    const entry = { draw };
    charts.add(entry);
    draw();
    return () => {
      observer.disconnect();
      charts.delete(entry);
      chart?.destroy();
    };
  }

  const redraw = () => charts.forEach((entry) => entry.draw());
  new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);

  document.addEventListener("alpine:init", () => {
    window.Alpine.data("chart", () => ({
      init() {
        this.unmount = mount(this.$el);
      },
      destroy() {
        this.unmount();
      },
    }));
  });
})();
