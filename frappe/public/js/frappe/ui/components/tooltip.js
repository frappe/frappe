import { place, SIDES, ALIGNS } from "./position.js";
import { validated, shortcut_keys } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} TooltipOpts
 * @property {string} text The label. Rendered as text, never HTML.
 * @property {string|string[]} [shortcut] Keyboard hint after the label, one <kbd> per key — pass the raw combo ("ctrl+b") and each key becomes its OS form (⌘B on Mac), or an array of already-formatted keys. Display only; binding stays the caller's job.
 * @property {"top"|"right"|"bottom"|"left"} [side="top"] Which side of the trigger the bubble prefers.
 * @property {"start"|"center"|"end"} [align="center"] How the bubble lines up along that side.
 * @property {number} [delay=500] Hover delay in ms before showing. Focus always shows immediately.
 * @property {number} [offset=4] Gap between trigger and bubble, in px. The 4px arrow fills it, tip touching the trigger (frappe-ui's side-offset).
 */

// After any tooltip hides, the next one within this window skips the hover
// delay. Moving along a toolbar shouldn't cost 500ms per button — the first
// tooltip proves you're reading labels, the rest follow instantly (this is
// what radix's TooltipProvider does for a group; a module-level clock does
// the same job here without needing a provider).
const SKIP_DELAY_MS = 300;
let last_hidden_at = 0;

// only one tooltip on screen at a time (like radix's provider): the pointer
// can be parked on one control while the keyboard focuses another, and two
// open bubbles would fight over the reader's attention
let visible = null;

const EXIT_MS = 100; // keep in sync with es-tooltip-out in tooltip.css

let id_counter = 0;

/**
 * The small dark bubble that names a control on hover or keyboard focus —
 * the espresso replacement for bootstrap's title-tooltips.
 *
 * Shows after a short hover delay (immediately on focus), hides on leave,
 * blur, Escape, or pressing the trigger. The bubble is plain text and never
 * catches the pointer. While visible, the trigger gets aria-describedby so
 * screen readers announce the label too.
 * @example
 * frappe.ui.tooltip(this.$el.find(".nav-btn"), { text: __("Notifications") });
 */
frappe.ui.Tooltip = class Tooltip {
	/**
	 * @param {Element|JQuery} trigger The element the tooltip describes.
	 * @param {TooltipOpts} opts
	 */
	constructor(trigger, opts = {}) {
		this.trigger_el = $(trigger)[0];
		if (!this.trigger_el) {
			console.warn("frappe.ui.Tooltip: trigger element not found");
			return;
		}

		this.text = opts.text || "";
		this.shortcut = opts.shortcut || null;
		this.side = validated(opts.side, SIDES, "side", "Tooltip") || "top";
		this.align = validated(opts.align, ALIGNS, "align", "Tooltip") || "center";
		this.delay = opts.delay == null ? 500 : opts.delay;
		this.offset = opts.offset == null ? 4 : opts.offset;

		this.bubble = null;
		this.show_timer = null;

		// hover: wait out the delay (or skip it right after another tooltip);
		// focus: show right away, but only for keyboard focus — a click also
		// focuses, and a tooltip popping on every click is just noise
		this.onenter = () => {
			const warm = Date.now() - last_hidden_at < SKIP_DELAY_MS;
			this.schedule(warm ? 0 : this.delay);
		};
		this.onleave = () => this.hide();
		this.onfocus = () => {
			if (this.trigger_el.matches(":focus-visible")) this.schedule(0);
		};
		this.onblur = () => this.hide();
		// pressing the trigger means the label did its job — get out of the
		// way (Escape too, without closing anything else above it)
		this.ondown = (e) => {
			if (e.key === "Escape" && this.bubble) e.stopPropagation();
			this.hide();
		};

		this.trigger_el.addEventListener("pointerenter", this.onenter);
		this.trigger_el.addEventListener("pointerleave", this.onleave);
		this.trigger_el.addEventListener("focus", this.onfocus);
		this.trigger_el.addEventListener("blur", this.onblur);
		this.trigger_el.addEventListener("pointerdown", this.ondown);
		this.trigger_el.addEventListener("keydown", this.ondown);
	}

	schedule(wait) {
		if (this.bubble || !this.text) return;
		clearTimeout(this.show_timer);
		this.show_timer = setTimeout(() => this.show(), wait);
	}

	show() {
		if (this.bubble || !this.text || !this.trigger_el.isConnected) return;

		// evict whichever tooltip is showing now
		if (visible && visible !== this) visible.hide();
		visible = this;

		const bubble = document.createElement("div");
		bubble.className = "es-tooltip";
		bubble.setAttribute("role", "tooltip");
		bubble.id = `es-tooltip-${++id_counter}`;
		bubble.textContent = this.text; // text, never HTML (set_text edits this node)

		if (this.shortcut) {
			const hint = document.createElement("span");
			hint.className = "es-tooltip__shortcut";
			// symbols like ⌘ read poorly; the label alone stays the
			// accessible description (same call as the menu shortcuts)
			hint.setAttribute("aria-hidden", "true");
			for (const key of shortcut_keys(this.shortcut)) {
				const kbd = document.createElement("kbd");
				kbd.textContent = key;
				hint.appendChild(kbd);
			}
			bubble.appendChild(hint);
		}

		const arrow = document.createElement("span");
		arrow.className = "es-tooltip__arrow";
		bubble.appendChild(arrow);

		// same drill as menus: into <body> first (place() needs the real
		// size), position, then data-state starts the enter animation
		document.body.appendChild(bubble);
		const anchor = this.trigger_el.getBoundingClientRect();
		place(bubble, anchor, this.side, this.align, this.offset);

		// point the arrow at the trigger's center even when the bubble was
		// nudged sideways to stay on screen, but never into the rounded
		// corners (8px in from either end)
		const rect = bubble.getBoundingClientRect();
		const landed = bubble.getAttribute("data-side");
		if (landed === "top" || landed === "bottom") {
			const center = anchor.left + anchor.width / 2 - rect.left;
			const offset = Math.min(Math.max(center, 8), rect.width - 8);
			bubble.style.setProperty("--arrow-offset", `${Math.round(offset)}px`);
		} else {
			const center = anchor.top + anchor.height / 2 - rect.top;
			const offset = Math.min(Math.max(center, 8), rect.height - 8);
			bubble.style.setProperty("--arrow-offset", `${Math.round(offset)}px`);
		}

		bubble.setAttribute("data-state", "open");
		this.trigger_el.setAttribute("aria-describedby", bubble.id);
		this.bubble = bubble;
	}

	hide() {
		clearTimeout(this.show_timer);
		if (!this.bubble) return;

		if (visible === this) visible = null;
		last_hidden_at = Date.now();
		this.trigger_el.removeAttribute("aria-describedby");

		// let the exit animation play, then drop the node
		const bubble = this.bubble;
		this.bubble = null;
		bubble.setAttribute("data-state", "closed");
		setTimeout(() => bubble.remove(), EXIT_MS + 50);
	}

	/** Change the label; applies from the next show. */
	set_text(text) {
		this.text = text || "";
		if (this.bubble) this.bubble.childNodes[0].nodeValue = this.text;
	}

	destroy() {
		this.hide();
		if (!this.trigger_el) return;
		this.trigger_el.removeEventListener("pointerenter", this.onenter);
		this.trigger_el.removeEventListener("pointerleave", this.onleave);
		this.trigger_el.removeEventListener("focus", this.onfocus);
		this.trigger_el.removeEventListener("blur", this.onblur);
		this.trigger_el.removeEventListener("pointerdown", this.ondown);
		this.trigger_el.removeEventListener("keydown", this.ondown);
	}
};

/**
 * Convenience form: attach a tooltip and get the trigger back, so it chains
 * inside append(...) calls. The instance is on `.data("es-tooltip")` when
 * you need set_text/destroy.
 * @param {Element|JQuery} trigger
 * @param {TooltipOpts} opts
 * @returns {JQuery}
 * @example toolbar.append(frappe.ui.tooltip($btn, { text: __("Refresh") }));
 */
frappe.ui.tooltip = function (trigger, opts = {}) {
	const tooltip = new frappe.ui.Tooltip(trigger, opts);
	const $trigger = $(trigger);
	$trigger.data("es-tooltip", tooltip);
	return $trigger;
};

export default frappe.ui.tooltip;
