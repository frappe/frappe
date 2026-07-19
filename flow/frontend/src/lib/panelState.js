// Persists the panel's open/fullscreen/width/session across reloads.
const KEY = "flow-panel-state";

export function readPanelState() {
	try {
		return JSON.parse(localStorage.getItem(KEY)) || {};
	} catch {
		return {};
	}
}

export function writePanelState(state) {
	try {
		localStorage.setItem(KEY, JSON.stringify(state));
	} catch {
		// storage unavailable — persistence is best-effort
	}
}
