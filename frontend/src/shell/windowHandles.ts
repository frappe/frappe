// The standing windows' handles, one per app. A handle exists from its first use, so an act can open
// the window before the app's shell hook has attached it.
import { markRaw, reactive } from "vue";
import type { StandingWindow, StandingWindowAction, StandingWindowHandle } from "./standingWindows";

const MAX_ACTIONS = 3;

const entries = new Map<string, StandingWindow>();

/** The handle of `app`'s window, whether or not its component has attached yet. */
export function windowHandleOf(app: string): StandingWindowHandle {
	return entryOf(app).handle;
}

/** The window state behind `app`'s handle, made on first use. */
export function entryOf(app: string): StandingWindow {
	let entry = entries.get(app);
	if (!entry) {
		entry = reactive({
			app,
			icon: undefined,
			width: 0,
			component: null,
			props: {},
			state: "closed",
			appTitle: "",
			title: "",
			actions: [],
			closable: true,
			keepAlive: false,
			attention: false,
			placed: null,
		}) as unknown as StandingWindow;
		entry.handle = handleFor(entry);
		entries.set(app, entry);
	}
	return entry;
}

export function resetWindowHandles() {
	entries.clear();
}

// Frozen, so `reactive` leaves it raw; `state` reads through to the entry and stays reactive.
function handleFor(entry: StandingWindow): StandingWindowHandle {
	return Object.freeze({
		get state() {
			return entry.state;
		},
		get isOpen() {
			return entry.state === "open";
		},
		open: (props?: Record<string, unknown>) => {
			if (props) entry.props = markRaw({ ...props });
			entry.state = "open";
		},
		minimise: () => void (entry.state = "minimised"),
		close: () => void (entry.state = "closed"),
		setTitle: (text: string) => void (entry.title = text ? String(text) : entry.appTitle),
		setActions: (actions: StandingWindowAction[]) => {
			if (actions.length > MAX_ACTIONS)
				console.warn(`[frappe] ${entry.app}'s window draws only its first three actions.`);
			entry.actions = actions.slice(0, MAX_ACTIONS).map((action) => markRaw({ ...action }));
		},
		setClosable: (closable: boolean) => void (entry.closable = Boolean(closable)),
		setKeepAlive: (on: boolean) => void (entry.keepAlive = Boolean(on)),
		setAttention: (attention: boolean) => void (entry.attention = Boolean(attention)),
	});
}
