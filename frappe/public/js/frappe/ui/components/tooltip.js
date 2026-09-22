import { place, SIDES, ALIGNS } from "./position.js";
import { validated, shortcut_keys } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} TooltipOpts
 * @property {string} text The label. Rendered as text, never HTML.
 * @property {boolean} [when_truncated=false] Only show when the trigger's text is cut off (an ellipsis, a line clamp), and stay silent when it fits. Without `text`, the label is the trigger's own text, read at show time.
 * @property {string|string[]} [shortcut] Keyboard hint after the label, one <kbd> per key — pass the raw combo ("ctrl+b") and each key becomes its OS form (⌘B on Mac), or an array of already-formatted keys. Display only; binding stays the caller's job.
 * @property {"top"|"right"|"bottom"|"left"} [side="top"] Which side of the trigger the bubble prefers.
 * @property {"start"|"center"|"end"} [align="center"] How the bubble lines up along that side.
 * @property {"start"|"center"} [text_align="center"] How the label sits inside the bubble. A label that lists things reads better from one left edge; newlines in the text are kept either way.
 * @property {number} [delay=500] Hover delay in ms before showing. Focus always shows immediately.
 * @property {number} [offset=4] Gap between trigger and bubble, in px. The 4px arrow fills it, tip touching the trigger (frappe-ui's side-offset).
 * @property {string} [class] Extra class(es) on the bubble, for a variant — "es-tooltip--plain" drops the arrow. Styling only; the bubble always keeps `es-tooltip`.
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

const TEXT_ALIGNS = ["start", "center"];

let id_counter = 0;

/**
 * Does this element clip its text? `nowrap` clips sideways (the classic ellipsis), a line clamp
 * clips downward, and anything else can only clip at a fixed height, so both are checked.
 *
 * scrollWidth and clientWidth are integers, so at fractional zoom a box that fits can report a
 * 1px difference; the 1px of slack absorbs that. An inline element cannot clip at all
 * (`overflow: hidden` does nothing on one), so it always reads as "fits".
 */
function is_truncated(el) {
	// a hidden element reports zeroes for everything; it has no answer yet
	if (el.offsetWidth === 0 && el.offsetHeight === 0) return false;
	const style = getComputedStyle(el);
	let axis = "both";
	if (style.whiteSpace === "nowrap" || style.whiteSpace === "pre") axis = "x";
	else if (style.webkitLineClamp && style.webkitLineClamp !== "none") axis = "y";
	const x = axis !== "y" && el.scrollWidth - el.clientWidth > 1;
	const y = axis !== "x" && el.scrollHeight - el.clientHeight > 1;
	return x || y;
}

/** Collapse the runs of whitespace that indented markup leaves behind. */
function collapse(text) {
	return (text || "").replace(/\s+/g, " ").trim();
}

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
// Point the arrow at the trigger's center even when the bubble was nudged sideways to stay on
// screen, but never into the rounded corners (8px in from either end).
function point_arrow(bubble, anchor) {
	const rect = bubble.getBoundingClientRect();
	const landed = bubble.getAttribute("data-side");
	const offset =
		landed === "top" || landed === "bottom"
			? Math.min(Math.max(anchor.left + anchor.width / 2 - rect.left, 8), rect.width - 8)
			: Math.min(Math.max(anchor.top + anchor.height / 2 - rect.top, 8), rect.height - 8);
	bubble.style.setProperty("--arrow-offset", `${Math.round(offset)}px`);
}

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
		this.when_truncated = !!opts.when_truncated;
		this.shortcut = opts.shortcut || null;
		this.side = validated(opts.side, SIDES, "side", "Tooltip") || "top";
		this.align = validated(opts.align, ALIGNS, "align", "Tooltip") || "center";
		this.text_align =
			validated(opts.text_align, TEXT_ALIGNS, "text_align", "Tooltip") || "center";
		this.delay = opts.delay == null ? 500 : opts.delay;
		this.offset = opts.offset == null ? 4 : opts.offset;
		// A variant class, not a replacement: `es-tooltip` is what the stylesheet and the
		// data-attribute contract hang off, so it is always there and this is appended to it.
		this.extra_class = opts.class || "";

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

	schedule(wait = this.delay) {
		if (this.bubble || !(this.text || this.when_truncated)) return;
		clearTimeout(this.show_timer);
		this.show_timer = setTimeout(() => this.show(), wait);
	}

	show() {
		if (this.bubble || !this.trigger_el.isConnected) return;
		// Truncation is checked here, not when the tooltip is attached, because the answer keeps
		// changing: the window resizes, a column is dragged, the label is renamed, the webfont
		// swaps in. By now the layout is whatever it is on screen.
		if (this.when_truncated && !is_truncated(this.trigger_el)) return;
		const text =
			this.text || (this.when_truncated ? collapse(this.trigger_el.textContent) : "");
		if (!text) return;

		// evict whichever tooltip is showing now
		if (visible && visible !== this) visible.hide();
		visible = this;

		const bubble = document.createElement("div");
		const classes = ["es-tooltip"];
		if (this.text_align === "start") classes.push("es-tooltip--text-start");
		if (this.extra_class) classes.push(this.extra_class);
		bubble.className = classes.join(" ");
		bubble.setAttribute("role", "tooltip");
		bubble.id = `es-tooltip-${++id_counter}`;
		bubble.textContent = text; // text, never HTML (set_text edits this node)

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

		// `es-tooltip--plain` hides the arrow, so it is not built either -- a node nothing can see,
		// with a position computed for it below, is work done for no one.
		const plain = bubble.classList.contains("es-tooltip--plain");
		if (!plain) {
			const arrow = document.createElement("span");
			arrow.className = "es-tooltip__arrow";
			bubble.appendChild(arrow);
		}

		// same drill as menus: into <body> first (place() needs the real
		// size), position, then data-state starts the enter animation
		document.body.appendChild(bubble);
		const anchor = this.trigger_el.getBoundingClientRect();
		place(bubble, anchor, this.side, this.align, this.offset);

		// An arrowless bubble has nothing to point with. The enter animation reads
		// `--arrow-offset` as its origin, so leaving it unset grows the bubble from its own
		// centre, which is what one should do.
		if (!plain) point_arrow(bubble, anchor);

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

	/**
	 * Tooltips for every element matching `selector` inside `root`, with one set of listeners no
	 * matter how many match. For grids and long lists: it costs nothing per item, covers items
	 * rendered later, and only the element under the pointer ever gets a Tooltip, which is thrown
	 * away when the pointer leaves. Returns a function that stops it.
	 * @param {Element|JQuery} root
	 * @param {string} selector
	 * @param {TooltipOpts} opts
	 * @returns {() => void}
	 * @example frappe.ui.Tooltip.delegate(page.body, ".icon-title", { when_truncated: true });
	 */
	static delegate(root, selector, opts = {}) {
		root = $(root)[0];
		let current = null;

		const release = () => {
			current?.destroy();
			current = null;
		};

		const claim = (el, from_keyboard) => {
			if (current?.trigger_el === el) return;
			release();
			current = new Tooltip(el, opts);
			// The enter or focus event that brought us here is already gone, so start the
			// tooltip by hand. `onenter` keeps the shorter wait right after another tooltip
			// closed. From here its own listeners take over (leave, blur, Escape, press).
			if (from_keyboard) current.schedule(0);
			else current.onenter();
		};

		const match = (e) => {
			const hit = e.target?.closest?.(selector);
			return hit && root.contains(hit) ? hit : null;
		};

		// pointerover and pointerout bubble (pointerenter and pointerleave do not), which is
		// what makes one listener on the root enough
		const onover = (e) => {
			const hit = match(e);
			if (hit) claim(hit, false);
			else if (current && !current.trigger_el.contains(e.target)) release();
		};
		const onout = (e) => {
			if (current && !current.trigger_el.contains(e.relatedTarget)) release();
		};
		// keyboard focus only: a click also focuses, and a tooltip on every click is noise
		const onfocus = (e) => {
			const hit = match(e);
			if (hit?.matches(":focus-visible")) claim(hit, true);
		};

		root.addEventListener("pointerover", onover);
		root.addEventListener("pointerout", onout);
		root.addEventListener("focusin", onfocus);
		root.addEventListener("focusout", release);

		return () => {
			release();
			root.removeEventListener("pointerover", onover);
			root.removeEventListener("pointerout", onout);
			root.removeEventListener("focusin", onfocus);
			root.removeEventListener("focusout", release);
		};
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
