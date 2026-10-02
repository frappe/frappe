import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ProgressOpts
 * @property {number} [value=0] Progress from 0 to 100.
 * @property {"sm"|"md"|"lg"|"xl"} [size="sm"] Bar thickness (2/4/8/12px).
 * @property {string} [label] Text above the bar. Rendered as text, never HTML; also becomes the bar's accessible name.
 * @property {boolean|function} [hint] Right-aligned value text. `true` shows "30%"; a function gets the value and returns the text (text only).
 * @property {boolean} [intervals=false] Segmented bar instead of a continuous fill.
 * @property {number} [interval_count=6] How many segments.
 * @property {string} [css_class] Extra classes on the root.
 */

const SIZES = ["sm", "md", "lg", "xl"];
let id_counter = 0;

/**
 * A linear progress bar — data imports, bulk actions, onboarding,
 * backups. Continuous by default; `intervals` renders discrete segments
 * (a stepper feel) instead. Call set_value() as work progresses — the
 * fill, the hint text and the aria value all follow.
 * @example
 * const progress = new frappe.ui.Progress({ label: __("Importing"), hint: true });
 * area.append(progress.$el);
 * frappe.realtime.on("import_progress", (data) => progress.set_value(data.percent));
 */
frappe.ui.Progress = class Progress {
	/** @param {ProgressOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.size = validated(opts.size, SIZES, "size", "Progress") || "sm";
		this.intervals = !!opts.intervals;
		this.interval_count = opts.interval_count || 6;

		this.el = document.createElement("div");
		this.el.className = ["es-progress", opts.css_class].filter(Boolean).join(" ");

		if (opts.label || opts.hint) {
			const header = document.createElement("div");
			header.className = "es-progress__header";
			if (opts.label) {
				this.label_el = document.createElement("span");
				this.label_el.className = "es-progress__label";
				this.label_el.id = `es-progress-label-${++id_counter}`;
				this.label_el.textContent = opts.label;
				header.appendChild(this.label_el);
			}
			if (opts.hint) {
				this.hint_el = document.createElement("span");
				this.hint_el.className = "es-progress__hint";
				header.appendChild(this.hint_el);
			}
			this.el.appendChild(header);
		}

		this.track = document.createElement("div");
		this.track.className = "es-progress__track";
		this.track.setAttribute("role", "progressbar");
		this.track.setAttribute("aria-valuemin", "0");
		this.track.setAttribute("aria-valuemax", "100");
		if (this.label_el) this.track.setAttribute("aria-labelledby", this.label_el.id);
		if (this.size !== "sm") this.track.setAttribute("data-size", this.size);
		this.el.appendChild(this.track);

		if (this.intervals) {
			this.track.setAttribute("data-intervals", "");
			this.segments = [];
			for (let i = 0; i < this.interval_count; i++) {
				const segment = document.createElement("div");
				segment.className = "es-progress__segment";
				this.segments.push(segment);
				this.track.appendChild(segment);
			}
		} else {
			this.fill = document.createElement("div");
			this.fill.className = "es-progress__fill";
			this.track.appendChild(this.fill);
		}

		this.set_value(opts.value || 0);
		this.$el = $(this.el);
	}

	/** Move the bar. Values outside 0-100 are clamped for display. */
	set_value(value) {
		this.value = value;
		const shown = Math.min(Math.max(value, 0), 100);
		this.track.setAttribute("aria-valuenow", String(shown));

		if (this.intervals) {
			// how many segments count as done (all of them past 100)
			const filled = Math.round((shown / 100) * this.interval_count);
			this.segments.forEach((segment, i) => {
				segment.toggleAttribute("data-filled", i < filled);
			});
		} else {
			this.fill.style.width = `${shown}%`;
		}

		if (this.hint_el) {
			this.hint_el.textContent =
				typeof this.opts.hint === "function"
					? this.opts.hint(value)
					: `${Math.round(shown)}%`;
		}
	}

	get_value() {
		return this.value;
	}
};

/**
 * Convenience form: build the bar and get the element back, so it chains
 * inside append(...) calls. The instance is on `.data("es-progress")` when
 * you need set_value.
 * @param {ProgressOpts} opts
 * @returns {JQuery}
 * @example body.append(frappe.ui.progress({ label: __("Backing up"), hint: true, value: 10 }));
 */
frappe.ui.progress = function (opts = {}) {
	const progress = new frappe.ui.Progress(opts);
	progress.$el.data("es-progress", progress);
	return progress.$el;
};

/**
 * Markup-string form for templates. Static — no set_value; render with the
 * value you have.
 * @param {ProgressOpts} [opts]
 * @returns {string}
 */
frappe.ui.progress.html = function (opts = {}) {
	return new frappe.ui.Progress(opts).el.outerHTML;
};

export default frappe.ui.progress;
