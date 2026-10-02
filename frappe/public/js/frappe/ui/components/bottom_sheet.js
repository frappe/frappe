import { validated, is_thenable, icon_html, TABBABLE, resolve_content } from "./utils.js";
import { normalize_options, build_item } from "./menu.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} BottomSheetStep
 * @property {string} [title] Plain text; it also names the sheet for screen readers.
 * @property {string} [subtitle] Muted second line under the title.
 * @property {Element|JQuery|Array|function|string} [header] Your own content, fixed at the top: a search box, tabs, a title with a button beside it. It takes the title's place; with a `title` it sits under it. An element, several in an array (side by side), or a function called with the sheet.
 * @property {Element|JQuery|function|string} [content] The body, which scrolls. An element, or a function called with the sheet the first time the step shows; a plain string renders as text, never HTML.
 * @property {Array} [options] Tappable rows, after any content: MenuItem-like { label, icon, description, theme, selected, disabled, onclick(e, sheet) } and { group, options } sections. A tap runs onclick and closes the sheet unless it returns false.
 * @property {Element|JQuery|Array|function|string} [footer] Your own content, fixed at the bottom: buttons (frappe.ui.button), a tab bar, a total. Same forms as `header`. Nothing closes the sheet for you: call `sheet.close()`.
 * @property {function} [on_show] Called with the sheet each time the step becomes the one on screen: when it opens, is pushed, or is returned to with Back.
 */

/**
 * @typedef {BottomSheetStep & Object} BottomSheetOpts
 * @property {Element|JQuery} [trigger] An existing element that opens the sheet.
 * @property {Object} [button] Options for a generated frappe.ui.button trigger (ignored when `trigger` is passed).
 * @property {"auto"|"half"|"full"} [height="auto"] auto fits the content up to 90% of the screen.
 * @property {Array<"half"|"full">} [snap_points] Heights the handle drags between; the sheet opens at the first.
 * @property {boolean} [show_close=false] A close button in the header.
 * @property {boolean} [dismissible=true] A tap on the scrim, a swipe down and Escape close it.
 * @property {function} [on_open] Called with the sheet once it is shown.
 * @property {function} [on_close] Called with the reason: "scrim" | "swipe" | "escape" | "close" | "option" | "route" | "owner", or what your own `sheet.close(reason)` passed.
 */

const HEIGHTS = ["auto", "half", "full"];
const SNAPS = ["half", "full"];
const EXIT_MS = 200; // keep in sync with es-sheet-out in bottom_sheet.css
// a drag down past this share of the height, or a flick, closes the sheet
const CLOSE_SHARE = 0.25;
const FLICK = 0.5; // px per ms
const EXPAND_DRAG = 40;

// page-level layers that can be in <body> before a sheet opens and still take
// focus from it; anything else added to <body> after it opened is allowed too
const LAYERS = ".es-bottom-sheet-root, .modal, .datepickers-container, .es-toast-container";
// the menu layer; a sheet lifted to or past it has to lift what it opens as well
const MENU_LAYER = 1060;

let id_counter = 0;
const open_sheets = new Set();
let router_bound = false;

// one listener for every sheet: frappe.router.off can't remove a handler
function close_on_route_change() {
	if (router_bound || !frappe.router?.on) return;
	router_bound = true;
	frappe.router.on("change", () => [...open_sheets].forEach((sheet) => sheet.close("route")));
}

// sheets sit below dialogs, so a dialog opened from a sheet stacks above it on
// its own; a sheet opened from a dialog lifts itself over that dialog instead
function layer_above_open_dialogs(root) {
	const dialogs = [...document.querySelectorAll(".modal.show")];
	const top = Math.max(0, ...dialogs.map((el) => parseInt(getComputedStyle(el).zIndex) || 0));
	if (!top) return 0;
	root.style.zIndex = top + 1;
	return top + 1;
}

const z_of = (el) => parseInt(getComputedStyle(el).zIndex) || 0;

// a classic Link / Autocomplete suggestion list or the date picker, open on the field
function field_popup_open(target) {
	const list = target
		.closest?.(".awesomplete")
		?.querySelector(":scope > ul, :scope > [role='listbox']");
	if (list && !list.hidden && list.children.length) return true;
	return !!document.querySelector(".datepicker.active");
}

// a header or footer: one piece of the caller's content, or several side by side
function slot_parts(content, sheet) {
	if (typeof content === "function") content = content(sheet);
	return []
		.concat(content || [])
		.flatMap((part) => (typeof part === "string" ? [resolve_content(part)] : $(part).get()));
}

/**
 * A panel that slides up from the bottom of the screen, for choices, short
 * forms and confirmations on phones. Modal: the page behind is dimmed and
 * doesn't scroll, focus stays inside until it closes. Drag the handle down
 * to close, or between snap points. A follow-up choice is a step pushed
 * into the same sheet (Back appears), never a second sheet.
 * @example
 * new frappe.ui.BottomSheet({
 *     title: __("Sort by"),
 *     options: [{ label: __("Created On"), selected: true, onclick: () => sort("creation") }],
 * }).open();
 */
frappe.ui.BottomSheet = class BottomSheet {
	/** @param {BottomSheetOpts} opts */
	constructor(opts = {}) {
		// a copy, so set_title / set_options never change the caller's object
		this.opts = { ...opts };
		this.height = validated(opts.height, HEIGHTS, "height", "BottomSheet") || "auto";
		this.snap_points = (opts.snap_points || []).filter((snap) =>
			validated(snap, SNAPS, "snap_points", "BottomSheet")
		);
		this.dismissible = opts.dismissible !== false;
		this.steps = [];
		this.root = null;

		if (opts.trigger || opts.button) {
			const button_opts = { label: __("Open"), ...opts.button };
			// the trigger's click opens the sheet, so its own onclick would double up
			delete button_opts.onclick;
			this.$trigger = opts.trigger ? $(opts.trigger) : frappe.ui.button(button_opts);
			this.trigger_el = this.$trigger[0];
			if (this.trigger_el) {
				this.trigger_el.setAttribute("aria-haspopup", "dialog");
				this.ontriggerclick = (e) => {
					e.preventDefault();
					this.open();
				};
				this.trigger_el.addEventListener("click", this.ontriggerclick);
			}
		}
	}

	get is_open() {
		return !!this.root;
	}

	open() {
		if (this.root) return;
		this.return_focus = document.activeElement;
		// the page behind; taken before rendering, so pickers the content makes aren't in it
		this.background = new Set(document.body.children);
		this.title_id = `es-bottom-sheet-${++id_counter}-title`;

		const root = document.createElement("div");
		root.className = "es-bottom-sheet-root";
		root.innerHTML = `
			<div class="es-bottom-sheet__scrim"></div>
			<div class="es-bottom-sheet flex flex-col" role="dialog" aria-modal="true" tabindex="-1">
				<div class="es-bottom-sheet__grip flex justify-center"><div class="es-bottom-sheet__handle"></div></div>
				<div class="es-bottom-sheet__header flex items-center gap-1"></div>
				<div class="es-bottom-sheet__subheader flex items-center gap-2" hidden></div>
				<div class="es-bottom-sheet__body"></div>
				<div class="es-bottom-sheet__footer flex gap-2"></div>
			</div>`;
		this.root = root;
		this.scrim = root.querySelector(".es-bottom-sheet__scrim");
		this.panel = root.querySelector(".es-bottom-sheet");
		this.header = root.querySelector(".es-bottom-sheet__header");
		this.subheader = root.querySelector(".es-bottom-sheet__subheader");
		this.body = root.querySelector(".es-bottom-sheet__body");
		this.footer = root.querySelector(".es-bottom-sheet__footer");

		// fresh copies per open: content() runs again and nothing built last time is reused
		this.steps = [{ ...this.opts }];
		this.render();
		this.set_height(this.snap_points[0] || this.height);

		this.lift_layers(layer_above_open_dialogs(root));
		document.body.appendChild(root);
		root.setAttribute("data-state", "open");
		if (!open_sheets.size) {
			const html = document.documentElement;
			// keep the scrollbar's space only if there was a scrollbar to hide
			html.classList.toggle("es-bottom-sheet-gutter", window.innerWidth > html.clientWidth);
			html.classList.add("es-bottom-sheet-open");
		}
		open_sheets.add(this);
		close_on_route_change();

		this.bind();
		this.panel.focus({ preventScroll: true });
		this.opts.on_open && this.opts.on_open(this);
	}

	close(reason = "owner") {
		if (!this.root) return;
		const root = this.root;
		this.root = null;
		this.unbind();
		open_sheets.delete(this);
		if (!open_sheets.size) {
			document.documentElement.classList.remove(
				"es-bottom-sheet-open",
				"es-bottom-sheet-gutter"
			);
		}
		this.drop_layers();
		// so set_title / set_options while closed change what the next open starts from
		this.steps = [];

		// a swipe keeps its drag offset, so the exit slides on from there
		root.setAttribute("data-state", "closed");
		setTimeout(() => root.remove(), EXIT_MS + 50);

		// back to where it came from, unless the tap that closed it moved focus on
		// (an option that opened another sheet or a dialog)
		const active = document.activeElement;
		if (!active || active === document.body || root.contains(active)) {
			(this.trigger_el || this.return_focus)?.focus?.({ preventScroll: true });
		}
		this.opts.on_close && this.opts.on_close(reason);
	}

	toggle() {
		this.is_open ? this.close("owner") : this.open();
	}

	destroy() {
		this.close("owner");
		this.trigger_el?.removeEventListener("click", this.ontriggerclick);
	}

	/** Show a follow-up step in the same sheet; Back returns to the previous one. */
	push(step) {
		if (!this.root) return;
		this.current_step().scroll_top = this.body.scrollTop;
		this.steps.push({ ...step });
		this.render("forward");
	}

	pop() {
		if (!this.root || this.steps.length < 2) return;
		this.steps.pop();
		this.render("back");
	}

	set_title(title, subtitle) {
		const step = this.current_step();
		Object.assign(step, { title, subtitle });
		this.root && this.keeping_focus(() => this.render_header(step));
	}

	/** Replace the option rows of the step on screen: after a search, a toggle, a reload. */
	set_options(options) {
		const step = this.current_step();
		step.options = options;
		if (!this.root || !step._el) return;
		this.keeping_focus(() => {
			const list = this.build_options(options || []);
			step._options ? step._options.replaceWith(list) : step._el.append(list);
			step._options = list;
		});
		this.body.scrollTop = 0;
	}

	set_height(height) {
		this.current_height = height;
		this.panel?.setAttribute("data-height", height);
	}

	current_step() {
		return this.steps[this.steps.length - 1] || this.opts;
	}

	// ---- rendering ----

	// the rebuilt part may have held focus (the row just tapped, Back); send it back
	// to the panel, where Escape and the Tab cycle are handled, not to <body>
	keeping_focus(rebuild) {
		rebuild();
		const active = document.activeElement;
		if (!active || active === document.body || !active.isConnected) {
			this.panel.focus({ preventScroll: true });
		}
	}

	render(motion) {
		const step = this.current_step();
		this.keeping_focus(() => {
			this.render_header(step);
			this.render_body(step);
			this.render_footer(step);
		});
		step.on_show && step.on_show(this);
		if (motion) {
			// cleared and reflowed first, so a second push or pop replays the slide
			this.body.removeAttribute("data-motion");
			void this.body.offsetWidth;
			this.body.setAttribute("data-motion", motion);
			this.body.addEventListener(
				"animationend",
				() => this.body.removeAttribute("data-motion"),
				{ once: true }
			);
		}
	}

	render_header(step) {
		this.header.replaceChildren();
		this.subheader.replaceChildren();
		const has_back = this.steps.length > 1;
		this.header.toggleAttribute("data-back", has_back);
		if (has_back) {
			this.header.append(
				frappe.ui.button({
					icon: "chevron-left",
					variant: "ghost",
					title: __("Back"),
					css_class: "es-bottom-sheet__back",
					onclick: () => this.pop(),
				})[0]
			);
		}

		// built once per step of this open, so going Back finds it as it was left
		if (step.header && !step._header) step._header = slot_parts(step.header, this);
		const custom = step._header || [];
		const has_text = !!(step.title || step.subtitle);
		const main = document.createElement("div");
		if (has_text) {
			main.className = "es-bottom-sheet__titles flex flex-col flex-1 min-w-0";
			if (step.title) {
				const title = document.createElement("div");
				title.className = "es-bottom-sheet__title";
				title.textContent = step.title;
				main.append(title);
			}
			if (step.subtitle) {
				const subtitle = document.createElement("div");
				subtitle.className = "es-bottom-sheet__subtitle";
				subtitle.textContent = step.subtitle;
				main.append(subtitle);
			}
			this.subheader.append(...custom);
		} else {
			// the caller's header takes the title's place, between Back and Close
			main.className = "es-bottom-sheet__header-slot flex items-center gap-2 flex-1 min-w-0";
			main.append(...custom);
		}
		this.header.append(main);

		if (this.opts.show_close) {
			this.header.append(
				frappe.ui.button({
					icon: "x",
					variant: "ghost",
					title: __("Close"),
					css_class: "es-bottom-sheet__close",
					onclick: () => this.close("close"),
				})[0]
			);
		}

		this.header.hidden = !has_text && !custom.length && !has_back && !this.opts.show_close;
		this.subheader.hidden = !has_text || !custom.length;
		// named by its title: the sheet's own, or the one in the caller's header
		const title = this.header.querySelector(".es-bottom-sheet__title");
		if (title) {
			title.id = this.title_id;
			this.panel.setAttribute("aria-labelledby", this.title_id);
		} else {
			this.panel.removeAttribute("aria-labelledby");
		}
	}

	render_body(step) {
		this.body.replaceChildren();
		// built once per step of this open, so going Back finds it as it was left
		if (!step._el) step._el = this.build_step_body(step);
		this.body.append(step._el);
		this.body.scrollTop = step.scroll_top || 0;
	}

	build_step_body(step) {
		const wrap = document.createElement("div");
		wrap.className = "flex flex-col gap-3";
		const content = resolve_content(step.content, this);
		if (content) {
			if (typeof step.content === "string") content.className = "es-bottom-sheet__text";
			wrap.append(content);
		}
		if (step.options) {
			step._options = this.build_options(step.options);
			wrap.append(step._options);
		}
		return wrap;
	}

	build_options(options) {
		const list = document.createElement("div");
		list.className = "es-bottom-sheet__options flex flex-col";
		const groups = normalize_options(options);
		// one label column: rows without an icon keep its space when any row has one
		const reserve_icon_space = groups.some((group) =>
			group.options.some((item) => item.icon || item.image)
		);
		for (const group of groups) {
			const section = document.createElement("div");
			section.className = "es-bottom-sheet__group flex flex-col";
			section.setAttribute("role", "group");
			if (group.group && !group.hide_label) {
				const label = document.createElement("div");
				label.className = "es-bottom-sheet__group-label";
				label.textContent = group.group;
				section.append(label);
				section.setAttribute("aria-label", group.group);
			}
			for (const item of group.options) {
				section.append(this.build_option(item, reserve_icon_space));
			}
			list.append(section);
		}
		return list;
	}

	build_option(item, reserve_icon_space) {
		const { el } = build_item(item, { reserve_icon_space, component: "BottomSheet" });
		el.classList.add("es-bottom-sheet__option");
		// a plain button in the sheet's Tab cycle, not a menu row driven by arrow keys
		el.removeAttribute("role");
		el.removeAttribute("tabindex");
		if (item.selected) {
			if (el.tagName === "BUTTON") el.setAttribute("aria-pressed", "true");
			el.insertAdjacentHTML(
				"beforeend",
				icon_html("check", "es-bottom-sheet__check", "BottomSheet")
			);
		}

		// a submenu is a step here: Back returns to this list
		if (item.submenu) {
			el.removeAttribute("aria-haspopup");
			el.removeAttribute("aria-expanded");
		}

		el.addEventListener("click", (e) => {
			// an answer that arrives after this open ended mustn't act on the next one
			const root = this.root;
			if (item.submenu) {
				const rows =
					typeof item.submenu === "function" ? item.submenu(e, this) : item.submenu;
				const show = (options) =>
					this.root === root && this.push({ title: item.label, options });
				is_thenable(rows) ? this.wait_for(el, rows).then(show) : show(rows);
				return;
			}
			const result = item.onclick ? item.onclick(e, this) : undefined;
			if (!is_thenable(result)) {
				if (result !== false) this.close("option");
				return;
			}
			// an async handler (load, then push a step) is waited for
			this.wait_for(el, result).then(
				(value) => value !== false && this.root === root && this.close("option")
			);
		});
		return el;
	}

	// busy row until the promise settles; resolves with its value
	wait_for(el, promise) {
		el.setAttribute("aria-busy", "true");
		if (el.tagName === "BUTTON") el.disabled = true;
		return promise.finally(() => {
			el.removeAttribute("aria-busy");
			if (el.tagName === "BUTTON") el.disabled = el.hasAttribute("data-disabled");
		});
	}

	// lifted over a dialog at or past the menu layer (a msgprint): what the sheet
	// opens (menus, pickers) and the toasts it fires go above it too
	lift_layers(z) {
		if (z < MENU_LAYER) return;
		const lift = (el) => {
			if (el.nodeType !== 1 || z_of(el) > z) return;
			this.lifted.push([el, el.style.zIndex]);
			el.style.zIndex = z + 1;
		};
		this.lifted = [];
		document.querySelectorAll(".es-toast-container").forEach(lift);
		this.layer_observer = new MutationObserver((records) =>
			records.forEach((record) => record.addedNodes.forEach(lift))
		);
		this.layer_observer.observe(document.body, { childList: true });
	}

	drop_layers() {
		if (!this.layer_observer) return;
		this.layer_observer.disconnect();
		this.layer_observer = null;
		this.lifted.forEach(([el, z_index]) => (el.style.zIndex = z_index));
		this.lifted = [];
	}

	render_footer(step) {
		this.footer.replaceChildren();
		if (step.footer && !step._footer) step._footer = slot_parts(step.footer, this);
		const parts = step._footer || [];
		this.footer.hidden = !parts.length;
		this.footer.append(...parts);
	}

	// ---- behaviour ----

	bind() {
		// capture phase, so it's known whether a field's own list was open before the
		// field closes it: that Escape belongs to the field, the next one to the sheet
		this.onescape = (e) => {
			if (e.key !== "Escape" || field_popup_open(e.target)) return;
			e.stopPropagation();
			if (this.steps.length > 1) this.pop();
			else if (this.dismissible) this.close("escape");
		};
		this.onkeydown = (e) => e.key === "Tab" && this.trap_tab(e);
		// the scrim can't take focus, so a press on it would drop focus on <body>
		this.onscrimpress = (e) => e.preventDefault();
		this.onscrimclick = () =>
			this.dismissible ? this.close("scrim") : this.panel.focus({ preventScroll: true });
		// modal: focus that reaches the page behind comes back
		this.onfocusin = (e) => {
			let top = e.target;
			while (top && top.parentElement !== document.body) top = top.parentElement;
			if (!top || !this.background.has(top) || top.matches(LAYERS)) return;
			this.panel.focus({ preventScroll: true });
		};
		this.ondragstart = (e) => this.drag_start(e);
		// an on-screen keyboard shrinks the visual viewport; the sheet sits above it
		this.onviewport = () => {
			const viewport = window.visualViewport;
			// a pinch-zoomed page shrinks the visual viewport too; that isn't a keyboard
			const zoomed = Math.abs((viewport.scale || 1) - 1) > 0.01;
			const covered = zoomed
				? 0
				: Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
			this.root?.style.setProperty("--es-sheet-keyboard", `${covered}px`);
		};

		this.panel.addEventListener("keydown", this.onescape, true);
		this.panel.addEventListener("keydown", this.onkeydown);
		this.scrim.addEventListener("mousedown", this.onscrimpress);
		this.scrim.addEventListener("click", this.onscrimclick);
		document.addEventListener("focusin", this.onfocusin);
		this.root
			.querySelector(".es-bottom-sheet__grip")
			.addEventListener("pointerdown", this.ondragstart);
		this.header.addEventListener("pointerdown", this.ondragstart);
		window.visualViewport?.addEventListener("resize", this.onviewport);
		window.visualViewport?.addEventListener("scroll", this.onviewport);
		// a keyboard already up when the sheet opens
		window.visualViewport && this.onviewport();
	}

	unbind() {
		this.drag_end();
		document.removeEventListener("focusin", this.onfocusin);
		window.visualViewport?.removeEventListener("resize", this.onviewport);
		window.visualViewport?.removeEventListener("scroll", this.onviewport);
	}

	// modal, so Tab cycles inside the sheet
	trap_tab(e) {
		const tabbables = [...this.panel.querySelectorAll(TABBABLE)].filter(
			(el) => el.offsetParent !== null
		);
		if (!tabbables.length) {
			e.preventDefault();
			return;
		}
		const first = tabbables[0];
		const last = tabbables[tabbables.length - 1];
		const active = document.activeElement;
		if (e.shiftKey && (active === first || active === this.panel)) {
			e.preventDefault();
			last.focus();
		} else if (!e.shiftKey && active === last) {
			e.preventDefault();
			first.focus();
		}
	}

	drag_start(e) {
		if (e.button !== 0 || this.drag) return;
		if (e.target.closest("button, a, input, select, textarea")) return;
		// captured, so the release arrives even when the pointer leaves the window
		const el = e.currentTarget;
		try {
			el.setPointerCapture(e.pointerId);
		} catch {
			// a pointer that's already gone: drag without capture
		}
		this.drag = {
			el,
			start_y: e.clientY,
			last_y: e.clientY,
			last_t: e.timeStamp,
			velocity: 0,
			offset: 0,
			height: this.panel.offsetHeight,
		};
		this.panel.setAttribute("data-dragging", "");
		this.ondragmove = (event) => this.drag_move(event);
		this.ondragup = () => this.drag_release();
		el.addEventListener("pointermove", this.ondragmove);
		el.addEventListener("pointerup", this.ondragup);
		el.addEventListener("pointercancel", this.ondragup);
		el.addEventListener("lostpointercapture", this.ondragup);
	}

	drag_move(e) {
		const drag = this.drag;
		const dt = e.timeStamp - drag.last_t;
		if (dt > 0) drag.velocity = (e.clientY - drag.last_y) / dt;
		drag.last_y = e.clientY;
		drag.last_t = e.timeStamp;
		const dy = e.clientY - drag.start_y;
		// upward drags resist: the sheet only grows by snapping
		drag.offset = dy > 0 ? dy : dy / 4;
		this.panel.style.transform = `translateY(${drag.offset}px)`;
		this.scrim.style.opacity = String(1 - Math.max(0, dy) / drag.height);
	}

	drag_release() {
		const drag = this.drag;
		if (!drag) return;
		this.drag_end();
		const dy = drag.last_y - drag.start_y;
		const next = this.next_snap(dy, drag.velocity, drag.height);
		if (next === "close" && this.dismissible) {
			this.close("swipe");
			return;
		}
		this.panel.style.transform = "";
		this.scrim.style.opacity = "";
		if (next && next !== "close") this.set_height(next);
	}

	drag_end() {
		if (!this.drag) return;
		const { el } = this.drag;
		this.drag = null;
		this.panel?.removeAttribute("data-dragging");
		el.removeEventListener("pointermove", this.ondragmove);
		el.removeEventListener("pointerup", this.ondragup);
		el.removeEventListener("pointercancel", this.ondragup);
		el.removeEventListener("lostpointercapture", this.ondragup);
	}

	next_snap(dy, velocity, height) {
		const up = dy < -EXPAND_DRAG || velocity < -FLICK;
		const down = dy > 0 && (dy > height * CLOSE_SHARE || velocity > FLICK);
		const index = this.snap_points.indexOf(this.current_height);
		if (index === -1) return down ? "close" : null;
		if (up && index < this.snap_points.length - 1) return this.snap_points[index + 1];
		if (down) return index > 0 ? this.snap_points[index - 1] : "close";
		return null;
	}
};

/**
 * Convenience form: makes the trigger button and wires the sheet in one
 * call. Returns the trigger element (append it wherever); the instance is
 * on `.data("es-bottom-sheet")` when you need open/close/push.
 * @param {BottomSheetOpts} opts
 * @returns {JQuery}
 * @example toolbar.append(frappe.ui.bottom_sheet({
 *     button: { label: __("Sort"), icon: "arrow-down-wide-narrow" },
 *     title: __("Sort by"),
 *     options: sort_options,
 * }));
 */
frappe.ui.bottom_sheet = function (opts = {}) {
	const sheet = new frappe.ui.BottomSheet({ button: {}, ...opts });
	sheet.$trigger.data("es-bottom-sheet", sheet);
	return sheet.$trigger;
};

export default frappe.ui.bottom_sheet;
