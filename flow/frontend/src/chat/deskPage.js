import { onBeforeUnmount, ref } from "vue";

// What the Desk page beside the panel is, for the crumb over the box: a form's record, a list or
// a report, as `{ key, parent, label }`, `label` left out for a plain list. A workspace or any
// other page has no crumb, nor does a page outside Desk. It follows Desk's router as the page
// changes.
export function useDeskPage(win = window) {
	const page = ref(readDeskPage(win));
	const router = win.frappe?.router;
	if (typeof router?.on !== "function") return page;
	// the router sets the route before it says so, the page's view comes after
	const update = () => setTimeout(() => (page.value = readDeskPage(win)));
	router.on("change", update);
	onBeforeUnmount(() => router.off?.("change", update));
	return page;
}

export function readDeskPage(win = window) {
	const frappe = win.frappe;
	if (typeof frappe?.get_route !== "function") return null;
	const route = frappe.get_route() ?? [];
	const key = route.join("/");
	const [view, doctype, name] = route;
	const url = win.location.pathname + win.location.search;
	if (view === "Form" && doctype && name) {
		// a record not yet saved has a placeholder name, "new-sales-invoice-…"
		const unsaved = name.startsWith("new-");
		const record = unsaved ? null : { doctype, name };
		return { key, url, parent: doctype, label: unsaved ? "New" : name, record };
	}
	// a list is its doctype alone; another view of it (Report, Kanban…) is named after it
	if (view === "List" && doctype) {
		const kind = name && name !== "List" ? name : null;
		return { key, url, parent: doctype, label: kind };
	}
	if (view === "query-report" && doctype) return { key, url, parent: "Report", label: doctype };
	return null;
}

// The panel's "Open in new tab" hands its page to the tab it opens, so Flow there still names
// where the user came from. The new tab takes it once, if it is fresh, and keeps it over a reload
const HANDOFF = "flow:from-page";
const FRESH = 30_000; // ms

export function handOffPage(page) {
	try {
		localStorage.setItem(HANDOFF, JSON.stringify({ ...page, at: Date.now() }));
	} catch {
		// no storage: the new tab simply has no crumb
	}
}

export function cameFrom() {
	try {
		const kept = sessionStorage.getItem(HANDOFF);
		if (kept) return JSON.parse(kept);
		const raw = localStorage.getItem(HANDOFF);
		localStorage.removeItem(HANDOFF);
		const page = raw && JSON.parse(raw);
		if (!page || Date.now() - page.at > FRESH) return null;
		sessionStorage.setItem(HANDOFF, raw);
		return page;
	} catch {
		return null;
	}
}
