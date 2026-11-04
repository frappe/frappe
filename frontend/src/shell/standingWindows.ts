// The standing windows apps attach through their shell hooks: one per app, kept for the tab.
import { markRaw, type Component } from "vue";
import { entryOf } from "./windowHandles";
import type { Placement } from "./windowDrag";

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

/** What `shell.window` and `shell.windowOf(app)` return, and the window's component gets as its `window` prop. */
export interface StandingWindowHandle {
	/** Reactive. */
	readonly state: StandingWindowState;
	/** Reactive; `state` is `open`, so false while minimised, and true after an early `open` whether or not the window ever attaches. */
	readonly isOpen: boolean;
	/** Shows the frame; `props` become the component's props, and a call before the window attaches opens it on attach. */
	open(props?: Record<string, unknown>): void;
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
	/** While on, the pill pulses a soft ring for something that waits on the user; off until set. */
	setAttention(attention: boolean): void;
}

/** One app's window as the row draws it. */
export interface StandingWindow {
	app: string;
	icon?: string;
	width: number;
	/** Null until the app's shell hook attaches the window. */
	component: Component | null;
	/** What the last `open(props)` gave the component. */
	props: Record<string, unknown>;
	state: StandingWindowState;
	/** The app's `add_to_apps_screen` title, what `setTitle("")` restores. */
	appTitle: string;
	title: string;
	actions: StandingWindowAction[];
	closable: boolean;
	keepAlive: boolean;
	attention: boolean;
	/** Where the user dragged it, for this tab; null while it stands in the row. */
	placed: Placement | null;
	handle: StandingWindowHandle;
}

const MIN_WIDTH = 240;
const MAX_WIDTH = 400;
const DEFAULT_WIDTH = 280;

/** Adds `app`'s window to `windows`, kept in `order`, the hooked apps' app order. */
export function attachWindow(
	windows: StandingWindow[],
	order: string[],
	app: string,
	title: string,
	component: Component,
	options: StandingWindowOptions = {}
): StandingWindowHandle | undefined {
	const entry = entryOf(app);
	if (entry.component) {
		console.warn(`[frappe] ${app}'s shell.js asked for a second window; it is ignored.`);
		return undefined;
	}
	Object.assign(entry, {
		icon: options.icon,
		width: clampWidth(options.width),
		component: markRaw(component),
		appTitle: title,
		title: entry.title || title,
	});
	const rank = order.indexOf(app);
	const after = windows.findIndex((other) => order.indexOf(other.app) > rank);
	windows.splice(after === -1 ? windows.length : after, 0, entry);
	return entry.handle;
}

function clampWidth(width: number | undefined) {
	if (typeof width !== "number" || Number.isNaN(width)) return DEFAULT_WIDTH;
	return Math.min(Math.max(width, MIN_WIDTH), MAX_WIDTH);
}
