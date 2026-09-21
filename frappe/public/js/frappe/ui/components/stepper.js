frappe.provide("frappe.ui");

/**
 * @typedef {Object} StepperStep
 * @property {string} label Step name (pre-translated). Rendered as text.
 *
 * @typedef {Object} StepperOpts
 * @property {StepperStep[]} steps
 * @property {number} [current=0] Index of the active step.
 * @property {string} [label] Accessible name for the nav. Defaults to "Steps".
 * @property {(index: number) => boolean} [is_locked] Steps the user can't jump to right now. Re-checked on every render.
 * @property {(index: number) => void} [on_step_click] Fires when an unlocked, non-active step is clicked. Navigation stays the caller's job — call set_current when the move is accepted.
 * @property {string} [css_class] Extra classes on the nav.
 */

/**
 * The step header for multi-step flows — markers, connectors and labels with
 * active / completed / locked states. The CSS contract lives in components/stepper.css.
 *
 * @example
 * const stepper = new frappe.ui.Stepper({
 *   steps: [{ label: __("Config") }, { label: __("Import") }],
 *   on_step_click: (i) => stepper.set_current(i),
 * });
 * $(".wizard-head").append(stepper.$el);
 */
frappe.ui.Stepper = class Stepper {
	/** @param {StepperOpts} opts */
	constructor(opts = {}) {
		this.steps = opts.steps || [];
		this.current = opts.current || 0;
		this.is_locked = opts.is_locked || null;
		this.on_step_click = opts.on_step_click || null;

		this.nav = document.createElement("nav");
		this.nav.className = ["es-stepper", opts.css_class].filter(Boolean).join(" ");
		this.nav.setAttribute("aria-label", opts.label || __("Steps"));

		this.$el = $(this.nav);
		this.$el.data("es-stepper", this);
		this.render();
	}

	/** Move the active step and repaint states, connectors and markers. */
	set_current(index) {
		this.current = Math.max(0, Math.min(index, this.steps.length - 1));
		this.render();
	}

	/** Re-evaluate is_locked without moving — for when the flow's rules change. */
	refresh() {
		this.render();
	}

	locked(index) {
		return Boolean(this.is_locked && index !== this.current && this.is_locked(index));
	}

	render() {
		const render_key = [
			this.current,
			...this.steps.map((step, index) => `${step.label}:${Number(this.locked(index))}`),
		].join("|");
		if (render_key === this._render_key) return;
		this._render_key = render_key;

		// a rebuild destroys the focused button — put focus back on the same
		// step so keyboard users aren't dumped to <body>
		const had_focus =
			document.activeElement && this.nav.contains(document.activeElement)
				? Array.from(this.nav.querySelectorAll(".es-stepper__step")).indexOf(
						document.activeElement.closest(".es-stepper__step")
				  )
				: -1;

		this.nav.textContent = "";

		this.steps.forEach((step, index) => {
			if (index > 0) {
				const connector = document.createElement("span");
				connector.className = "es-stepper__connector";
				connector.setAttribute("aria-hidden", "true");
				if (index - 1 < this.current) {
					connector.setAttribute("data-completed", "true");
				}
				this.nav.appendChild(connector);
			}

			const locked = this.locked(index);
			const is_done = index < this.current;
			const state =
				index === this.current
					? "active"
					: is_done
					? "completed"
					: locked
					? "locked"
					: null;

			const button = document.createElement("button");
			button.type = "button";
			button.className = "es-stepper__step";
			if (state) button.setAttribute("data-state", state);
			if (state === "active") button.setAttribute("aria-current", "step");
			if (is_done) button.setAttribute("data-completed", "true");
			// aria-disabled, not disabled: locked steps stay in the tab order so
			// the whole flow is discoverable; the click guard does the blocking
			if (locked) button.setAttribute("aria-disabled", "true");

			const marker = document.createElement("span");
			marker.className = "es-stepper__marker";
			const icon_name = is_done
				? "check"
				: state === "active"
				? "circle-dot-dashed"
				: "circle-dashed";
			marker.innerHTML = frappe.utils.icon(icon_name, "sm", "", "", "", true);
			button.appendChild(marker);

			const label = document.createElement("span");
			label.className = "es-stepper__label";
			label.textContent = step.label;
			button.appendChild(label);

			button.addEventListener("click", () => {
				if (locked || index === this.current) return;
				this.on_step_click && this.on_step_click(index);
			});

			this.nav.appendChild(button);
		});

		if (had_focus > -1) {
			const target = this.nav.querySelectorAll(".es-stepper__step")[had_focus];
			target && target.focus({ preventScroll: true });
		}
	}
};

/**
 * Function form: returns the element, instance on `.data("es-stepper")`.
 * @param {StepperOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.stepper = (opts) => new frappe.ui.Stepper(opts).$el;

export default frappe.ui.stepper;
