import { validated, safe_href, shortcut_keys } from "./utils.js";
import { place } from "./position.js";

/**
 * Internal engine shared by frappe.ui.Dropdown and frappe.ui.ContextMenu:
 * renders .es-menu panels, positions them against an anchor, and owns
 * keyboard navigation and the submenu stack. Not a public API.
 *
 * How it fits together:
 * - The owner (Dropdown/ContextMenu) creates one MenuTree every time the
 *   menu opens, and throws it away when it closes. Nothing here is reused
 *   between opens — that's why condition() and function-options are always
 *   fresh.
 * - `this.panels` is the chain of open panels: panels[0] is the root menu,
 *   panels[1] a submenu inside it, panels[2] a submenu inside that, and so
 *   on. Only one branch can be open at a time.
 * - Each panel is appended to <body> (not inside the trigger's parent), so
 *   it can never be clipped by an overflow:hidden container. That's also
 *   why positioning is done in fixed viewport coordinates.
 * - Focus IS the highlight: hovering or arrowing to a row focuses its
 *   element, and the focusin handler moves the data-highlighted attribute.
 *   One source of truth, so the pointer and the keyboard can't ever mark
 *   two rows at once.
 *
 * Rows are built with createElement + textContent, so labels can never
 * smuggle markup — there is no HTML channel here at all.
 *
 * Async: the root options (via a function returning a promise, or a bare
 * promise) and function submenus may resolve later — the panel opens with a
 * loading placeholder and fill() swaps the rows in when the data lands,
 * re-measuring the position. Late resolutions after a close are discarded.
 */

/**
 * @typedef {Object} MenuItem
 * @property {string} label Row text. Rendered as text, never HTML.
 * @property {string} [icon] Lucide icon name shown before the label.
 * @property {string} [description] Smaller second line under the label.
 * @property {"gray"|"red"} [theme="gray"] "red" for destructive rows.
 * @property {boolean} [selected] Marks the current choice (visual only).
 * @property {boolean} [disabled] Inert row, skipped by keyboard navigation.
 * @property {string|string[]} [shortcut] Keyboard hint, display only — pass the raw combo ("ctrl+p") and each key becomes its OS form (⌘P on Mac, Ctrl+P elsewhere), or an array of already-formatted keys. Binding the keys stays the caller's job (frappe.ui.keys.add_shortcut).
 * @property {function} [onclick] Called with the click event. The menu closes after.
 * @property {string} [href] Renders the row as a link. Code-running schemes are refused.
 * @property {function} [condition] Checked on every open; return false to hide the row.
 * @property {string} [css_class] Extra classes on the row element (responsive visibility hooks like visible-xs).
 * @property {MenuItem[]|function} [submenu] Nested rows — the row opens a side panel instead of acting. A function runs at hover-start (once per menu open, result cached) and may return the rows or a Promise of them; the panel shows a loading state until it settles.
 */

/**
 * @typedef {Object} MenuGroup
 * @property {string} group Heading text for the section.
 * @property {boolean} [hide_label] Keep the section border but hide the heading.
 * @property {MenuItem[]} options Rows in this section.
 */

const THEMES = ["gray", "red"];

function is_thenable(value) {
	return !!value && typeof value.then === "function";
}

const SUBMENU_OFFSET = 4;
const SUBMENU_OPEN_DELAY = 150;
const EXIT_MS = 140;
const TYPEAHEAD_RESET_MS = 1000;
// how long the safe-triangle grace lasts after leaving a submenu row —
// enough to cross the menu diagonally, short enough that a change of mind
// (parking on a sibling) recovers quickly. Same value radix uses.
const GRACE_MS = 300;
// widen the triangle a little around the exit point and the panel corners so
// pointer paths that hug an edge stay inside it
const GRACE_PAD = 5;

// ray-casting point-in-polygon; polygon is [[x, y], ...]
function point_in_polygon(x, y, polygon) {
	let inside = false;
	for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
		const [xi, yi] = polygon[i];
		const [xj, yj] = polygon[j];
		if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
			inside = !inside;
		}
	}
	return inside;
}

function is_group(entry) {
	return entry && typeof entry === "object" && "group" in entry && Array.isArray(entry.options);
}

// flatten the mixed list into explicit groups (loose items become unlabeled
// groups in source order), dropping condition()-hidden rows and empty groups
export function normalize_options(options) {
	const groups = [];
	let current = null;
	const visible = (items) =>
		(items || []).filter(Boolean).filter((item) => (item.condition ? item.condition() : true));

	const flush = () => {
		if (current && current.options.length) groups.push(current);
		current = null;
	};

	for (const entry of options || []) {
		if (!entry) continue;
		if (is_group(entry)) {
			flush();
			const items = visible(entry.options);
			if (!items.length) continue;
			groups.push({
				group: entry.group || "",
				hide_label: !!entry.hide_label,
				options: items,
			});
			continue;
		}
		if (entry.condition && !entry.condition()) continue;
		if (!current) current = { group: "", hide_label: true, options: [] };
		current.options.push(entry);
	}
	flush();

	// theme is validated later, once per row, in build_item — no second
	// pass here or a bad theme would warn twice
	return groups;
}

// icon names end up inside svg use hrefs, so only plain names pass
function icon_html(name, svg_class, component) {
	if (typeof name !== "string" || !/^[a-z0-9-]+$/i.test(name)) {
		console.warn(`frappe.ui.${component}: icons take a lucide icon name, got "${name}"`);
		return "";
	}
	return frappe.utils.icon(name, "sm", "", "", svg_class, true);
}

// Underline the first free a-z letter of the label so Alt+letter can activate
// the row (skipping letters earlier rows in the same panel already took).
// Built from text nodes + a span, never innerHTML, so labels still can't
// smuggle markup. Returns the chosen letter, or null when none is free.
function assign_mnemonic(label_el, text, taken) {
	for (let i = 0; i < text.length; i++) {
		const letter = text[i].toLowerCase();
		if (letter < "a" || letter > "z" || taken.has(letter)) continue;
		taken.add(letter);
		const mark = document.createElement("span");
		mark.className = "es-menu__mnemonic";
		mark.textContent = text[i];
		label_el.append(
			document.createTextNode(text.slice(0, i)),
			mark,
			document.createTextNode(text.slice(i + 1))
		);
		return letter;
	}
	label_el.textContent = text;
	return null;
}

function build_item(item, { reserve_icon_space, component, taken }) {
	// a disabled row is always a real disabled <button>, never a link — a
	// disabled <a> keeps a working href that a screen reader's link list or
	// a script click would still follow, right past the disabled state
	const href = item.submenu || item.disabled ? null : safe_href(item.href, component);
	const el = document.createElement(href ? "a" : "button");
	el.className = "es-menu__item";
	if (item.css_class) el.className += ` ${item.css_class}`;
	el.setAttribute("role", "menuitem");
	el.setAttribute("tabindex", "-1");
	if (href) el.href = href;
	else el.type = "button";

	if (item.disabled) {
		el.setAttribute("data-disabled", "");
		el.setAttribute("aria-disabled", "true");
		el.disabled = true;
	}
	if (item.selected) el.setAttribute("data-state", "checked");
	if (validated(item.theme, THEMES, "theme", component) === "red") {
		el.setAttribute("data-theme", "red");
	}

	if (item.icon) {
		el.insertAdjacentHTML("beforeend", icon_html(item.icon, "", component));
	} else if (reserve_icon_space) {
		const space = document.createElement("span");
		space.className = "es-menu__icon-space";
		space.setAttribute("aria-hidden", "true");
		el.appendChild(space);
	}

	const label = document.createElement("span");
	label.className = "es-menu__label";
	const label_text = item.label || "";
	// disabled rows can't be activated, so they get no mnemonic; rows with
	// an accelerator keep it as their only key path (the legacy desk rule —
	// it also leaves the letter pool for shortcut-less rows)
	let mnemonic = null;
	if (taken && label_text && !item.disabled && !item.shortcut) {
		mnemonic = assign_mnemonic(label, label_text, taken);
	} else {
		label.textContent = label_text;
	}
	if (item.description) {
		const description = document.createElement("span");
		description.className = "es-menu__description";
		description.textContent = item.description;
		label.appendChild(description);
	}
	el.appendChild(label);

	if (item.shortcut) {
		const shortcut = document.createElement("span");
		shortcut.className = "es-menu__shortcut";
		shortcut.setAttribute("aria-hidden", "true");
		for (const key of shortcut_keys(item.shortcut)) {
			const kbd = document.createElement("kbd");
			kbd.textContent = key;
			shortcut.appendChild(kbd);
		}
		el.appendChild(shortcut);
	}

	if (item.submenu) {
		el.setAttribute("aria-haspopup", "menu");
		el.setAttribute("aria-expanded", "false");
		el.insertAdjacentHTML(
			"beforeend",
			icon_html("chevron-right", "es-menu__chevron", component)
		);
	}

	return { el, mnemonic };
}

// fill a bare panel with its group/row elements (or the empty text) and
// return the rows. Separate from build_panel so a panel that opened in its
// loading state can be filled in place when the async items arrive.
function render_content(panel, groups, { empty_text, component }) {
	const rows = []; // [{ el, item, mnemonic }] in visual order
	const taken = new Set(); // Alt-mnemonic letters, unique within a panel

	if (!groups.length) {
		const empty = document.createElement("div");
		empty.className = "es-menu__empty";
		empty.textContent = empty_text || __("No options");
		panel.appendChild(empty);
		return rows;
	}

	for (const group of groups) {
		const group_el = document.createElement("div");
		group_el.className = "es-menu__group";
		group_el.setAttribute("role", "group");

		if (group.group && !group.hide_label) {
			const label = document.createElement("div");
			label.className = "es-menu__group-label";
			label.id = frappe.utils.get_random(8);
			label.textContent = group.group;
			group_el.setAttribute("aria-labelledby", label.id);
			group_el.appendChild(label);
		}

		// when any row in a group has an icon, iconless rows reserve the
		// same space so the labels line up
		const reserve_icon_space = group.options.some((item) => item.icon);

		for (const item of group.options) {
			const { el, mnemonic } = build_item(item, {
				reserve_icon_space,
				component,
				taken,
			});
			rows.push({ el, item, mnemonic });
			group_el.appendChild(el);
		}
		panel.appendChild(group_el);
	}

	return rows;
}

// the placeholder shown while async items load: a spinner + "Loading...",
// inert like the empty state (no rows, so keyboard navigation has nothing
// to land on; Escape and outside-click work through the panel as usual)
function render_loading(panel) {
	const loading = document.createElement("div");
	loading.className = "es-menu__loading";
	const spinner = document.createElement("span");
	spinner.className = "es-spinner";
	spinner.setAttribute("aria-hidden", "true");
	const text = document.createElement("span");
	text.textContent = __("Loading...");
	loading.append(spinner, text);
	panel.appendChild(loading);
	panel.setAttribute("aria-busy", "true");
}

// `groups === null` means the items are still loading (async source) — the
// panel opens with the loading placeholder and fill() swaps the rows in
function build_panel(groups, { empty_text, component }) {
	const panel = document.createElement("div");
	panel.className = "es-menu";
	panel.setAttribute("role", "menu");
	panel.setAttribute("tabindex", "-1");

	if (groups === null) {
		render_loading(panel);
		return { panel, rows: [] };
	}

	const rows = render_content(panel, groups, { empty_text, component });
	return { panel, rows };
}

/**
 * One open menu: the root panel plus any open submenu panels.
 * The owner (Dropdown/ContextMenu) creates a MenuTree per open and gets an
 * on_close(reason) callback; reasons are "activate", "escape", "outside",
 * "tab" and "owner" (closed programmatically).
 */
export class MenuTree {
	constructor({ options, empty_text, component, anchor, ignore, on_close, lock_scroll }) {
		this.options = options;
		this.empty_text = empty_text;
		this.component = component || "dropdown";
		this.anchor = anchor; // () => DOMRect of the trigger / pointer
		this.ignore = ignore || []; // elements whose clicks don't count as "outside"
		this.on_close = on_close;
		this.lock_scroll = lock_scroll;
		this.panels = []; // [{ panel, rows, anchor, side, align, offset, parent_row }]
		this.closed = false;
		// function submenus resolve once per menu open: row -> items or the
		// pending promise (see get_submenu_items)
		this.submenu_cache = new Map();
		this.submenu_timer = null;
		// the safe triangle: while the pointer travels from a submenu row
		// toward its open panel, sibling rows must not steal the highlight or
		// close the panel. { polygon, expiry } or null.
		this.grace = null;
		this.typeahead_buffer = "";
		this.typeahead_timer = null;
		this.mnemonics_visible = false; // Alt held → underlines showing
	}

	open({ side = "bottom", align = "start", offset = 4, motion = "animated", focus = null }) {
		// options can be a function so the menu reflects right-now state
		// (which row was clicked, what's selected); it runs on every open.
		// A promise (or a function returning one) opens the menu in its
		// loading state, and the rows fill in when it settles.
		const value = typeof this.options === "function" ? this.options() : this.options;
		const mount_opts = { anchor: this.anchor, side, align, offset, motion };
		let entry;
		if (is_thenable(value)) {
			entry = this.mount(null, mount_opts);
			entry.pending_focus = focus === "first" || focus === "last" ? focus : null;
			value.then(
				(items) => this.fill(entry, normalize_options(items)),
				(error) => this.fill_failed(entry, error)
			);
		} else {
			entry = this.mount(normalize_options(value), mount_opts);
		}

		// pressing down anywhere that isn't a panel (or the trigger, which
		// handles its own clicks) closes the menu
		this.onpointerdown = (e) => {
			const inside = [...this.panels.map((p) => p.panel), ...this.ignore].some(
				(el) => el && (el === e.target || el.contains(e.target))
			);
			if (!inside) this.close("outside");
		};
		document.addEventListener("pointerdown", this.onpointerdown, true);

		// if the page scrolls or the window resizes while open, the menu
		// follows its trigger instead of floating loose
		this.onreposition = () => this.reposition();
		window.addEventListener("resize", this.onreposition);
		document.addEventListener("scroll", this.onreposition, { capture: true, passive: true });

		// the safe triangle is judged on every pointer move (cheap: a null
		// check when no grace is active)
		this.ongracemove = (e) => this.handle_grace_move(e);
		document.addEventListener("pointermove", this.ongracemove, true);

		if (this.lock_scroll) {
			// context menus freeze the page: a stray trackpad flick shouldn't
			// scroll the content out from under the menu. Scroll events can't
			// be canceled, so block wheel/touchmove instead — except inside
			// the menu itself, which may scroll.
			this.onwheel = (e) => {
				if (e.target instanceof Element && e.target.closest('[role="menu"]')) return;
				e.preventDefault();
			};
			window.addEventListener("wheel", this.onwheel, { passive: false, capture: true });
			window.addEventListener("touchmove", this.onwheel, { passive: false, capture: true });
		}

		// holding Alt underlines each row's mnemonic letter; Alt+letter then
		// activates that row. Capture phase so the reveal still fires even
		// though handle_keydown stops the bare Alt keydown from bubbling to
		// frappe's global handler.
		this.onaltkey = (e) => {
			if (e.key === "Alt") this.show_mnemonics(e.type === "keydown");
		};
		document.addEventListener("keydown", this.onaltkey, true);
		document.addEventListener("keyup", this.onaltkey, true);
		// Alt+Tab away can swallow the keyup — clear on blur so the underlines
		// don't get stuck on
		this.onblur = () => this.show_mnemonics(false);
		window.addEventListener("blur", this.onblur);

		// keyboard opens land on a row right away (ArrowDown = first,
		// ArrowUp = last); mouse opens just focus the panel so keys work
		// without stealing the highlight from wherever the pointer is. An
		// async panel has no rows yet — focus the panel so Escape works, and
		// fill() honors pending_focus when the rows arrive
		if (focus === "first" && entry.rows.length) this.focus_step(entry, 1);
		else if (focus === "last" && entry.rows.length) this.focus_step(entry, -1);
		else entry.panel.focus({ preventScroll: true });
	}

	// build one panel and put it on screen; used for the root menu and for
	// every submenu
	mount(groups, { anchor, side, align, offset, motion, parent_row = null }) {
		const { panel, rows } = build_panel(groups, {
			empty_text: this.empty_text,
			component: this.component,
		});
		const entry = { panel, rows, anchor, side, align, offset, parent_row };

		panel.setAttribute("data-motion", motion);
		this.bind_panel(entry);
		// order matters: the panel must be in the DOM before place() can
		// measure it, and data-state="open" starts the enter animation only
		// after it's already in position
		document.body.appendChild(panel);
		place(panel, anchor(), side, align, offset);
		panel.setAttribute("data-state", "open");

		if (parent_row) {
			parent_row.setAttribute("data-state", "open");
			parent_row.setAttribute("aria-expanded", "true");
		}
		this.panels.push(entry);
		// the reveal follows the deepest panel, so opening a submenu while
		// Alt is held moves the underlines onto it
		this.update_mnemonic_panels();
		return entry;
	}

	bind_panel(entry) {
		this.bind_rows(entry);

		// reaching any panel surface — including its padding and group labels,
		// not just a row — means the pointer arrived at a menu: a close
		// pending from a previously hovered row must not fire under the
		// cursor, and any safe-triangle journey is complete
		entry.panel.addEventListener("pointerenter", (e) => {
			// real pointerenter doesn't bubble — the panel only ever sees
			// itself as target. Synthetic events (tests) may bubble up from a
			// row; those are the row's business, and clearing here would kill
			// the submenu-open timer the row just scheduled.
			if (e.target !== entry.panel) return;
			clearTimeout(this.submenu_timer);
			this.grace = null;
		});

		// whichever row has focus carries the highlight — this is the only
		// place data-highlighted is ever set. Reads entry.rows live (not a
		// captured copy) so an async fill's new rows are covered too.
		entry.panel.addEventListener("focusin", (e) => {
			for (const row of entry.rows) {
				row.el.toggleAttribute("data-highlighted", row.el === e.target);
			}
		});

		// key presses on focused rows bubble up to the panel, so one
		// listener per panel covers all of its rows
		entry.panel.addEventListener("keydown", (e) => this.handle_keydown(entry, e));
	}

	// per-row listeners; called at mount and again after an async fill
	// replaces a panel's rows
	bind_rows(entry) {
		for (const row of entry.rows) {
			row.el.addEventListener("click", (e) => {
				// disabled buttons don't fire click, but a scripted or AT
				// activation can still reach here — never act on a disabled row
				if (row.item.disabled) {
					e.preventDefault();
					return;
				}
				// a submenu row doesn't act — it opens its panel and the
				// menu stays up. A normal row acts and everything closes.
				if (row.item.submenu) {
					e.preventDefault();
					this.open_submenu(entry, row, { focus: false });
					return;
				}
				// link rows also navigate here, natively — nothing to do
				row.item.onclick && row.item.onclick(e);
				this.close("activate");
			});

			// the highlight follows the pointer; focus follows so keyboard
			// navigation continues from where the mouse was. While the safe
			// triangle is active the pointer is on its way to an open
			// submenu — siblings crossed en route must not steal the
			// highlight or schedule anything.
			row.el.addEventListener("pointerenter", (e) => {
				if (this.in_grace(e)) return;
				row.el.focus({ preventScroll: true });
				this.schedule_submenu(entry, row);
			});

			// leaving a row whose submenu is open starts the safe triangle:
			// exit point + the panel's near corners
			row.el.addEventListener("pointerleave", (e) => {
				this.start_grace(entry, row, e);
			});
		}
	}

	// ---- the safe triangle (hover grace toward an open submenu) ----

	start_grace(entry, row, e) {
		const depth = this.panels.indexOf(entry);
		const child = this.panels[depth + 1];
		// only when THIS row's submenu is open
		if (!child || child.parent_row !== row.el) return;

		const rect = child.panel.getBoundingClientRect();
		// the triangle spans from the exit point (nudged back so edge-hugging
		// paths stay inside) to the panel's near edge, padded top and bottom
		const opens_left = rect.left < e.clientX;
		const near_x = opens_left ? rect.right : rect.left;
		const origin_x = e.clientX + (opens_left ? GRACE_PAD : -GRACE_PAD);
		this.grace = {
			polygon: [
				[origin_x, e.clientY],
				[near_x, rect.top - GRACE_PAD],
				[near_x, rect.bottom + GRACE_PAD],
			],
			expiry: Date.now() + GRACE_MS,
		};
	}

	in_grace(e) {
		if (!this.grace) return false;
		if (Date.now() > this.grace.expiry) {
			this.grace = null;
			return false;
		}
		return point_in_polygon(e.clientX, e.clientY, this.grace.polygon);
	}

	// once the pointer leaves the triangle (or the grace expires), hand
	// control back to whatever row it is actually on — pointerenter already
	// fired and was suppressed, so it won't fire again without this
	handle_grace_move(e) {
		if (!this.grace) return;
		if (
			Date.now() <= this.grace.expiry &&
			point_in_polygon(e.clientX, e.clientY, this.grace.polygon)
		) {
			return;
		}
		this.grace = null;
		const row_el = e.target instanceof Element && e.target.closest(".es-menu__item");
		if (!row_el) return;
		for (const entry of this.panels) {
			const row = entry.rows.find((r) => r.el === row_el);
			if (row) {
				row.el.focus({ preventScroll: true });
				this.schedule_submenu(entry, row);
				return;
			}
		}
	}

	// swap a loading panel's placeholder for the resolved rows, in place.
	// Late resolutions are dropped: the whole menu may have closed, or just
	// that submenu panel (hover moved on) — either way there's nothing to do.
	fill(entry, groups) {
		if (this.closed || !this.panels.includes(entry)) return;
		// read focus before replaceChildren blurs whatever held it
		const had_focus =
			entry.panel === document.activeElement || entry.panel.contains(document.activeElement);
		entry.panel.replaceChildren();
		entry.panel.removeAttribute("aria-busy");
		entry.rows = render_content(entry.panel, groups, {
			empty_text: this.empty_text,
			component: this.component,
		});
		this.bind_rows(entry);
		// the panel's size just changed — measure, flip and clamp again
		place(entry.panel, entry.anchor(), entry.side, entry.align, entry.offset);
		if (entry.pending_focus) {
			this.focus_step(entry, entry.pending_focus === "last" ? -1 : 1);
			entry.pending_focus = null;
		} else if (had_focus) {
			entry.panel.focus({ preventScroll: true });
		}
	}

	// async items rejected: keep the panel up with an inert notice — a dead
	// hover with no feedback would look like the menu is broken
	fill_failed(entry, error) {
		if (this.closed || !this.panels.includes(entry)) return;
		console.warn(`frappe.ui.${this.component}: menu items failed to load`, error);
		entry.panel.replaceChildren();
		entry.panel.removeAttribute("aria-busy");
		const failed = document.createElement("div");
		failed.className = "es-menu__empty";
		failed.textContent = __("Couldn't load options");
		entry.panel.appendChild(failed);
		entry.rows = [];
		entry.pending_focus = null;
		place(entry.panel, entry.anchor(), entry.side, entry.align, entry.offset);
	}

	// all keyboard behavior for one panel. `entry` is the panel the focused
	// row lives in, so submenus get the same treatment as the root.
	handle_keydown(entry, e) {
		const handled = () => {
			e.preventDefault();
			e.stopPropagation();
		};

		// in RTL, submenus open toward the left, so the "step in" and
		// "step out" arrows swap with them (only these two — up/down and
		// everything else are direction-free)
		let key = e.key;
		if (frappe.utils.is_rtl()) {
			if (key === "ArrowRight") key = "ArrowLeft";
			else if (key === "ArrowLeft") key = "ArrowRight";
		}

		switch (key) {
			case "ArrowDown":
				handled();
				this.focus_step(entry, 1);
				break;
			case "ArrowUp":
				handled();
				this.focus_step(entry, -1);
				break;
			case "Home":
				handled();
				this.focus_step(entry, 1, "edge");
				break;
			case "End":
				handled();
				this.focus_step(entry, -1, "edge");
				break;
			case "ArrowRight": {
				// only does something on a submenu row: open it and step in
				const row = entry.rows.find((r) => r.el === document.activeElement);
				if (row && row.item.submenu) {
					handled();
					this.open_submenu(entry, row, { focus: true });
				}
				break;
			}
			case "ArrowLeft": {
				// step back out of a submenu (no-op in the root menu, which
				// has no parent_row)
				if (entry.parent_row) {
					handled();
					this.close_submenus_from(this.panels.indexOf(entry));
					entry.parent_row.focus();
				}
				break;
			}
			case "Escape":
				handled();
				this.close("escape");
				break;
			case "Tab":
				// don't trap focus — close and let Tab move on naturally
				this.close("tab");
				break;
			default: {
				// Alt+letter activates the row with that mnemonic (the letter
				// underlined while Alt is held). Only plain Alt; Alt+Ctrl etc.
				// falls through to the modifier trap below. e.code, not e.key,
				// because Alt rewrites e.key to a special glyph on macOS.
				// Always acts on the deepest open panel — that's the only one
				// showing its mnemonics — no matter which panel has focus.
				if (e.altKey && !e.ctrlKey && !e.metaKey) {
					const match = e.code.match(/^Key([A-Z])$/);
					const letter = match && match[1].toLowerCase();
					const active = this.panels[this.panels.length - 1];
					const row =
						letter &&
						active &&
						active.rows.find((r) => r.mnemonic === letter && !r.item.disabled);
					if (row) {
						handled();
						// a submenu row steps into its panel (keyboard-driven);
						// a leaf acts and closes, same as a click
						if (row.item.submenu) this.open_submenu(active, row, { focus: true });
						else row.el.click();
						break;
					}
				}
				// a modifier combo (Ctrl+S, Ctrl+K, ...) would otherwise
				// bubble to frappe's global keyboard handler and fire behind
				// the open menu. Stop it reaching that handler, but leave the
				// browser's own default (Ctrl+C, reload, ...) alone.
				if (e.ctrlKey || e.metaKey || e.altKey) {
					e.stopPropagation();
					break;
				}
				// everything else: single printable characters feed the
				// type-to-search
				if (e.key.length !== 1) break;
				if (e.key === " " && !this.typeahead_buffer) {
					// plain Space activates the focused row; buttons do that
					// natively, links don't
					const row = entry.rows.find((r) => r.el === document.activeElement);
					if (row && row.el.tagName === "A") {
						handled();
						row.el.click();
					}
					break;
				}
				// any other printable key searches ("de" jumps to Delete);
				// preventing default keeps Space from scrolling or clicking
				handled();
				this.typeahead(entry, e.key);
				break;
			}
		}
	}

	// type-to-jump: letters collect into a short-lived search that focuses
	// the first row whose label starts with it; pressing one letter
	// repeatedly cycles through that letter's matches
	typeahead(entry, char) {
		// a second of quiet forgets the search and the next key starts fresh
		clearTimeout(this.typeahead_timer);
		this.typeahead_timer = setTimeout(() => (this.typeahead_buffer = ""), TYPEAHEAD_RESET_MS);
		this.typeahead_buffer += char;

		const rows = entry.rows.filter((row) => !row.item.disabled && row.item.label);
		if (!rows.length) return;

		// "ddd" means the user is tapping d to walk through the D-items,
		// not searching for a row literally called "ddd"
		const repeated =
			this.typeahead_buffer.length > 1 &&
			[...this.typeahead_buffer].every((c) => c === this.typeahead_buffer[0]);
		const search = (repeated ? this.typeahead_buffer[0] : this.typeahead_buffer).toLowerCase();

		// a growing search keeps matching the current row ("d", then "de");
		// a single letter moves past it so repeats cycle
		const current = rows.findIndex((row) => row.el === document.activeElement);
		const start = current === -1 ? 0 : current + (search.length === 1 ? 1 : 0);

		for (let i = 0; i < rows.length; i++) {
			const row = rows[(start + i) % rows.length];
			if (row.item.label.toLowerCase().startsWith(search)) {
				row.el.focus();
				return;
			}
		}
	}

	// move focus by direction, skipping disabled rows, wrapping around;
	// "edge" jumps straight to the first (direction 1) or last (-1) row
	focus_step(entry, direction, edge) {
		const rows = entry.rows.filter((row) => !row.item.disabled);
		if (!rows.length) return;
		let index;
		if (edge === "edge") {
			index = direction > 0 ? 0 : rows.length - 1;
		} else {
			const active = rows.findIndex((row) => row.el === document.activeElement);
			index =
				active >= 0
					? (active + direction + rows.length) % rows.length
					: direction > 0
					? 0
					: rows.length - 1;
		}
		// no preventScroll: in a scrolling panel the row must come into view
		// (the panel is position: fixed, so the page itself never moves)
		rows[index].el.focus();
	}

	// hovering a submenu row opens its panel after a beat; hovering any
	// other row closes panels deeper than this one
	schedule_submenu(entry, row) {
		clearTimeout(this.submenu_timer);
		// a function submenu starts resolving at hover-START, before the open
		// delay — a fast source is ready before the panel ever shows, so the
		// loading state often never appears at all
		if (row.item.submenu) this.get_submenu_items(row);
		const depth = this.panels.indexOf(entry);
		this.submenu_timer = setTimeout(() => {
			if (this.closed) return;
			if (row.item.submenu) this.open_submenu(entry, row, { focus: false });
			else this.close_submenus_from(depth + 1);
		}, SUBMENU_OPEN_DELAY);
	}

	// a submenu's items: an array passes through; a function runs once per
	// menu open and its result — value or promise — is cached, so hovering
	// away and back doesn't refetch. When a promise resolves, the cache is
	// swapped to the plain items so the next open of that row is synchronous.
	// A rejected promise stays cached (no retry until the next menu open);
	// the rejection itself is handled where the panel consumes it.
	get_submenu_items(row) {
		const source = row.item.submenu;
		if (typeof source !== "function") return source;
		if (!this.submenu_cache.has(row)) {
			const value = source();
			this.submenu_cache.set(row, value);
			if (is_thenable(value)) {
				value.then(
					(items) => this.submenu_cache.set(row, items),
					() => {} // fill_failed reports it; this guard just keeps the prefetch handled
				);
			}
		}
		return this.submenu_cache.get(row);
	}

	open_submenu(parent_entry, row, { focus }) {
		// this row's submenu is already open — just step into it if asked
		const depth = this.panels.indexOf(parent_entry);
		const already = this.panels[depth + 1];
		if (already && already.parent_row === row.el) {
			if (focus && already.rows.length) this.focus_step(already, 1);
			return;
		}
		// a sibling's submenu may be open — only one branch at a time
		this.close_submenus_from(depth + 1);

		const source = this.get_submenu_items(row);
		const mount_opts = {
			// the submenu hangs off its row and follows it around, opening
			// toward the reading direction (left in RTL)
			anchor: () => row.el.getBoundingClientRect(),
			side: frappe.utils.is_rtl() ? "left" : "right",
			align: "start",
			offset: SUBMENU_OFFSET,
			motion: "animated",
			parent_row: row.el,
		};
		let entry;
		if (is_thenable(source)) {
			entry = this.mount(null, mount_opts);
			if (focus) entry.pending_focus = "first";
			source.then(
				(items) => this.fill(entry, normalize_options(items)),
				(error) => this.fill_failed(entry, error)
			);
		} else {
			entry = this.mount(normalize_options(source), mount_opts);
			// keyboard opens step onto the first row; hover opens leave focus
			// on the parent row until the pointer moves in
			if (focus) this.focus_step(entry, 1);
		}
	}

	// close every panel deeper than `depth` (the Math.max keeps the root
	// panel safe — only close() may take that one down)
	close_submenus_from(depth) {
		while (this.panels.length > Math.max(depth, 1)) {
			const entry = this.panels.pop();
			if (entry.parent_row) {
				entry.parent_row.removeAttribute("data-state");
				entry.parent_row.setAttribute("aria-expanded", "false");
			}
			this.retire(entry.panel);
		}
		// reveal moves back onto whatever panel is deepest now
		this.update_mnemonic_panels();
	}

	// show or hide the Alt mnemonic underlines
	show_mnemonics(show) {
		this.mnemonics_visible = show;
		this.update_mnemonic_panels();
	}

	// only the deepest open panel reveals its mnemonics — with a submenu open,
	// the parent's letters aren't live, so the same letter can't mean two
	// different rows. Called whenever the panel stack or Alt state changes.
	update_mnemonic_panels() {
		const deepest = this.panels.length - 1;
		this.panels.forEach((entry, i) => {
			entry.panel.toggleAttribute("data-alt", this.mnemonics_visible && i === deepest);
		});
	}

	// re-anchor every open panel; anchors are functions so each call reads
	// where the trigger/row is right now
	reposition() {
		for (const entry of this.panels) {
			place(entry.panel, entry.anchor(), entry.side, entry.align, entry.offset);
		}
	}

	// play the exit animation, then remove
	retire(panel) {
		panel.setAttribute("data-state", "closed");
		setTimeout(() => panel.remove(), EXIT_MS);
	}

	// tear the whole tree down. Safe to call twice — a click that also
	// lands on the trigger would otherwise close, then close again.
	close(reason) {
		if (this.closed) return;
		this.closed = true;
		clearTimeout(this.submenu_timer);
		clearTimeout(this.typeahead_timer);
		document.removeEventListener("keydown", this.onaltkey, true);
		document.removeEventListener("keyup", this.onaltkey, true);
		window.removeEventListener("blur", this.onblur);
		document.removeEventListener("pointerdown", this.onpointerdown, true);
		window.removeEventListener("resize", this.onreposition);
		document.removeEventListener("scroll", this.onreposition, { capture: true });
		document.removeEventListener("pointermove", this.ongracemove, true);
		this.grace = null;
		if (this.onwheel) {
			window.removeEventListener("wheel", this.onwheel, { capture: true });
			window.removeEventListener("touchmove", this.onwheel, { capture: true });
		}
		for (const entry of this.panels) this.retire(entry.panel);
		this.panels = [];
		this.on_close && this.on_close(reason);
	}
}
