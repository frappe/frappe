frappe.provide("frappe.ui");

/**
 * @typedef {Object} StepperStep
 * @property {string} label Translated step name.
 * @property {string|Element|JQuery|((index:number)=>string|Element|JQuery)} [content] Shown beside the marker line in the vertical layout; a string shows as text. Built when the steps render: on creation and whenever the current step or a step's state changes.
 *
 * @typedef {Object} StepperOpts
 * @property {StepperStep[]} steps
 * @property {number} [current=0] Index of the active step.
 * @property {string} [label] Accessible name for the nav. Defaults to "Steps".
 * @property {(index:number)=>boolean} [is_locked] Steps that can't be jumped to yet; checked on every render.
 * @property {(index:number)=>boolean} [is_completed] Marks a step done. Without it, every step before the current one counts as done.
 * @property {(index:number)=>void} [on_step_click] Called for an unlocked step; call set_current to move.
 * @property {(index:number)=>void} [on_locked_click] Called for a locked step; ignored if not given.
 * @property {boolean} [compact] Show a progress bar with "Step x of y" instead of the steps, for narrow layouts. Horizontal only.
 * @property {"horizontal"|"vertical"} [orientation="horizontal"] Vertical stacks the steps, each with its content, for a checklist that stays open.
 * @property {"right"|"left"|"top"|"bottom"} [label_position="right"] Where each label sits relative to its marker. Horizontal only.
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
 *
 * @example
 * frappe.ui.stepper({
 *   orientation: "vertical",
 *   steps: [{ label: __("Accounts"), content: $accounts_actions }, { label: __("Go Live") }],
 * });
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
		this.vertical = opts.orientation === "vertical";
		this.compact = Boolean(opts.compact) && !this.vertical;

		this.nav = document.createElement("nav");
		this.nav.className = [
			"es-stepper",
			this.vertical && "es-stepper--vertical",
			opts.css_class,
		]
			.filter(Boolean)
			.join(" ");
		const label_position =
			!this.vertical && ["bottom", "top", "left"].includes(opts.label_position)
				? opts.label_position
				: "right";
		if (label_position !== "right") {
			this.nav.classList.add(`es-stepper--label-${label_position}`);
		}
		if (label_position === "bottom" || label_position === "top") {
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
		const focused =
			document.activeElement && this.nav.contains(document.activeElement)
				? document.activeElement
				: null;
		const had_focus = focused
			? Array.from(this.nav.querySelectorAll(".es-stepper__step")).indexOf(
					focused.closest(".es-stepper__step")
			  )
			: -1;

		this.nav.textContent = "";

		if (this.compact) {
			this.render_compact();
			return;
		}

		// vertical steps are an ordered list, so assistive tech announces their count and order
		const list = this.vertical && document.createElement("ol");
		if (list) {
			list.className = "es-stepper__list";
			this.nav.appendChild(list);
		}

		this.steps.forEach((step, index) => {
			const step_el = this.make_step(step, index, done);
			if (list) {
				list.appendChild(this.make_item(step, index, step_el, done));
				return;
			}
			if (index > 0) {
				this.nav.appendChild(this.make_connector(done(index - 1)));
			}
			this.nav.appendChild(step_el);
		});

		// content nodes are reused, so a control inside one gets its focus back
		if (focused && this.nav.contains(focused)) {
			focused.focus({ preventScroll: true });
		} else if (had_focus > -1) {
			const target = this.nav.querySelectorAll(".es-stepper__step")[had_focus];
			target && target.focus({ preventScroll: true });
		}
	}

	make_step(step, index, done) {
		const locked = Boolean(this.is_locked && index !== this.current && this.is_locked(index));
		const is_done = done(index);
		const state =
			index === this.current ? "active" : is_done ? "completed" : locked ? "locked" : null;

		// a step nothing can click is text, so keyboard users get no dead tab stop
		const clickable = Boolean(this.on_step_click || this.on_locked_click);
		const step_el = document.createElement(clickable ? "button" : "div");
		if (clickable) step_el.type = "button";
		step_el.className = "es-stepper__step";
		if (state) step_el.setAttribute("data-state", state);
		if (state === "active") step_el.setAttribute("aria-current", "step");
		// Separate from data-state so a revisited done step can also be active.
		if (is_done) step_el.setAttribute("data-completed", "true");
		// Not `disabled`, so locked steps stay in the tab order; the click guard blocks.
		if (locked) step_el.setAttribute("aria-disabled", "true");

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
		step_el.appendChild(marker);

		const label = document.createElement("span");
		label.className = "es-stepper__label";
		label.textContent = step.label;
		step_el.appendChild(label);
		// Full label on hover, since long ones get cut off.
		step_el.title = step.label;

		if (clickable) {
			step_el.addEventListener("click", () => {
				if (step_el.getAttribute("aria-disabled") === "true") {
					this.on_locked_click && this.on_locked_click(index);
					return;
				}
				if (index === this.current) return;
				this.on_step_click && this.on_step_click(index);
			});
		}

		return step_el;
	}

	make_connector(completed) {
		const connector = document.createElement("span");
		connector.className = "es-stepper__connector";
		connector.setAttribute("aria-hidden", "true");
		if (completed) {
			connector.setAttribute("data-completed", "true");
		}
		return connector;
	}

	make_item(step, index, step_el, done) {
		const item = document.createElement("li");
		item.className = "es-stepper__item";
		item.appendChild(step_el);
		if (index < this.steps.length - 1) {
			item.appendChild(this.make_connector(done(index)));
		}
		let content = typeof step.content === "function" ? step.content(index) : step.content;
		// a string stays text, like the label beside it
		if (typeof content === "string") content = content && document.createTextNode(content);
		if (content && $(content).length) {
			const body = document.createElement("div");
			body.className = "es-stepper__content";
			$(body).append(content);
			item.appendChild(body);
		}
		return item;
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
