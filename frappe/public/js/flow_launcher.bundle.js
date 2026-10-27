// Flow's launcher: opens /flow in a panel beside the page, on Cmd/Ctrl+I or a click on any element
// marked data-flow-toggle, which each app places itself (added by frappe/flow/launcher.py)

const STORE_KEY = "flow_launcher";
const FLOW_PATH = /^\/flow(\/|\?|$)/;
const PANEL_WIDTH = 420;
const MIN_WIDTH = 320;
// the page beside the panel keeps room for Desk's sidebar and a form with its side column, which
// lay out by the window's width, not the page's
const MIN_PAGE_WIDTH = 880;
const PHONE_WIDTH = 640; // narrower windows show the panel full screen
const SLIDE_TIME = 200; // ms the panel takes to slide in or out
// under the page's dialogs and toasts, which start at 1040 on Desk and 50 in frappe-ui apps
const LAYER = location.pathname.startsWith("/desk") ? 1035 : 45;
// Cmd/Ctrl keys a text box uses, kept in the chat; other shortcuts go to the page
const TEXT_KEYS = new Set([
	...["a", "b", "c", "i", "u", "v", "x", "y", "z"],
	...["backspace", "delete", "enter", "home", "end"],
	...["arrowleft", "arrowright", "arrowup", "arrowdown"],
]);

class FlowLauncher {
	constructor() {
		this.state = load_state();
		this.covered = false; // filling the window while /flow's settings are open
		this.make();
		this.bind();
		this.place();
		if (this.state.open) this.open({ focus: false, slide: false });
	}

	make() {
		this.host = document.createElement("flow-launcher");
		const root = this.host.attachShadow({ mode: "open" });
		root.innerHTML = `<style>${STYLE}</style>
			<div class="panel" role="dialog" aria-label="Flow" inert>
				<div class="window"></div>
				<div class="shield"></div>
				<div class="edge"></div>
			</div>`;
		this.panel = root.querySelector(".panel");
		this.window = root.querySelector(".window");
		document.body.append(this.host);
		const page_style = document.createElement("style");
		page_style.textContent = PAGE_STYLE;
		document.head.append(page_style);
		on_theme_change(document.documentElement, () => this.sync_theme());
	}

	bind() {
		window.addEventListener("keydown", (event) => this.toggle_by_key(event), true);
		// the apps' own toggles, wherever they put them, including ones rendered later
		document.addEventListener("click", (event) => {
			if (event.target.closest?.("[data-flow-toggle]")) this.toggle();
		});
		// a chat loading behind the closed panel takes the keyboard: give it back where it was
		const stolen = () =>
			!this.state.open && this.host.shadowRoot.activeElement === this.iframe;
		// where the keyboard was on the page as it went into the panel; none from the page itself
		document.addEventListener("focusin", (event) => {
			if (event.target === this.host) this.page_focus = event.relatedTarget;
		});
		window.addEventListener("blur", () => {
			if (!stolen()) return;
			// a task later: taken back sooner, the frame keeps it
			setTimeout(() => {
				this.chat_focus = this.iframe.contentDocument?.activeElement; // for the next open
				this.focus_page();
			});
		});
		this.panel
			.querySelector(".edge")
			.addEventListener("pointerdown", (event) => this.resize_panel(event));
		window.addEventListener("resize", () => this.place());
		window.addEventListener("pagehide", () => this.save());
	}

	open({ focus = true, slide = true } = {}) {
		if (slide) this.slide();
		this.state.open = true;
		if (!this.iframe) this.make_iframe();
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
		this.slide();
		this.state.open = false;
		this.panel.inert = true;
		this.squeeze();
		if (focused) this.focus_page();
		this.save();
	}

	// out of the hidden chat, so the next keys, Cmd/Ctrl+I among them, reach the page: back where
	// they were, without scrolling to it
	focus_page() {
		this.iframe.blur();
		if (this.page_focus?.isConnected) this.page_focus.focus({ preventScroll: true });
	}

	toggle() {
		if (this.state.open) this.minimize();
		else this.open();
	}

	// Cmd/Ctrl+I anywhere on the page; rich text keeps it for italics
	toggle_by_key(event) {
		if (!is_toggle_key(event) || event.composedPath()[0].isContentEditable) return;
		event.preventDefault();
		event.stopPropagation();
		this.toggle();
	}

	make_iframe() {
		this.iframe = document.createElement("iframe");
		this.iframe.title = "Flow";
		// the chat open on the last page
		this.iframe.src = FLOW_PATH.test(this.state.src) ? this.state.src : "/flow";
		this.iframe.addEventListener("load", (event) => {
			this.cover(false); // a page just loaded has no settings open
			const chat = event.target.contentDocument?.defaultView;
			if (!chat) return; // an error page, which the page can't reach into
			// /flow applies its own saved theme as it loads; the page's wins
			on_theme_change(chat.document.documentElement, () => this.sync_theme());
			this.handle_keys(chat);
			chat.addEventListener("flow-settings", (e) => this.cover(e.detail.open));
			// the chat header's ×, which puts the panel away with its chat kept for the next open
			chat.addEventListener("flow-close", () => this.minimize());
		});
		this.window.append(this.iframe);
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
		if (!this.iframe) return;

		// docked on the right, or over the whole window while /flow's settings are open
		const width = this.covered ? innerWidth : this.dock_width();
		// as variables, so the phone layout's rules can override them
		const rect = { left: innerWidth - width, top: 0, width, height: innerHeight };
		for (const [name, px] of Object.entries(rect)) {
			this.panel.style.setProperty(`--${name}`, `${px}px`);
		}
		this.panel.toggleAttribute("data-covered", this.covered);
		this.squeeze();
	}

	// the page narrows beside the open panel, as an editor's does beside its side bar; in a window
	// too narrow to leave the page its room, the panel covers the page instead
	squeeze() {
		const width = this.dock_width();
		const docked = this.state.open && innerWidth - width >= MIN_PAGE_WIDTH;
		const page = document.documentElement;
		page.style.setProperty("--flow-dock-width", docked ? `${width}px` : "");
		page.toggleAttribute("data-flow-docked", docked);
	}

	// the panel slides and the page's edge moves with it, only while opening or closing, so a
	// resize or a page load doesn't animate
	slide() {
		const page = document.documentElement;
		page.toggleAttribute("data-flow-sliding", true);
		this.host.toggleAttribute("data-sliding", true);
		clearTimeout(this.slide_timer);
		this.slide_timer = setTimeout(() => {
			page.removeAttribute("data-flow-sliding");
			this.host.removeAttribute("data-sliding");
		}, SLIDE_TIME + 50);
	}

	// /flow's settings dialog fills the window until they close
	cover(covered) {
		this.covered = covered;
		this.place();
	}

	// by its left edge
	resize_panel(event) {
		const width = this.dock_width();
		const start_x = event.clientX;
		this.track(
			event,
			(e) => {
				const grow = start_x - e.clientX;
				this.state.width = clamp(width + grow, MIN_WIDTH, max_width());
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

	dock_width() {
		return clamp(this.state.width || PANEL_WIDTH, MIN_WIDTH, max_width());
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

// Cmd/Ctrl+I, by the letter typed, or by the key's place on layouts with no Latin letters
function is_toggle_key(event) {
	if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return false;
	return /^[!-~]$/.test(event.key) ? event.key.toLowerCase() === "i" : event.code === "KeyI";
}

// Calls back now and whenever an <html>'s data-theme changes.
function on_theme_change(root, callback) {
	callback();
	new MutationObserver(callback).observe(root, {
		attributes: true,
		attributeFilter: ["data-theme"],
	});
}

// the widest the panel docks, leaving the page its room
function max_width() {
	return Math.max(MIN_WIDTH, innerWidth - MIN_PAGE_WIDTH);
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

const SLIDE = `${SLIDE_TIME}ms cubic-bezier(0.2, 0, 0, 1)`;
// the page's room beside the panel, on screen only, so a printout keeps the page's width. The apps
// lay out at the window's width (w-screen), which the page's margin can't narrow
const PAGE_STYLE = `@media screen {
	html[data-flow-docked] { margin-right: var(--flow-dock-width); }
}
html:is([data-flow-docked], [data-flow-sliding]) .w-screen { width: 100%; }
@media (prefers-reduced-motion: no-preference) {
	html[data-flow-sliding] { transition: margin-right ${SLIDE}; }
}`;

const STYLE = `
/* var(--*) are the page's design tokens; the fallbacks serve apps that lack them */
:host { all: initial; }
@media print { :host { display: none; } }
.panel { position: fixed; z-index: ${LAYER}; box-sizing: border-box; }
.panel { left: var(--left); top: var(--top); width: var(--width); height: var(--height); }
.panel[inert] { visibility: hidden; transform: translateX(100%); }
/* closing, it stays in view until it is out */
@media (prefers-reduced-motion: no-preference) {
	:host([data-sliding]) .panel { transition: transform ${SLIDE}; }
	:host([data-sliding]) .panel[inert] { transition: transform ${SLIDE}, visibility 0s ${SLIDE_TIME}ms; }
}
.window {
	background: var(--surface-base, #fff);
	color: var(--ink-gray-9, #0f0f0f);
	border: 1px solid var(--outline-elevation-2, rgba(128, 128, 128, 0.25));
	border-radius: var(--radius-6, 12px);
	box-shadow: var(--elevation-md, 0 0 1.5px rgba(0, 0, 0, 0.15), 0 0 6px 2px rgba(0, 0, 0, 0.04), 0 6px 12px -2px rgba(0, 0, 0, 0.08));
	font: var(--font-weight-medium, 500) var(--text-sm, 13px)/1 InterVariable, Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
:host([data-theme="dark"]) .window {
	background: var(--surface-base, #171717);
	color: var(--ink-gray-9, #f8f8f8);
}
/* flat beside the page, as Desk's sidebar is: a line on the edge toward the page, which the grip
   sticks out of to be easy to grab */
.window {
	display: flex;
	flex-direction: column;
	box-sizing: border-box;
	width: 100%;
	height: 100%;
	overflow: hidden;
	border-width: 0 0 0 1px;
	border-color: var(--outline-gray-1, rgba(128, 128, 128, 0.2));
	border-radius: 0;
	box-shadow: none;
}
/* filling the window, it has no edge toward the page */
.panel[data-covered] .window { border-width: 0; }
iframe { display: block; flex: 1; width: 100%; min-height: 0; border: 0; }
.shield { position: absolute; inset: 0; display: none; }
.busy .shield { display: block; }
.edge { position: absolute; top: 0; bottom: 0; left: -4px; width: 8px; cursor: ew-resize; touch-action: none; }
.panel[data-covered] .edge { display: none; }
@media (max-width: ${PHONE_WIDTH - 1}px) {
	.panel { inset: 0; width: auto; height: auto; }
	.window { border-width: 0; }
	.edge { display: none; }
}
`;

// not inside frames, such as a Desk page opened in the panel; window.flow.toggle() is for an app's
// code, as data-flow-toggle is for its markup
if (window.top === window) {
	const launcher = new FlowLauncher();
	window.flow = { toggle: () => launcher.toggle() };
}
