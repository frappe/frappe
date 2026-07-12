import { place, SIDES, ALIGNS } from "./position.js";
import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} HoverCardOpts
 * @property {Element|JQuery|function|string} content The card body. An element (or a function returning one, called fresh on every open) is the rich channel; a plain string renders as text, never HTML.
 * @property {"top"|"right"|"bottom"|"left"} [side="bottom"] Which side of the trigger the card opens on.
 * @property {"start"|"center"|"end"} [align="center"] How the card lines up along that side.
 * @property {number} [offset=4] Gap between trigger and card, in px.
 * @property {number} [open_delay=700] Hover time before the card shows (the radix default — long enough that passing the pointer over a list of links doesn't pop cards).
 * @property {number} [close_delay=300] Grace period after the pointer leaves, so it can travel from the trigger onto the card without it vanishing.
 * @property {string} [css_class] Extra classes on the card.
 * @property {function} [on_open]
 * @property {function} [on_close]
 */

const EXIT_MS = 100; // keep in sync with es-popover-out in popover.css (shared shell)

/**
 * A rich preview on hover — Tooltip's timing with Popover's body. Shows
 * after resting the pointer on the trigger, stays while the pointer is on
 * the trigger OR the card (so links inside are clickable), and goes away
 * shortly after leaving both. Escape dismisses it. Keyboard focus on the
 * trigger shows it too (immediately), blur hides it.
 *
 * It's a sighted-pointer enhancement, so the trigger gets NO aria state
 * (the radix hover-card stance): focus never moves into the card, and
 * whatever it previews must also be reachable the normal way — usually by
 * following the link it decorates.
 * @example
 * frappe.ui.hover_card(this.$el.find(".user-link"), {
 *     content: () => this.build_user_card(user),
 * });
 */
frappe.ui.HoverCard = class HoverCard {
	/**
	 * @param {Element|JQuery} trigger The element the card previews.
	 * @param {HoverCardOpts} opts
	 */
	constructor(trigger, opts = {}) {
		this.trigger_el = $(trigger)[0];
		if (!this.trigger_el) {
			console.warn("frappe.ui.HoverCard: trigger element not found");
			return;
		}

		this.opts = opts;
		this.side = validated(opts.side, SIDES, "side", "HoverCard") || "bottom";
		this.align = validated(opts.align, ALIGNS, "align", "HoverCard") || "center";
		this.offset = opts.offset == null ? 4 : opts.offset;
		this.open_delay = opts.open_delay == null ? 700 : opts.open_delay;
		this.close_delay = opts.close_delay == null ? 300 : opts.close_delay;

		this.panel = null;
		this.open_timer = null;
		this.close_timer = null;

		// hover cards are a pointer thing: a finger can't rest on a link, it
		// taps it — so touch goes straight to the link's normal behavior
		this.onenter = (e) => {
			if (e.pointerType === "touch") return;
			this.cancel_timers();
			if (!this.panel) {
				this.open_timer = setTimeout(() => this.open(), this.open_delay);
			}
		};
		this.onleave = () => {
			this.cancel_timers();
			// the grace period: long enough to travel onto the card
			if (this.panel) {
				this.close_timer = setTimeout(() => this.close(), this.close_delay);
			}
		};
		// keyboard focus shows it right away — the pointer delay exists to
		// filter accidental passes, and focusing a link is never accidental
		this.onfocus = () => {
			this.cancel_timers();
			this.open();
		};
		this.onblur = () => this.close();

		this.trigger_el.addEventListener("pointerenter", this.onenter);
		this.trigger_el.addEventListener("pointerleave", this.onleave);
		this.trigger_el.addEventListener("focus", this.onfocus);
		this.trigger_el.addEventListener("blur", this.onblur);
	}

	get is_open() {
		return !!this.panel;
	}

	cancel_timers() {
		clearTimeout(this.open_timer);
		clearTimeout(this.close_timer);
	}

	// Same policy as Popover: elements and element-returning functions are
	// the rich channel; strings become text nodes, never markup.
	resolve_content() {
		let content = this.opts.content;
		if (typeof content === "function") content = content(this);
		if (typeof content === "string") {
			const p = document.createElement("div");
			p.textContent = content;
			return p;
		}
		const el = content && $(content)[0];
		if (!el) {
			console.warn("frappe.ui.HoverCard: no content to show");
			return null;
		}
		return el;
	}

	open() {
		if (this.panel || !this.trigger_el.isConnected) return;
		const content = this.resolve_content();
		if (!content) return;

		// the popover shell + the hover-card modifier (see hover_card.css);
		// no role, no tabindex — focus stays where it is, this is a preview
		const panel = document.createElement("div");
		panel.className = ["es-popover es-hover-card", this.opts.css_class]
			.filter(Boolean)
			.join(" ");
		panel.appendChild(content);

		document.body.appendChild(panel);
		place(panel, this.trigger_el.getBoundingClientRect(), this.side, this.align, this.offset);
		panel.setAttribute("data-state", "open");
		this.panel = panel;

		// the pointer resting on the card counts as "still there" — that's
		// what makes links inside it clickable
		panel.addEventListener("pointerenter", this.onenter);
		panel.addEventListener("pointerleave", this.onleave);

		// Escape dismisses; focus never enters the card, so listen on the
		// document (and let the event keep bubbling — unlike a popover, the
		// card holds no focus and shouldn't swallow anyone else's Escape)
		this.onkeydown = (e) => {
			if (e.key === "Escape") this.close();
		};
		this.onreposition = () => {
			place(
				panel,
				this.trigger_el.getBoundingClientRect(),
				this.side,
				this.align,
				this.offset
			);
		};
		document.addEventListener("keydown", this.onkeydown);
		window.addEventListener("resize", this.onreposition);
		document.addEventListener("scroll", this.onreposition, { capture: true, passive: true });

		this.opts.on_open && this.opts.on_open(this);
	}

	close() {
		this.cancel_timers();
		if (!this.panel) return;
		const panel = this.panel;
		this.panel = null;

		document.removeEventListener("keydown", this.onkeydown);
		window.removeEventListener("resize", this.onreposition);
		document.removeEventListener("scroll", this.onreposition, { capture: true });

		// let the exit animation play, then drop the node
		panel.setAttribute("data-state", "closed");
		setTimeout(() => panel.remove(), EXIT_MS + 50);

		this.opts.on_close && this.opts.on_close();
	}

	destroy() {
		this.close();
		if (!this.trigger_el) return;
		this.trigger_el.removeEventListener("pointerenter", this.onenter);
		this.trigger_el.removeEventListener("pointerleave", this.onleave);
		this.trigger_el.removeEventListener("focus", this.onfocus);
		this.trigger_el.removeEventListener("blur", this.onblur);
	}
};

/**
 * Convenience form: attach a hover card and get the trigger back, so it
 * chains inside append(...) calls. The instance is on `.data("es-hover-card")`
 * when you need open/close/destroy.
 * @param {Element|JQuery} trigger
 * @param {HoverCardOpts} opts
 * @returns {JQuery}
 * @example list_row.append(frappe.ui.hover_card($user_link, {
 *     content: () => build_user_card(user),
 * }));
 */
frappe.ui.hover_card = function (trigger, opts = {}) {
	const card = new frappe.ui.HoverCard(trigger, opts);
	const $trigger = $(trigger);
	$trigger.data("es-hover-card", card);
	return $trigger;
};

export default frappe.ui.hover_card;
