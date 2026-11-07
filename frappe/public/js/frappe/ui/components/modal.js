import { validated, resolve_content } from "./utils.js";
import { scrollbar_width, page_behind, guard_focus, trap_tab, return_focus } from "./overlay.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ModalOpts
 * @property {Element|JQuery} [element] An existing `.modal` element (frappe.get_modal() markup). Omit to have one made from `title`, `content` and `actions`.
 * @property {string} [title] Plain text.
 * @property {Element|JQuery|function|string} [content] The body. An element, or a function called with the modal; a plain string renders as text, never HTML.
 * @property {string} [message] Plain text under the title, at the top of the body.
 * @property {string} [icon] Icon name shown in a round badge before the title.
 * @property {"gray"|"amber"|"blue"|"red"|"green"} [theme="gray"] Color of the icon badge.
 * @property {Array<Object>} [actions] frappe.ui.button options for the footer; `onclick` is called with (event, modal), and an action without one closes the modal.
 * @property {Element|JQuery} [trigger] An existing element that opens the modal.
 * @property {Object} [button] Options for a generated frappe.ui.button trigger (ignored when `trigger` is passed).
 * @property {"small"|"large"|"extra-large"} [size] Wider or narrower than the default width.
 * @property {"top"|"center"} [position="center"] Where the modal sits on the screen.
 * @property {boolean|"static"} [dismissible=true] Escape and a click outside close it; "static" makes them bounce it instead; false ignores them.
 * @property {boolean} [show_close_button=true] The × in the header.
 * @property {boolean} [animate=true] Fade in and out.
 * @property {boolean|string|Element} [focus=true] What gets focus once it is open: the modal itself (true), an element or selector inside it, or nothing (false).
 * @property {function} [on_show] Called before it opens.
 * @property {function} [on_shown] Called once it is open and the animation ended.
 * @property {function} [on_hide] Called with the reason before it closes: "escape" | "outside" | "close-button" | "action" | "owner" | "route", or what your own `modal.hide(reason)` passed.
 * @property {function} [on_hidden] Called with the reason once it is closed and the backdrop is gone.
 */

const SIZES = { small: "modal-sm", large: "modal-lg", "extra-large": "modal-xl" };
const POSITIONS = { top: "modal-dialog-top", center: "modal-dialog-centered" };
const THEMES = ["gray", "amber", "blue", "red", "green"];
const DISMISSIBLE = [true, false, "static"];
const EVENTS = ["show", "shown", "hide", "hidden"];
const FIXED_CONTENT = ".fixed-top, .fixed-bottom, .is-fixed, .sticky-top";
const STICKY_CONTENT = ".sticky-top";

const open_modals = [];
const page_lock = { count: 0, restore: [] };

const reflow = (element) => element.offsetHeight;

function transition_ms(element) {
	if (!element) return 0;
	const style = getComputedStyle(element);
	return (
		((parseFloat(style.transitionDuration) || 0) + (parseFloat(style.transitionDelay) || 0)) *
		1000
	);
}

function after_transition(element, callback, duration = transition_ms(element)) {
	let timer;
	const done = (event) => {
		if (event && event.target !== element) return;
		cancel();
		callback();
	};
	const cancel = () => {
		element.removeEventListener("transitionend", done);
		clearTimeout(timer);
	};
	element.addEventListener("transitionend", done);
	timer = setTimeout(done, duration);
	return cancel;
}

function lock_page(width) {
	if (page_lock.count++) return;
	if (width) {
		const adjust = (element, prop, sign) => {
			page_lock.restore.push([element, prop, element.style[prop]]);
			const current = parseFloat(getComputedStyle(element)[prop]) || 0;
			element.style[prop] = `${current + sign * width}px`;
		};
		document.querySelectorAll(FIXED_CONTENT).forEach((el) => adjust(el, "paddingRight", 1));
		document.querySelectorAll(STICKY_CONTENT).forEach((el) => adjust(el, "marginRight", -1));
		adjust(document.body, "paddingRight", 1);
	}
	document.body.classList.add("modal-open");
}

function unlock_page() {
	if (--page_lock.count) return;
	document.body.classList.remove("modal-open");
	page_lock.restore.forEach(([element, prop, value]) => (element.style[prop] = value));
	page_lock.restore = [];
}

/**
 * A dialog window over a dimmed page: the page behind doesn't scroll and
 * can't take focus until it closes. Several can be open at once, each above
 * the last; Escape closes only the top one. frappe.ui.Dialog is built on it,
 * so most forms want a Dialog; use this for your own markup.
 * @example
 * const modal = new frappe.ui.Modal({
 *     title: __("Discard changes?"),
 *     content: __("Your edits to this note will be lost."),
 *     size: "small",
 *     actions: [{ label: __("Discard"), variant: "solid", theme: "red", onclick: (e, modal) => modal.hide() }],
 * });
 * modal.on("hidden", (reason) => console.log(reason));
 * modal.show();
 */
frappe.ui.Modal = class Modal {
	/** @param {ModalOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.listeners = {};
		this.dismissible =
			validated(opts.dismissible ?? true, DISMISSIBLE, "dismissible", "Modal") ?? true;
		this.is_shown = false;
		this.transitioning = false;
		this.backdrop = null;

		this.element = $(opts.element)[0] || this.make();
		this.dialog = this.element.querySelector(".modal-dialog");
		const size = validated(opts.size || null, Object.keys(SIZES), "size", "Modal");
		if (size) this.dialog.classList.add(SIZES[size]);
		const position =
			validated(opts.position, Object.keys(POSITIONS), "position", "Modal") || "center";
		this.dialog.classList.add(POSITIONS[position]);
		if (opts.show_close_button === false) $(this.close_button).hide();
		if (opts.icon) this.set_icon(opts.icon, opts.theme);
		if (opts.message) this.set_message(opts.message);
		if (opts.actions?.length) this.set_actions(opts.actions);

		$(this.element).on("click.es-modal", ".btn-modal-close", (e) => {
			e.preventDefault();
			this.hide("close-button");
		});
		this.make_trigger();
	}

	get close_button() {
		return this.element.querySelector(".btn-modal-close");
	}

	get animated() {
		return this.element.classList.contains("fade");
	}

	get is_open() {
		return this.is_shown;
	}

	make() {
		const $modal = frappe.get_modal("", "");
		this.made = true;
		if (this.opts.animate === false) $modal.removeClass("fade");
		$modal.find(".modal-title").text(this.opts.title || "");
		const content = resolve_content(this.opts.content, this);
		if (content) $modal.find(".modal-body").append(content);
		return $modal[0];
	}

	/** The round badge before the title; a falsy `icon` removes it. */
	set_icon(icon, theme) {
		this.element.querySelector(".modal-icon")?.remove();
		if (!icon) return;
		const badge = document.createElement("div");
		badge.className = "modal-icon";
		badge.dataset.theme = validated(theme, THEMES, "theme", "Modal") || "gray";
		badge.innerHTML = frappe.utils.icon(String(icon).replace(/^lucide-/, ""), "sm");
		this.element.querySelector(".modal-title").before(badge);
	}

	/** Plain text under the title; a falsy `text` removes it. */
	set_message(text) {
		let description = this.element.querySelector(".modal-description");
		if (!text) {
			description?.remove();
			this.element.removeAttribute("aria-describedby");
			return;
		}
		if (!description) {
			description = document.createElement("p");
			description.className = "modal-description";
			description.id = frappe.utils.get_random(8);
			this.element.querySelector(".modal-body").prepend(description);
		}
		description.textContent = text;
		this.element.setAttribute("aria-describedby", description.id);
	}

	/** Replace the buttons set_actions added before; Dialog's own footer buttons stay. */
	set_actions(actions = []) {
		this.$actions?.remove();
		this.$actions = $(
			actions.map(
				(action) =>
					frappe.ui.button({
						...action,
						onclick: (e) =>
							action.onclick ? action.onclick(e, this) : this.hide("action"),
					})[0]
			)
		);
		const footer = this.element.querySelector(".modal-footer");
		footer.querySelector(".standard-actions").append(...this.$actions);
		footer.classList.toggle("hide", !footer.querySelector(".es-button:not(.hide)"));
	}

	make_trigger() {
		if (!this.opts.trigger && !this.opts.button) return;
		const button_opts = { label: __("Open"), ...this.opts.button };
		delete button_opts.onclick;
		this.$trigger = this.opts.trigger ? $(this.opts.trigger) : frappe.ui.button(button_opts);
		this.trigger_el = this.$trigger[0];
		if (!this.trigger_el) return;
		this.trigger_el.setAttribute("aria-haspopup", "dialog");
		this.ontriggerclick = (e) => {
			e.preventDefault();
			this.show();
		};
		this.trigger_el.addEventListener("click", this.ontriggerclick);
	}

	/** Listen to "show" | "shown" | "hide" | "hidden"; hide and hidden get the reason. */
	on(event, handler) {
		if (validated(event, EVENTS, "event", "Modal")) {
			(this.listeners[event] = this.listeners[event] || []).push(handler);
		}
		return this;
	}

	off(event, handler) {
		const handlers = this.listeners[event];
		if (handlers) this.listeners[event] = handlers.filter((h) => h !== handler);
		return this;
	}

	emit(event, reason) {
		this.opts[`on_${event}`]?.(reason, this);
		for (const handler of [...(this.listeners[event] || [])]) handler.call(this, reason, this);
	}

	show() {
		if (this.is_shown || this.transitioning) return;
		this.emit("show");

		this.is_shown = true;
		if (this.animated) this.transitioning = true;
		this.return_to = this.trigger_el || document.activeElement;
		this.page_bar = scrollbar_width();
		lock_page(this.page_bar);
		open_modals.push(this);
		this.adjust_padding();
		this.bind();
		this.show_backdrop(() => this.show_element());
	}

	hide(reason = "owner") {
		if (!this.is_shown || this.transitioning) return;
		this.emit("hide", reason);
		if (!this.is_shown) return;

		this.is_shown = false;
		const animated = this.animated;
		if (animated) this.transitioning = true;
		open_modals.splice(open_modals.indexOf(this), 1);
		this.unbind();
		this.element.classList.remove("show");
		return_focus(this.return_to, this.element);

		const hidden = () => this.hide_element(reason);
		if (animated) after_transition(this.element, hidden);
		else hidden();
	}

	toggle() {
		this.is_shown ? this.hide() : this.show();
	}

	destroy() {
		this.hide();
		this.trigger_el?.removeEventListener("click", this.ontriggerclick);
		$(this.element).off(".es-modal");
		if (this.made) this.element.remove();
	}

	/** Let focus leave the modal (a minimized dialog), until trap_focus(). */
	release_focus() {
		this.stop_guard?.();
		this.stop_guard = null;
	}

	trap_focus() {
		if (this.stop_guard || !this.is_shown) return;
		this.stop_guard = guard_focus(this.element, this.background);
	}

	show_element() {
		const body = this.dialog.querySelector(".modal-body");
		if (this.element.parentNode?.nodeType !== Node.ELEMENT_NODE) {
			document.body.appendChild(this.element);
		}

		this.element.style.display = "block";
		this.element.removeAttribute("aria-hidden");
		this.element.setAttribute("aria-modal", true);
		this.element.setAttribute("role", "dialog");
		if (this.dialog.classList.contains("modal-dialog-scrollable") && body) {
			body.scrollTop = 0;
		} else {
			this.element.scrollTop = 0;
		}

		if (this.animated) reflow(this.element);
		this.element.classList.add("show");
		this.trap_focus();

		const shown = () => {
			this.focus_initial();
			this.transitioning = false;
			this.emit("shown");
		};
		if (this.animated) after_transition(this.dialog, shown);
		else shown();
	}

	focus_initial() {
		const focus = this.opts.focus ?? true;
		if (focus === false) return;
		const target =
			focus === true ? this.element : $(this.element).find(focus)[0] || this.element;
		target.focus();
	}

	hide_element(reason) {
		this.element.style.display = "none";
		this.element.setAttribute("aria-hidden", true);
		this.element.removeAttribute("aria-modal");
		this.element.removeAttribute("role");
		this.transitioning = false;
		this.hide_backdrop(() => {
			this.element.style.paddingLeft = "";
			this.element.style.paddingRight = "";
			unlock_page();
			this.emit("hidden", reason);
		});
	}

	bind() {
		this.background = page_behind();
		this.onkeydown = (e) => {
			if (e.key === "Escape") this.on_escape(e);
			else if (e.key === "Tab" && this.stop_guard && !e.defaultPrevented) {
				trap_tab(this.element, e);
			}
		};
		this.onpointerdown = (e) => {
			if (!this.dialog.contains(e.target)) return;
			$(this.element).one("mouseup.es-modal-press", (up) => {
				if (up.target === this.element) this.ignore_outside_click = true;
			});
		};
		this.onclick = (e) => {
			if (this.ignore_outside_click) {
				this.ignore_outside_click = false;
				return;
			}
			if (e.target !== this.element) return;
			if (this.dismissible === "static") this.bounce();
			else if (this.dismissible) this.hide("outside");
		};
		this.onresize = () => this.adjust_padding();
		this.element.addEventListener("keydown", this.onkeydown);
		this.element.addEventListener("mousedown", this.onpointerdown);
		this.element.addEventListener("click", this.onclick);
		window.addEventListener("resize", this.onresize);
	}

	unbind() {
		this.release_focus();
		this.element.removeEventListener("keydown", this.onkeydown);
		this.element.removeEventListener("mousedown", this.onpointerdown);
		this.element.removeEventListener("click", this.onclick);
		$(this.element).off(".es-modal-press");
		window.removeEventListener("resize", this.onresize);
	}

	on_escape(e) {
		if (open_modals[open_modals.length - 1] !== this) return;
		if (this.dismissible === true) {
			e.preventDefault();
			this.hide("escape");
		} else if (this.dismissible === "static") {
			this.bounce();
		}
	}

	adjust_padding() {
		const overflowing = this.element.scrollHeight > document.documentElement.clientHeight;
		const own_bar = this.element.offsetWidth - this.element.clientWidth;
		if (!this.page_bar && overflowing) this.element.style.paddingLeft = `${own_bar}px`;
		if (this.page_bar && !overflowing) this.element.style.paddingRight = `${this.page_bar}px`;
	}

	bounce() {
		const overflowing = this.element.scrollHeight > document.documentElement.clientHeight;
		if (!overflowing) this.element.style.overflowY = "hidden";
		this.element.classList.add("modal-static");

		this.cancel_bounce?.();
		this.cancel_bounce = after_transition(
			this.element,
			() => {
				this.element.classList.remove("modal-static");
				if (overflowing) return;
				this.cancel_bounce = after_transition(
					this.element,
					() => (this.element.style.overflowY = ""),
					0
				);
			},
			transition_ms(this.dialog)
		);
		this.element.focus();
	}

	show_backdrop(callback) {
		this.backdrop = document.createElement("div");
		this.backdrop.className = "modal-backdrop";
		if (this.animated) this.backdrop.classList.add("fade");
		document.body.appendChild(this.backdrop);
		if (this.animated) reflow(this.backdrop);
		this.backdrop.classList.add("show");
		if (this.animated) after_transition(this.backdrop, callback);
		else callback();
	}

	hide_backdrop(callback) {
		const backdrop = this.backdrop;
		if (!backdrop) return callback();
		backdrop.classList.remove("show");
		const remove = () => {
			backdrop.remove();
			if (this.backdrop === backdrop) this.backdrop = null;
			callback();
		};
		if (this.animated) after_transition(backdrop, remove);
		else remove();
	}
};

/**
 * Convenience form: makes the trigger button and wires the modal in one
 * call. Returns the trigger element (append it wherever); the instance is
 * on `.data("es-modal")` when you need show/hide.
 * @param {ModalOpts} opts
 * @returns {JQuery}
 * @example toolbar.append(frappe.ui.modal({
 *     button: { label: __("Shortcuts"), icon: "keyboard" },
 *     title: __("Keyboard shortcuts"),
 *     content: () => build_shortcut_list(),
 * }));
 */
frappe.ui.modal = function (opts = {}) {
	const modal = new frappe.ui.Modal({ button: {}, ...opts });
	modal.$trigger.data("es-modal", modal);
	return modal.$trigger;
};

export default frappe.ui.modal;
