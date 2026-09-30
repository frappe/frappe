frappe.provide("frappe.ui");

/**
 * @typedef {Object} StepperStep
 * @property {string} label Translated step name.
 *
 * @typedef {Object} StepperOpts
 * @property {StepperStep[]} steps
 * @property {number} [current=0] Index of the active step.
 * @property {string} [label] Accessible name for the nav. Defaults to "Steps".
 * @property {(index:number)=>boolean} [is_locked] Steps that can't be jumped to yet; checked on every render.
 * @property {(index:number)=>boolean} [is_completed] Marks a step done. Without it, every step before the current one counts as done.
 * @property {(index:number)=>void} [on_step_click] Called for an unlocked step; call set_current to move.
 * @property {(index:number)=>void} [on_locked_click] Called for a locked step; ignored if not given.
 * @property {boolean} [compact] Show a progress bar with "Step x of y" instead of the steps, for narrow layouts.
 * @property {boolean} [label_below] Put each label under its marker instead of beside it.
 * @property {string} [css_class] Extra classes on the nav.
 */

/**
 * Step header for multi-step flows. Styles are in espresso/components/stepper.css.
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
		this.is_completed = opts.is_completed || null;
		this.on_step_click = opts.on_step_click || null;
		this.on_locked_click = opts.on_locked_click || null;
		this.compact = Boolean(opts.compact);

		this.nav = document.createElement("nav");
		this.nav.className = ["es-stepper", opts.css_class].filter(Boolean).join(" ");
		this.nav.classList.toggle("es-stepper--label-below", Boolean(opts.label_below));
		if (opts.label_below) {
			// Caps each label at its share of the row.
			this.nav.style.setProperty("--es-stepper-steps", this.steps.length);
		}
		this.nav.setAttribute("aria-label", opts.label || __("Steps"));

		this.$el = $(this.nav);
		this.$el.data("es-stepper", this);
		this.render();
	}

	/** Make a step active and re-render. */
	set_current(index) {
		this.current = Math.max(0, Math.min(index, this.steps.length - 1));
		this.render();
	}

	/** Move forward one step. Locks are not checked; validate before calling. */
	next_step() {
		this.set_current(this.current + 1);
	}

	/** Move back one step. */
	prev_step() {
		this.set_current(this.current - 1);
	}

	/** Re-check is_locked and is_completed without moving. */
	refresh() {
		this.render();
	}

	render() {
		// Owners re-render often, so skip the rebuild when nothing changed.
		const done = (index) =>
			this.is_completed ? Boolean(this.is_completed(index)) : index < this.current;
		const render_key = [
			this.compact ? "compact" : "full",
			this.current,
			...this.steps.map(
				(step, index) =>
					`${step.label}:${Number(done(index))}:${
						this.is_locked && index !== this.current
							? Number(Boolean(this.is_locked(index)))
							: 0
					}`
			),
		].join("|");
		if (render_key === this._render_key) return;
		this._render_key = render_key;

		// A rebuild drops focus, so restore it to the same step for keyboard users.
		const had_focus =
			document.activeElement && this.nav.contains(document.activeElement)
				? Array.from(this.nav.querySelectorAll(".es-stepper__step")).indexOf(
						document.activeElement.closest(".es-stepper__step")
				  )
				: -1;

		this.nav.textContent = "";

		if (this.compact) {
			this.render_compact();
			return;
		}

		this.steps.forEach((step, index) => {
			if (index > 0) {
				const connector = document.createElement("span");
				connector.className = "es-stepper__connector";
				connector.setAttribute("aria-hidden", "true");
				if (done(index - 1)) {
					connector.setAttribute("data-completed", "true");
				}
				this.nav.appendChild(connector);
			}

			const locked = Boolean(
				this.is_locked && index !== this.current && this.is_locked(index)
			);
			const is_done = done(index);
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
			// Separate from data-state so a revisited done step can also be active.
			if (is_done) button.setAttribute("data-completed", "true");
			// Not `disabled`, so locked steps stay in the tab order; the click guard blocks.
			if (locked) button.setAttribute("aria-disabled", "true");

			const marker = document.createElement("span");
			marker.className = "es-stepper__marker";
			const icon_name = is_done
				? state === "active"
					? "dot"
					: "check"
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
				if (button.getAttribute("aria-disabled") === "true") {
					this.on_locked_click && this.on_locked_click(index);
					return;
				}
				if (index === this.current) return;
				this.on_step_click && this.on_step_click(index);
			});

			this.nav.appendChild(button);
		});

		if (had_focus > -1) {
			const target = this.nav.querySelectorAll(".es-stepper__step")[had_focus];
			target && target.focus({ preventScroll: true });
		}
	}

	render_compact() {
		const done = this.current + 1;
		const count = this.steps.length;
		$(this.nav).append(
			frappe.ui.progress({
				label: this.steps[this.current]?.label || "",
				hint: () => __("Step {0} of {1}", [done, count]),
				intervals: true,
				interval_count: count,
				size: "md",
				value: count ? (done / count) * 100 : 0,
			})
		);
	}
};

/**
 * Returns the element; the instance is on `.data("es-stepper")`.
 * @param {StepperOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.stepper = (opts) => new frappe.ui.Stepper(opts).$el;

export default frappe.ui.stepper;
