frappe.provide("frappe.ui");

/**
 * @typedef {Object} StepperStep
 * @property {string} label Step name (pre-translated). Rendered as text. The state icon is generic (circle-check when completed, circle-dashed otherwise) — steps carry no icon of their own.
 *
 * @typedef {Object} StepperOpts
 * @property {StepperStep[]} steps
 * @property {number} [current=0] Index of the active step.
 * @property {string} [label] Accessible name for the nav. Defaults to "Steps".
 * @property {(index: number) => boolean} [is_locked] Steps the user can't jump to right now. Re-checked on every render.
 * @property {(index: number) => boolean} [is_completed] What "done" means for this flow. Without it, completion is positional (every step before the current one) — which forgets history when the user navigates back; pass this when completion is a fact (saved, imported…) so revisited flows keep their checks. The active step gets data-completed="true" alongside data-state="active" when both are true.
 * @property {(index: number) => void} [on_step_click] Fires when an unlocked, non-active step is clicked. Navigation stays the caller's job — call set_current when the move is accepted.
 * @property {(index: number) => void} [on_locked_click] Fires when a locked step is clicked — for "finish the earlier steps first" feedback. Without it, locked clicks are silently swallowed.
 * @property {boolean} [compact] Render a one-line progress summary (segmented bar + "Step x of y") instead of the step chips — for narrow layouts. Mount a compact and a full instance and toggle visibility at your breakpoint.
 * @property {string} [css_class] Extra classes on the nav.
 */

/**
 * The step header for multi-step flows — markers, connectors and labels with
 * active / completed / locked states. An espresso original (frappe-ui has no
 * stepper); the CSS contract lives in components/stepper.css.
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

	/** Advance one step (clamped at the end). Locks are not consulted —
	 * the owner calls this after its own validation passes. */
	next_step() {
		this.set_current(this.current + 1);
	}

	/** Go back one step (clamped at the start). */
	prev_step() {
		this.set_current(this.current - 1);
	}

	/** Re-evaluate is_locked without moving — for when the flow's rules change. */
	refresh() {
		this.render();
	}

	render() {
		// owners tend to re-render on every state poll (the DI wizard does, per
		// realtime progress tick) — skip when nothing visible would change.
		// Building the key queries is_locked, so lock flips bust the memo.
		// completion is a fact when the owner says so, positional otherwise
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

		// a rebuild destroys the focused button — put focus back on the same
		// step so keyboard users aren't dumped to <body>
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
			// revisiting a finished step: both facts ride on the element so CSS
			// can show "done, and you're here"
			if (is_done) button.setAttribute("data-completed", "true");
			// aria-disabled, not disabled: locked steps stay in the tab order so
			// the whole flow is discoverable; the click guard does the blocking
			if (locked) button.setAttribute("aria-disabled", "true");

			const marker = document.createElement("span");
			marker.className = "es-stepper__marker";
			// generic state icons: done = bare check on the filled disc, EXCEPT
			// the step being revisited, whose disc shows a dot ("you are here"
			// on a finished step); active-in-progress = dashed circle with the
			// dot, upcoming/locked = plain dash
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

	// one-line summary for narrow layouts: the progress interval form gives
	// one segment per step, the label/hint row gives name + "Step x of y"
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
 * Function form: returns the element, instance on `.data("es-stepper")`.
 * @param {StepperOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.stepper = (opts) => new frappe.ui.Stepper(opts).$el;

export default frappe.ui.stepper;
