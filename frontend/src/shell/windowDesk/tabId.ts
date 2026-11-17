// The tab's name for the relay: kept in `sessionStorage`, renewed when a copy of it exists in another tab.
const KEY = "desk-tab";
const CHANNEL = "desk-tab";
const WAIT = 150;

/** An id no other open tab holds. A tab opened from another copies its `sessionStorage`, so it asks the others. */
export async function claimTabId(): Promise<string> {
	// A reload keeps the tab's own id even when it has an opener; only a new tab copies storage.
	let id = window.opener && !reloaded() ? fresh() : sessionStorage.getItem(KEY) ?? fresh();
	if (typeof BroadcastChannel !== "function") return keep(id);

	const channel = new BroadcastChannel(CHANNEL);
	let settled = false;
	let clash = false;
	channel.onmessage = ({ data }) => {
		if (data?.id !== id) return;
		if (settled && data.type === "claim") channel.postMessage({ type: "taken", id });
		else clash = true;
	};
	for (let attempt = 0; attempt < 3; attempt++) {
		clash = false;
		channel.postMessage({ type: "claim", id });
		await new Promise((resolve) => setTimeout(resolve, WAIT));
		if (!clash) break;
		id = fresh();
	}
	settled = true;
	return keep(id);
}

function reloaded() {
	const [entry] = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
	return entry?.type === "reload";
}

function fresh() {
	return Math.random().toString(36).slice(2, 10);
}

function keep(id: string) {
	sessionStorage.setItem(KEY, id);
	return id;
}
