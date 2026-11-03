// The standing windows apps attach through their shell hooks: one per app, kept for the tab.
import { markRaw, reactive, type Component } from "vue";

export type StandingWindowState = "closed" | "open" | "minimised";

/** A button the shell draws in the window's header and its minimised form. */
export interface StandingWindowAction {
	label: string;
	icon: string;
	/** A frappe-ui Button theme; gray unless given. */
	theme?: "gray" | "blue" | "green" | "red";
	run: () => unknown;
}

export interface StandingWindowOptions {
	icon?: string;
	/** In pixels, clamped to 240–400. */
	width?: number;
}

/** What `shell.window` returns, and the window's component gets as its `window` prop. */
export interface StandingWindowHandle {
	/** Reactive. */
	readonly state: StandingWindowState;
	open(): void;
	minimise(): void;
	/** Hides the frame; the component stays mounted. */
	close(): void;
	setTitle(text: string): void;
	/** Up to three; the shell draws the first three of more. */
	setActions(actions: StandingWindowAction[]): void;
	/** Whether the frame offers close; true until set. */
	setClosable(closable: boolean): void;
	/** While on, the shell opens other pages in a new tab and asks before a reload; off until set. */
	setKeepAlive(on: boolean): void;
}

/** One app's window as the row draws it. */
export interface StandingWindow {
	app: string;
	icon?: string;
	width: number;
	component: Component;
	state: StandingWindowState;
	title: string;
	actions: StandingWindowAction[];
	closable: boolean;
	keepAlive: boolean;
	handle: StandingWindowHandle;
}

const MIN_WIDTH = 240;
const MAX_WIDTH = 400;
const DEFAULT_WIDTH = 280;
const MAX_ACTIONS = 3;

/** Adds `app`'s window to `windows`, kept in `order`, the hooked apps' app order. */
export function attachWindow(
	windows: StandingWindow[],
	order: string[],
	app: string,
	title: string,
	component: Component,
	options: StandingWindowOptions = {}
): StandingWindowHandle | undefined {
	if (windows.some((entry) => entry.app === app)) {
		console.warn(`[frappe] ${app}'s shell.js asked for a second window; it is ignored.`);
		return undefined;
	}
	const entry = reactive({
		app,
		icon: options.icon,
		width: clampWidth(options.width),
		component: markRaw(component),
		state: "closed",
		title,
		actions: [],
		closable: true,
		keepAlive: false,
	}) as unknown as StandingWindow;
	entry.handle = handleFor(entry, title);
	const rank = order.indexOf(app);
	const after = windows.findIndex((other) => order.indexOf(other.app) > rank);
	windows.splice(after === -1 ? windows.length : after, 0, entry);
	return entry.handle;
}

// Frozen, so `reactive` leaves it raw; `state` reads through to the entry and stays reactive.
function handleFor(entry: StandingWindow, appTitle: string): StandingWindowHandle {
	return Object.freeze({
		get state() {
			return entry.state;
		},
		open: () => void (entry.state = "open"),
		minimise: () => void (entry.state = "minimised"),
		close: () => void (entry.state = "closed"),
		setTitle: (text: string) => void (entry.title = text ? String(text) : appTitle),
		setActions: (actions: StandingWindowAction[]) => {
			if (actions.length > MAX_ACTIONS)
				console.warn(`[frappe] ${entry.app}'s window draws only its first three actions.`);
			entry.actions = actions.slice(0, MAX_ACTIONS).map((action) => markRaw({ ...action }));
		},
		setClosable: (closable: boolean) => void (entry.closable = Boolean(closable)),
		setKeepAlive: (on: boolean) => void (entry.keepAlive = Boolean(on)),
	});
}

function clampWidth(width: number | undefined) {
	if (typeof width !== "number" || Number.isNaN(width)) return DEFAULT_WIDTH;
	return Math.min(Math.max(width, MIN_WIDTH), MAX_WIDTH);
}
