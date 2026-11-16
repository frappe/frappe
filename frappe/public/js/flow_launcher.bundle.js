// Flow's launcher: opens Flow's chat in a panel beside the page, on Cmd/Ctrl+I or a click on any
// element marked data-flow-toggle, which each app places itself (added by frappe/flow/launcher.py,
// which names the chat's island files on the script tag)

// A relative path, because this branch's esbuild predates `alias`.
import { mountIsland } from "../../../ui/island/host.js";

const STORE_KEY = "flow_launcher";
const ISLAND = "frappe.flow.chat";
const SCRIPT = document.currentScript;
const PANEL_WIDTH = 420;
const MIN_WIDTH = 320;
// the page beside the panel keeps room for Desk's sidebar and a form with its side column, which
// lay out by the window's width, not the page's
const MIN_PAGE_WIDTH = 880;
const PHONE_WIDTH = 640; // narrower windows show the panel full screen
const SLIDE_TIME = 200; // ms the panel takes to slide in or out
// under the page's dialogs and toasts, which start at 1040 on Desk and 50 in frappe-ui apps
const LAYER = location.pathname.startsWith("/desk") ? 1035 : 45;

class FlowLauncher {
	constructor() {
		this.state = load_state();
		this.make();
		this.bind();
		this.place();
		if (this.state.open) this.open({ focus: false, slide: false });
		else prefetch_island();
	}

	make() {
		this.host = document.createElement("flow-launcher");
		const root = this.host.attachShadow({ mode: "open" });
		root.innerHTML = `<style>${STYLE}</style>
			<div class="panel" role="dialog" aria-label="Flow" inert>
				<div class="window"><slot></slot>${SKELETON}${FAILED}</div>
				<div class="shield"></div>
				<div class="edge"></div>
			</div>`;
		this.panel = root.querySelector(".panel");
		// the chat mounts in the page's tree, slotted into the panel: in this shadow root it would
		// sit two roots deep, where frappe-ui's patched overlays take a click on it for one outside
		this.chat = document.createElement("div");
		this.chat.inert = true;
		this.host.append(this.chat);
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
		// where the keyboard was on the page as it went into the panel; none from the page itself
		document.addEventListener("focusin", (event) => {
			if (this.host.contains(event.target) && !this.host.contains(event.relatedTarget))
				this.page_focus = event.relatedTarget;
		});
		this.panel
			.querySelector(".edge")
			.addEventListener("pointerdown", (event) => this.resize_panel(event));
		// a failed start isn't retried in place: the browser keeps a failed import for its URL, and
		// a deploy since the page loaded leaves it naming files that are gone
		this.panel.querySelector(".reload").addEventListener("click", () => location.reload());
		this.panel.querySelector(".close").addEventListener("click", () => this.minimize());
		// a file dropped on the panel's edge would open in the tab; the chat handles its own
		for (const name of ["dragover", "drop"])
			this.panel.addEventListener(name, (event) => {
				if (event.defaultPrevented || !event.dataTransfer?.types.includes("Files")) return;
				event.preventDefault();
				event.dataTransfer.dropEffect = "none";
			});
		window.addEventListener("resize", () => this.place());
		window.addEventListener("pagehide", () => this.save());
	}

	open({ focus = true, slide = true } = {}) {
		if (slide) this.slide();
		this.state.open = true;
		if (!this.island) this.make_island();
		this.panel.inert = this.chat.inert = false;
		this.place();
		this.save();
		// a failed start is logged once, where the island is made; its Try again takes the focus
		if (focus)
			this.island.ready.then(
				() => this.focus_chat(),
				() => this.panel.querySelector(".reload").focus()
			);
	}

	// where the keyboard was in the chat, or its message box
	focus_chat() {
		if (!this.state.open) return;
		const chat = this.chat.querySelector(".frappe-island")?.shadowRoot;
		const target = this.chat_focus?.isConnected
			? this.chat_focus
			: chat?.querySelector("[contenteditable=true], textarea");
		target?.focus({ preventScroll: true });
	}

	// hidden, not removed, so the chat doesn't lay itself out and animate in again
	minimize() {
		const focused = this.host.contains(document.activeElement);
		this.chat_focus = focused ? deep_active_element() : null;
		this.slide();
		this.state.open = false;
		this.panel.inert = this.chat.inert = true;
		this.squeeze();
		if (focused) this.focus_page();
		this.save();
	}

	// out of the hidden chat, so the next keys, Cmd/Ctrl+I among them, reach the page: back where
	// they were, without scrolling to it
	focus_page() {
		deep_active_element()?.blur();
		if (this.page_focus?.isConnected) this.page_focus.focus({ preventScroll: true });
	}

	toggle() {
		if (this.state.open) this.minimize();
		else this.open();
	}

	// Cmd/Ctrl+I anywhere on the page and in the chat; the page's rich text keeps it for italics
	toggle_by_key(event) {
		const path = event.composedPath();
		if (!is_toggle_key(event) || (path[0].isContentEditable && !path.includes(this.host)))
			return;
		event.preventDefault();
		event.stopPropagation();
		this.toggle();
	}

	make_island() {
		const desk = Boolean(window.frappe?.set_route);
		this.island = mountIsland(ISLAND, this.chat, {
			resolve: () => ({ js: SCRIPT.dataset.island, css: SCRIPT.dataset.islandCss }),
			host: {
				locale: window.frappe?.boot?.lang || document.documentElement.lang || "en",
				user: window.frappe?.session?.user || null,
				base_url: location.origin,
				navigate: (route) => (desk ? frappe.set_route(route) : location.assign(route)),
			},
			props: {
				panel: desk ? "desk" : "app",
				path: this.state.path,
				onClose: () => this.minimize(),
				onNavigate: (path) => {
					this.state.path = path;
					this.save();
				},
			},
		});
		this.island.ready.then(
			() => this.host.toggleAttribute("data-ready", true),
			(error) => {
				this.host.toggleAttribute("data-failed", true);
				console.error("Flow could not start", error);
			}
		);
	}

	// the panel takes the page's light or dark theme; the island follows it by itself
	sync_theme() {
		const theme = document.documentElement.getAttribute("data-theme");
		if (theme !== "light" && theme !== "dark") return;
		this.host.dataset.theme = theme;
	}

	place() {
		if (!this.island) return;

		// docked on the right
		const width = this.dock_width();
		// as variables, so the phone layout's rules can override them
		const rect = { left: innerWidth - width, top: 0, width, height: innerHeight };
		for (const [name, px] of Object.entries(rect)) {
			this.panel.style.setProperty(`--${name}`, `${px}px`);
		}
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

	// the layout, and the chat open in the panel for the next page to open
	save() {
		try {
			localStorage.setItem(STORE_KEY, JSON.stringify(this.state));
		} catch {
			// blocked storage only forgets the layout
		}
	}
}

// the chat's files, fetched once the page has loaded and gone idle, so the panel opens without
// waiting for them. The launcher is only on pages of users who may use Flow
function prefetch_island() {
	const idle = window.requestIdleCallback || ((callback) => setTimeout(callback, 2000));
	const fetch_files = () => {
		for (const href of [SCRIPT.dataset.island, SCRIPT.dataset.islandCss]) {
			if (!href) continue;
			const link = document.createElement("link");
			Object.assign(link, { rel: "prefetch", href });
			document.head.append(link);
		}
	};
	if (document.readyState === "complete") idle(fetch_files);
	else window.addEventListener("load", () => idle(fetch_files), { once: true });
}

// Cmd/Ctrl+I, by the letter typed, or by the key's place on layouts with no Latin letters
function is_toggle_key(event) {
	if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return false;
	return /^[!-~]$/.test(event.key) ? event.key.toLowerCase() === "i" : event.code === "KeyI";
}

// the element that has the keyboard, inside shadow roots too
function deep_active_element() {
	let element = document.activeElement;
	while (element?.shadowRoot?.activeElement) element = element.shadowRoot.activeElement;
	return element;
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

// the panel's header and message box, drawn at once while the chat loads
const SKELETON = `<div class="skeleton" aria-hidden="true">
	<div class="bar"><i style="width: 40%"></i><b></b><b></b><b></b></div>
	<div class="composer"><i style="width: 25%"></i></div>
</div>`;
// in the skeleton's place when the chat's files could not load
const FAILED = `<div class="failed" role="alert">
	<p>Flow could not start.</p>
	<div><button class="reload">Reload page</button><button class="close">Close</button></div>
</div>`;

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
/* a modal overlay in the chat (a menu, a dialog) turns the page's pointer events off; the panel
   follows the page, as the chat's own layer turns them back on */
:host { all: initial; pointer-events: inherit; }
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
/* the chat's own fixed layers (its toasts, a menu's backdrop, a sub-agent's sheet) place against
   the panel and not the page; its dialogs sit in the top layer, over the page */
.window { position: relative; contain: layout; }
/* after 300 ms, as Desk's island pages: a chat that is quicker never flashes it */
.skeleton { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: space-between; }
.panel:not([inert]) .skeleton { animation: skeleton-in 150ms ease-out 300ms backwards; }
@keyframes skeleton-in { from { opacity: 0; } }
:host([data-ready]) .skeleton { display: none; }
.skeleton i, .skeleton b { display: block; height: 12px; border-radius: 6px; background: var(--skeleton-bg, var(--surface-gray-3, rgba(128, 128, 128, 0.16))); }
.skeleton b { width: 16px; height: 16px; border-radius: 4px; }
.skeleton .bar { display: flex; align-items: center; gap: 16px; height: 48px; padding: 0 12px; box-sizing: border-box; }
.skeleton .bar i { margin-right: auto; }
.skeleton .composer { height: 124px; margin: 20px; padding: 22px 14px; box-sizing: border-box; border-radius: var(--radius-7, 16px); background: var(--surface-gray-1, rgba(128, 128, 128, 0.06)); }
.failed { position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 0 20px; color: var(--ink-gray-6, #7c7c7c); line-height: 1.5; }
.failed p { margin: 0; }
.failed div { display: flex; gap: 8px; }
.failed button { height: 28px; padding: 0 12px; border: 0; border-radius: var(--radius, 8px); font: inherit; cursor: pointer; background: var(--surface-gray-2, rgba(128, 128, 128, 0.12)); color: var(--ink-gray-8, #383838); }
.failed button:hover { background: var(--surface-gray-3, rgba(128, 128, 128, 0.2)); }
.failed .reload { background: var(--surface-gray-9, #171717); color: var(--ink-base, #fff); }
.failed .reload:hover { background: var(--surface-gray-8, #383838); }
:host([data-failed]) .skeleton { display: none; }
:host([data-failed]) .failed { display: flex; }
@media (prefers-reduced-motion: no-preference) {
	.skeleton :is(i, b) { animation: pulse 1.5s ease-in-out infinite; }
}
@keyframes pulse { 50% { opacity: 0.5; } }
::slotted(div) { flex: 1; min-height: 0; }
.shield { position: absolute; inset: 0; display: none; }
.busy .shield { display: block; }
.edge { position: absolute; top: 0; bottom: 0; left: -4px; width: 8px; cursor: ew-resize; touch-action: none; }
@media (max-width: ${PHONE_WIDTH - 1}px) {
	.panel { inset: 0; width: auto; height: auto; }
	.window { border-width: 0; }
	.edge { display: none; }
}
`;

// not inside frames; window.flow.toggle() is for an app's
// code, as data-flow-toggle is for its markup
if (window.top === window) {
	const launcher = new FlowLauncher();
	window.flow = { toggle: () => launcher.toggle() };
}
