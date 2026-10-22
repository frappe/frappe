// Flow's launcher: an icon that opens /flow in a panel (added by frappe/flow/launcher.py)

const STORE_KEY = "flow_launcher";
const FLOW_PATH = /^\/flow(\/|\?|$)/;
const NEW_CHAT = "/flow?new=1"; // bare /flow reopens its last chat
const ICON_SIZE = 44;
const GAP = 16;
const PANEL_WIDTH = 420;
const PANEL_HEIGHT = 680;
const MIN_WIDTH = 320;
const MIN_HEIGHT = 480; // room for a few lines between the headers and the composer
const MAX_DOCK_SHARE = 0.75; // of the window, so the page stays in view
const PHONE_WIDTH = 640; // narrower windows show the panel full screen
const NOTE_TIME = 8000; // ms the hide note and its Undo stay
// under the page's dialogs and toasts, which start at 1040 on Desk and 50 in frappe-ui apps
const LAYER = location.pathname.startsWith("/desk") ? 1035 : 45;
const EDGES = ["n", "e", "s", "w", "ne", "nw", "se", "sw"];
// Cmd/Ctrl keys a text box uses, kept in the chat; other shortcuts go to the page
const TEXT_KEYS = new Set([
	...["a", "b", "c", "i", "u", "v", "x", "y", "z"],
	...["backspace", "delete", "enter", "home", "end"],
	...["arrowleft", "arrowright", "arrowup", "arrowdown"],
]);

const svg = (paths, cls = "") =>
	`<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${paths}</svg>`;
const FLOW_MARK = svg(
	'<path d="M3.2 2.95H14.4A6.4 6.4 0 0 1 20.8 9.35V13.35A6.4 6.4 0 0 1 14.4 19.75H9.6A6.4 6.4 0 0 1 3.2 13.35V8.45H5.6V13.35A4 4 0 0 0 9.6 17.35H14.4A4 4 0 0 0 18.4 13.35V9.35A4 4 0 0 0 14.4 5.35H3.2Z"/><circle cx="9.1" cy="10.8" r="1.65"/><circle cx="14.5" cy="10.8" r="1.65"/>',
	"mark"
);
// lucide's panel-left, panel-right, picture-in-picture-2, minus, maximize, minimize and x
const ICONS = {
	left: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
	right: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M15 3v18"/>',
	float: '<path d="M21 9V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10c0 1.1.9 2 2 2h4"/><rect width="10" height="7" x="12" y="13" rx="2"/>',
	minimize: '<path d="M5 12h14"/>',
	expand: '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
	shrink: '<path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>',
	close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
};

class FlowLauncher {
	constructor() {
		this.state = load_state();
		this.turned_off = false; // hidden by the user on this page
		this.make();
		this.bind();
		this.place();
		if (this.state.open) this.open({ focus: false });
	}

	make() {
		this.host = document.createElement("flow-launcher");
		const root = this.host.attachShadow({ mode: "open" });
		root.innerHTML = `<style>${STYLE}</style>
			<button class="icon" type="button" title="Flow" aria-label="Open Flow">${FLOW_MARK}</button>
			<div class="menu" role="menu" popover>
				<button type="button" role="menuitem">Hide Flow icon</button>
			</div>
			<div class="note" role="status" hidden>
				<span><strong>Flow icon hidden</strong>Turn it back on in <a href="/flow">Flow › Settings</a></span>
				<button class="undo" type="button">Undo</button>
				<button class="dismiss" type="button" aria-label="Close">${svg(ICONS.close)}</button>
			</div>
			<div class="preview" hidden></div>
			<div class="panel" role="dialog" aria-label="Flow" inert>
				<div class="window">
					<div class="bar">
						<span class="title">${FLOW_MARK}Flow</span>
						<button class="dock" type="button"></button>
						<button class="full" type="button"></button>
						<button class="minimize" type="button"></button>
						<button class="close" type="button"></button>
					</div>
				</div>
				<div class="shield"></div>
				${EDGES.map((edge) => `<div class="edge" data-edge="${edge}"></div>`).join("")}
			</div>`;
		this.icon = root.querySelector(".icon");
		this.menu = root.querySelector(".menu");
		this.note = root.querySelector(".note");
		this.preview = root.querySelector(".preview");
		this.panel = root.querySelector(".panel");
		this.bar = root.querySelector(".bar");
		this.dock_button = root.querySelector(".dock");
		this.full_button = root.querySelector(".full");
		set_button(root.querySelector(".minimize"), "minimize", "Minimize");
		set_button(root.querySelector(".close"), "close", "Close");
		document.body.append(this.host);
		on_theme_change(document.documentElement, () => this.sync_theme());
	}

	bind() {
		this.icon.addEventListener("pointerdown", (event) => this.drag_icon(event));
		// a drag ends in a click too
		this.icon.addEventListener("click", () => {
			if (!this.icon_dragged) this.open();
			this.icon_dragged = false;
		});
		this.icon.addEventListener("contextmenu", (event) => this.show_menu(event));
		this.menu.querySelector("button").addEventListener("click", () => this.hide_icon());
		this.note.querySelector(".undo").addEventListener("click", () => this.show_icon());
		this.note
			.querySelector(".dismiss")
			.addEventListener("click", () => (this.note.hidden = true));
		this.note.addEventListener("pointerenter", () => clearTimeout(this.note_timer));
		this.note.addEventListener("pointerleave", () => this.time_note());
		window.addEventListener("keydown", (event) => this.toggle_by_key(event), true);
		// a chat loading behind the closed panel takes the keyboard: give it back where it was
		const stolen = () =>
			!this.state.open && this.host.shadowRoot.activeElement === this.iframe;
		document.addEventListener("focusin", (event) => {
			if (!stolen()) this.page_focus = event.target;
		});
		window.addEventListener("blur", () => {
			if (!stolen()) return;
			const back = this.page_focus === this.host ? this.icon : this.page_focus;
			// a task later: taken back sooner, the frame keeps it
			setTimeout(() => {
				this.chat_focus = this.iframe.contentDocument?.activeElement; // for the next open
				this.iframe.blur();
				(back?.isConnected ? back : this.icon).focus();
			});
		});
		this.bar.addEventListener("pointerdown", (event) => {
			if (!event.target.closest("button")) this.drag_panel(event);
		});
		for (const edge of this.panel.querySelectorAll(".edge")) {
			edge.addEventListener("pointerdown", (event) =>
				this.resize_panel(event, edge.dataset.edge)
			);
		}
		this.dock_button.addEventListener("click", () => this.toggle_dock());
		this.panel.querySelector(".minimize").addEventListener("click", () => this.minimize());
		this.full_button.addEventListener("click", () => this.toggle_full());
		this.panel.querySelector(".close").addEventListener("click", () => this.close());
		window.addEventListener("resize", () => this.place());
		window.addEventListener("pagehide", () => this.save());
	}

	open({ focus = true } = {}) {
		this.state.open = true;
		this.state.rect ||= this.default_rect();
		if (!this.iframe) this.make_iframe();
		this.icon.hidden = true;
		this.panel.inert = false;
		this.place();
		this.save();
		if (focus) {
			this.iframe.focus();
			this.chat_focus?.focus();
		}
	}

	// hidden, not removed, so the chat doesn't lay itself out and animate in again
	minimize() {
		const focused = document.activeElement === this.host;
		this.chat_focus = null;
		this.state.open = false;
		this.panel.inert = true;
		this.icon.hidden = this.turned_off;
		if (focused) this.icon.focus();
		this.save();
	}

	// Cmd/Ctrl+I anywhere on the page; rich text keeps it for italics
	toggle_by_key(event) {
		if (!is_toggle_key(event) || event.composedPath()[0].isContentEditable) return;
		if (this.turned_off && !this.state.open) return;
		event.preventDefault();
		event.stopPropagation();
		if (this.state.open) this.minimize();
		else this.open();
	}

	// opens toward the middle of the window
	show_menu(event) {
		event.preventDefault();
		this.menu.showPopover();
		const { right = true, bottom = true } = this.state.icon || {};
		const icon = this.icon.getBoundingClientRect();
		const { width, height } = this.menu.getBoundingClientRect();
		this.menu.style.left = `${right ? icon.right - width : icon.left}px`;
		this.menu.style.top = `${bottom ? icon.top - height - 8 : icon.bottom + 8}px`;
		this.menu.querySelector("button").focus();
	}

	// an icon that couldn't be saved as hidden comes back
	hide_icon() {
		this.menu.hidePopover();
		this.turned_off = true;
		this.icon.hidden = true;
		this.show_note();
		save_hidden(true).then((saved) => saved || this.show_icon());
	}

	// Desk's own toast on Desk, else one like the apps' (frappe-ui)
	show_note() {
		if (!window.frappe?.ui?.toast) {
			this.note.hidden = false;
			this.time_note();
			return;
		}
		this.toast = window.frappe.ui.toast({
			message: "Flow icon hidden",
			description: "Turn it back on in Flow › Settings",
			action: { label: "Undo", onclick: () => this.show_icon() },
			duration: NOTE_TIME,
		});
		// Desk escapes the description; the link goes in after
		this.toast.$el
			.find(".es-toast__description")
			.html('Turn it back on in <a href="/flow">Flow › Settings</a>');
	}

	show_icon() {
		this.toast?.dismiss();
		clearTimeout(this.note_timer);
		this.note.hidden = true;
		this.turned_off = false;
		this.icon.hidden = false;
		this.icon.focus();
		save_hidden(false);
	}

	time_note() {
		clearTimeout(this.note_timer);
		this.note_timer = setTimeout(() => (this.note.hidden = true), NOTE_TIME);
	}

	// loads the next chat now, so it opens without a wait
	close() {
		this.minimize();
		this.iframe.remove();
		this.state.src = NEW_CHAT;
		this.make_iframe();
		this.save();
	}

	make_iframe() {
		this.iframe = document.createElement("iframe");
		this.iframe.title = "Flow";
		// the chat open on the last page
		this.iframe.src = FLOW_PATH.test(this.state.src) ? this.state.src : "/flow";
		this.iframe.addEventListener("load", (event) => {
			const chat = event.target.contentDocument?.defaultView;
			if (!chat) return; // an error page, which the page can't reach into
			// /flow applies its own saved theme as it loads; the page's wins
			on_theme_change(chat.document.documentElement, () => this.sync_theme());
			this.handle_keys(chat);
			// /flow's Settings › Flow icon
			chat.addEventListener("flow-launcher", (e) => (this.turned_off = e.detail.hidden));
		});
		this.bar.after(this.iframe);
	}

	// Cmd/Ctrl+I in the chat minimizes; other shortcuts the chat leaves go to the page
	handle_keys(chat) {
		chat.addEventListener("keydown", (event) => {
			if (event.defaultPrevented || !(event.metaKey || event.ctrlKey)) return;
			if (is_toggle_key(event)) {
				event.preventDefault();
				this.minimize();
				this.chat_focus = event.target;
				return;
			}
			if (TEXT_KEYS.has(event.key.toLowerCase())) return;
			const copy = new KeyboardEvent("keydown", {
				key: event.key,
				code: event.code,
				location: event.location,
				repeat: event.repeat,
				metaKey: event.metaKey,
				ctrlKey: event.ctrlKey,
				altKey: event.altKey,
				shiftKey: event.shiftKey,
				bubbles: true,
				cancelable: true,
			});
			// Desk reads the legacy key codes, which a made event leaves at 0
			Object.defineProperties(copy, {
				keyCode: { value: event.keyCode },
				which: { value: event.which },
			});
			this.host.dispatchEvent(copy);
			if (copy.defaultPrevented) event.preventDefault();
		});
	}

	// the panel and the chat in it take the page's light or dark theme
	sync_theme() {
		const theme = document.documentElement.getAttribute("data-theme");
		if (theme !== "light" && theme !== "dark") return;
		this.host.dataset.theme = theme;
		const chat = this.iframe?.contentDocument?.documentElement;
		if (chat && chat.getAttribute("data-theme") !== theme) {
			chat.setAttribute("data-theme", theme);
		}
	}

	place() {
		this.place_icon();
		if (!this.iframe) return;

		const { side, full } = this.state;
		let { x, y, w, h } = this.fit(this.state.rect);
		if (full) {
			[x, y, w, h] = [0, 0, innerWidth, innerHeight];
		} else if (side) {
			w = this.dock_width();
			[x, y, h] = [side === "left" ? 0 : innerWidth - w, 0, innerHeight];
		}
		Object.assign(this.panel.style, {
			left: `${x}px`,
			top: `${y}px`,
			width: `${w}px`,
			height: `${h}px`,
		});
		this.panel.dataset.mode = full ? "full" : side || "float";
		this.update_buttons();
	}

	drag_icon(event) {
		const { left, top } = this.icon.getBoundingClientRect();
		const [grab_x, grab_y] = [event.clientX - left, event.clientY - top];
		this.icon_dragged = false;
		this.track(
			event,
			(e) => {
				this.icon_dragged = true;
				this.move_icon(e.clientX - grab_x, e.clientY - grab_y);
			},
			(moved) => {
				if (moved) this.save_icon();
			}
		);
	}

	move_icon(left, top) {
		this.icon.style.left = `${clamp(left, 0, innerWidth - ICON_SIZE)}px`;
		this.icon.style.top = `${clamp(top, 0, innerHeight - ICON_SIZE)}px`;
	}

	place_icon() {
		const { right = true, bottom = true, x = GAP, y = GAP } = this.state.icon || {};
		this.move_icon(
			right ? innerWidth - ICON_SIZE - x : x,
			bottom ? innerHeight - ICON_SIZE - y : y
		);
	}

	// kept as the distance from the nearest corner
	save_icon() {
		const { left, top } = this.icon.getBoundingClientRect();
		const right = left + ICON_SIZE / 2 > innerWidth / 2;
		const bottom = top + ICON_SIZE / 2 > innerHeight / 2;
		this.state.icon = {
			right,
			bottom,
			x: right ? innerWidth - ICON_SIZE - left : left,
			y: bottom ? innerHeight - ICON_SIZE - top : top,
		};
		this.save();
	}

	drag_panel(event) {
		if (innerWidth < PHONE_WIDTH) return;
		const before = this.fit(this.state.rect);
		const { left, top, width } = this.panel.getBoundingClientRect();
		let [grab_x, grab_y] = [event.clientX - left, event.clientY - top];
		let snap = null;
		this.track(
			event,
			(e) => {
				if (this.state.side || this.state.full) {
					// undocked, the same part of the bar stays under the pointer
					Object.assign(this.state, { side: null, full: false });
					grab_x *= before.w / width;
				}
				const { w, h } = this.state.rect;
				const x = e.clientX - grab_x;
				this.state.rect = this.fit({ x, y: e.clientY - grab_y, w, h });
				snap = snap_side(x, this.state.rect.w);
				this.show_preview(snap);
				this.place();
			},
			(moved) => {
				this.show_preview(null);
				if (snap) this.state.side = snap;
				this.place();
				if (moved) this.save();
			}
		);
	}

	resize_panel(event, edge) {
		const before = this.fit(this.state.rect);
		const width = this.dock_width();
		const [start_x, start_y] = [event.clientX, event.clientY];
		this.track(
			event,
			(e) => {
				const [dx, dy] = [e.clientX - start_x, e.clientY - start_y];
				if (this.state.side) {
					const grow = this.state.side === "left" ? dx : -dx;
					this.state.width = clamp(width + grow, MIN_WIDTH, innerWidth * MAX_DOCK_SHARE);
				} else {
					this.state.rect = resize(before, edge, dx, dy);
				}
				this.place();
			},
			(moved) => {
				if (moved) this.save();
			}
		);
	}

	// a shield over the chat takes the moves (pointer-events: none on it breaks Chrome's scroll)
	track(event, on_move, on_end) {
		if (event.button !== 0) return;
		event.preventDefault();
		const target = event.currentTarget;
		const [start_x, start_y] = [event.clientX, event.clientY];
		let moved = false;
		const move = (e) => {
			moved ||= Math.hypot(e.clientX - start_x, e.clientY - start_y) > 3;
			if (moved) on_move(e);
		};
		const end = () => {
			target.removeEventListener("pointermove", move);
			target.removeEventListener("lostpointercapture", end);
			this.panel.classList.remove("busy");
			on_end(moved);
		};
		target.setPointerCapture(event.pointerId);
		target.addEventListener("pointermove", move);
		target.addEventListener("lostpointercapture", end);
		this.panel.classList.add("busy");
	}

	show_preview(side) {
		this.preview.hidden = !side;
		if (!side) return;
		const width = this.dock_width();
		this.preview.style.width = `${width}px`;
		this.preview.style.left = side === "left" ? "0px" : `${innerWidth - width}px`;
	}

	// a docked panel floats at its side
	toggle_dock() {
		const { side } = this.state;
		if (side) {
			const { w } = this.fit(this.state.rect);
			this.state.rect.x = side === "left" ? GAP : innerWidth - w - GAP;
		}
		this.state.side = side ? null : this.nearer_side();
		this.place();
		this.save();
	}

	toggle_full() {
		this.state.full = !this.state.full;
		this.place();
		this.save();
	}

	nearer_side() {
		const { x, w } = this.fit(this.state.rect);
		return x + w / 2 < innerWidth / 2 ? "left" : "right";
	}

	update_buttons() {
		const dock = this.state.side ? "float" : this.nearer_side();
		set_button(this.dock_button, dock, dock === "float" ? "Float" : `Dock to the ${dock}`);
		const full = this.state.full;
		set_button(
			this.full_button,
			full ? "shrink" : "expand",
			full ? "Exit full screen" : "Full screen"
		);
	}

	dock_width() {
		return clamp(this.state.width || PANEL_WIDTH, MIN_WIDTH, innerWidth * MAX_DOCK_SHARE);
	}

	// first opened at the icon's corner
	default_rect() {
		const { right = true, bottom = true } = this.state.icon || {};
		const w = Math.min(PANEL_WIDTH, innerWidth - 2 * GAP);
		const h = Math.min(PANEL_HEIGHT, innerHeight - 2 * GAP);
		return {
			x: right ? innerWidth - w - GAP : GAP,
			y: bottom ? innerHeight - h - GAP : GAP,
			w,
			h,
		};
	}

	// the floating rect, kept inside the window
	fit({ x, y, w, h }) {
		w = clamp(w, MIN_WIDTH, innerWidth);
		h = clamp(h, MIN_HEIGHT, innerHeight);
		return { x: clamp(x, 0, innerWidth - w), y: clamp(y, 0, innerHeight - h), w, h };
	}

	save() {
		// the chat open in the panel, for the next page to open
		const location = this.iframe?.contentDocument?.location;
		if (location && FLOW_PATH.test(location.pathname)) {
			this.state.src = location.pathname + location.search;
		}
		try {
			localStorage.setItem(STORE_KEY, JSON.stringify(this.state));
		} catch {
			// blocked storage only forgets the layout
		}
	}
}

// The rect after dragging one of its edges or corners by dx, dy; the opposite sides stay put.
function resize({ x, y, w, h }, edge, dx, dy) {
	if (edge.includes("e")) w = clamp(w + dx, MIN_WIDTH, innerWidth - x);
	if (edge.includes("s")) h = clamp(h + dy, MIN_HEIGHT, innerHeight - y);
	if (edge.includes("w")) {
		const right = x + w;
		w = clamp(w - dx, MIN_WIDTH, right);
		x = right - w;
	}
	if (edge.includes("n")) {
		const bottom = y + h;
		h = clamp(h - dy, MIN_HEIGHT, bottom);
		y = bottom - h;
	}
	return { x, y, w, h };
}

// The side a panel dragged to x pushes against, if any, which it docks to.
function snap_side(x, w) {
	if (x < 0) return "left";
	if (x + w > innerWidth) return "right";
	return null;
}

// Cmd/Ctrl+I, by the letter typed, or by the key's place on layouts with no Latin letters
function is_toggle_key(event) {
	if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return false;
	return /^[!-~]$/.test(event.key) ? event.key.toLowerCase() === "i" : event.code === "KeyI";
}

// Saves whether the icon is hidden, after the save before it; resolves false when it couldn't.
let saving = Promise.resolve();
function save_hidden(hidden) {
	saving = saving.then(() =>
		fetch("/api/method/frappe.flow.launcher.set_hidden", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				// the apps keep their token on window, Desk on frappe
				"X-Frappe-CSRF-Token": window.csrf_token || window.frappe?.csrf_token,
			},
			body: JSON.stringify({ hidden }),
		}).then(
			(response) => response.ok,
			() => false
		)
	);
	return saving;
}

// Shows one of ICONS on a bar button, with its label as the tooltip.
function set_button(button, icon, label) {
	if (button.dataset.icon === icon) return;
	button.dataset.icon = icon;
	button.title = label;
	button.setAttribute("aria-label", label);
	button.innerHTML = svg(ICONS[icon]);
}

// Calls back now and whenever an <html>'s data-theme changes.
function on_theme_change(root, callback) {
	callback();
	new MutationObserver(callback).observe(root, {
		attributes: true,
		attributeFilter: ["data-theme"],
	});
}

// a window smaller than the minimum gets the window's size
function clamp(value, min, max) {
	return Math.min(Math.max(value, min), max);
}

function load_state() {
	try {
		return JSON.parse(localStorage.getItem(STORE_KEY)) || {};
	} catch {
		return {};
	}
}

const STYLE = `
:host { all: initial; }
@media print { :host { display: none !important; } }
[hidden] { display: none !important; }
.icon, .panel, .preview, .note { position: fixed; z-index: ${LAYER}; box-sizing: border-box; }
.panel[inert] { visibility: hidden; }
.mark { fill: currentColor; }
/* Flow's logo: its mark on gray */
.icon, .title .mark { background: #7c8089; color: #fff; }
button:focus-visible { outline: 2px solid #8a8a8a; outline-offset: 2px; }
.icon {
	display: grid;
	place-items: center;
	width: ${ICON_SIZE}px;
	height: ${ICON_SIZE}px;
	padding: 0;
	border: 0;
	border-radius: 50%;
	box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15), 0 8px 24px rgba(0, 0, 0, 0.15);
	cursor: pointer;
	touch-action: none;
	user-select: none;
	-webkit-user-select: none;
}
.icon .mark { width: 24px; height: 24px; }
.window, .menu {
	background: #fff;
	color: #171717;
	border: 1px solid rgba(0, 0, 0, 0.1);
	border-radius: 12px;
	/* frappe-ui's md elevation; the border stands in for its hairline */
	box-shadow: 0 0 6px 2px rgba(0, 0, 0, 0.04), 0 6px 12px -2px rgba(0, 0, 0, 0.08);
	font: 500 13px/1 InterVariable, Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
:host([data-theme="dark"]) :is(.window, .menu) {
	background: #171717;
	color: #f8f8f8;
	border-color: rgba(255, 255, 255, 0.12);
	box-shadow: 0 0 16px 2px rgba(0, 0, 0, 0.2), 0 6px 12px -2px rgba(0, 0, 0, 0.6);
}
/* the window clips the chat to its corners; the edges stick out of it to be easy to grab */
.window {
	display: flex;
	flex-direction: column;
	box-sizing: border-box;
	width: 100%;
	height: 100%;
	overflow: hidden;
}
/* a popover (closed, the browser hides it), placed by the icon */
.menu { inset: auto; margin: 0; padding: 4px; border-radius: 10px; font-weight: 420; }
.menu button {
	display: block;
	height: 28px;
	padding: 0 8px;
	border: 0;
	border-radius: 6px;
	background: none;
	color: inherit;
	font: inherit;
	white-space: nowrap;
	cursor: pointer;
}
.menu button:hover { background: rgba(0, 0, 0, 0.06); }
:host([data-theme="dark"]) .menu button:hover { background: rgba(255, 255, 255, 0.08); }
/* frappe-ui's toast, where it shows hers, in the page's colors (Desk shows its own) */
.note {
	right: 24px;
	bottom: 24px;
	display: flex;
	align-items: center;
	width: 360px;
	max-width: calc(100vw - ${2 * GAP}px);
	padding: 10px 16px;
	border-radius: var(--radius-5, 10px);
	background: var(--surface-gray-9, #333);
	color: var(--ink-base, #fff);
	box-shadow: var(--elevation-xl, 0 24px 30px -8px rgba(0, 0, 0, 0.1));
	font: 420 14px/1.5 InterVariable, Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
	letter-spacing: 0.02em;
}
.note strong { display: block; font-weight: 500; }
.note a { color: inherit; text-decoration: none; }
.note a:hover { text-decoration: underline; }
.note button { flex: none; border: 0; background: none; color: inherit; font: inherit; cursor: pointer; }
.note button:hover { background: var(--surface-gray-8, #444); }
.note .undo {
	height: 28px;
	margin: 0 8px 0 auto;
	padding: 0 8px;
	border-radius: var(--radius-4, 8px);
	color: var(--ink-blue-link, #0289f7);
	font-weight: 500;
}
.note .dismiss { display: grid; place-items: center; width: 20px; height: 20px; padding: 0; border-radius: var(--radius-1, 4px); }
.panel:not([data-mode="float"]) .window { border-width: 0; border-radius: 0; }
.panel[data-mode="left"] .window { border-right-width: 1px; }
.panel[data-mode="right"] .window { border-left-width: 1px; }
.panel[data-mode="full"] .dock { display: none; }
.bar {
	display: flex;
	flex: none;
	align-items: center;
	gap: 2px;
	height: 36px;
	padding: 0 6px 0 12px;
	border-bottom: 1px solid rgba(0, 0, 0, 0.08);
	cursor: grab;
	touch-action: none;
	user-select: none;
	-webkit-user-select: none;
}
:host([data-theme="dark"]) .bar { border-color: rgba(255, 255, 255, 0.1); }
/* filling the window, the bar runs into the chat's own header */
.panel[data-mode="full"] .bar { border-bottom-width: 0; }
.title { display: flex; align-items: center; gap: 6px; margin-right: auto; }
.title .mark {
	box-sizing: border-box;
	width: 18px;
	height: 18px;
	padding: 2.5px;
	border-radius: 4.5px;
}
.bar button {
	display: grid;
	place-items: center;
	width: 28px;
	height: 28px;
	padding: 0;
	border: 0;
	border-radius: 6px;
	background: none;
	color: inherit;
	opacity: 0.65;
	cursor: pointer;
}
.bar button:hover { opacity: 1; background: rgba(0, 0, 0, 0.06); }
:host([data-theme="dark"]) .bar button:hover { background: rgba(255, 255, 255, 0.08); }
.bar button svg, .note svg {
	width: 16px;
	height: 16px;
	fill: none;
	stroke: currentColor;
	stroke-width: 2;
	stroke-linecap: round;
	stroke-linejoin: round;
}
iframe { display: block; flex: 1; width: 100%; min-height: 0; border: 0; }
.shield { position: absolute; inset: 0; display: none; }
.busy .shield { display: block; }
.edge { position: absolute; display: none; touch-action: none; }
.panel[data-mode="float"] .edge,
.panel[data-mode="left"] .edge[data-edge="e"],
.panel[data-mode="right"] .edge[data-edge="w"] { display: block; }
.edge[data-edge="n"], .edge[data-edge="s"] { left: 12px; right: 12px; height: 8px; cursor: ns-resize; }
.edge[data-edge="e"], .edge[data-edge="w"] { top: 12px; bottom: 12px; width: 8px; cursor: ew-resize; }
.panel[data-mode="left"] .edge, .panel[data-mode="right"] .edge { top: 0; bottom: 0; }
.edge[data-edge="n"] { top: -4px; }
.edge[data-edge="s"] { bottom: -4px; }
.edge[data-edge="e"] { right: -4px; }
.edge[data-edge="w"] { left: -4px; }
.edge[data-edge="ne"], .edge[data-edge="nw"], .edge[data-edge="se"], .edge[data-edge="sw"] {
	width: 16px;
	height: 16px;
}
.edge[data-edge="nw"] { top: -4px; left: -4px; cursor: nwse-resize; }
.edge[data-edge="ne"] { top: -4px; right: -4px; cursor: nesw-resize; }
.edge[data-edge="sw"] { bottom: -4px; left: -4px; cursor: nesw-resize; }
.edge[data-edge="se"] { bottom: -4px; right: -4px; cursor: nwse-resize; }
.preview {
	top: 0;
	bottom: 0;
	background: rgba(128, 128, 128, 0.16);
	box-shadow: inset 0 0 0 2px rgba(128, 128, 128, 0.4);
	pointer-events: none;
}
@media (max-width: ${PHONE_WIDTH - 1}px) {
	.panel { inset: 0 !important; width: auto !important; height: auto !important; }
	.window { border-width: 0 !important; border-radius: 0 !important; }
	.edge, .dock, .full { display: none !important; }
	.bar { cursor: default; border-bottom-width: 0; }
}
`;

// not inside frames, such as a Desk page opened in the panel
if (window.top === window) new FlowLauncher();
