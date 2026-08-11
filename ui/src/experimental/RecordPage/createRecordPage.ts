// Builds the curated `page` and the controller that fires events into it.
// Handlers run serially in run order, each in its own try/catch: a thrower is
// skipped half-applied, never taking the page or another source down with it.
import { ref, type Ref } from "vue";
import type { Router } from "vue-router";
import { call, toast } from "frappe-ui";
import { withRunningSource } from "./context";
import { registrationsFor } from "./registry";
import { Surface } from "./surface";
import type {
	HeaderAction,
	PanelSectionItem,
	QuickAction,
	RecordPageApi,
	TabItem,
} from "./types";

export interface RecordPageHost {
	doctype: string;
	docname: string;
	doc: Ref<Record<string, any>>;
	meta: Ref<any>;
	perms: () => Record<string, any>;
	isDirty: () => boolean;
	save: () => Promise<void>;
	reload: () => Promise<void>;
	router: Router;
}

export interface RecordPageController {
	page: RecordPageApi;
	quickActions: Surface<QuickAction>;
	headerActions: Surface<HeaderAction>;
	tabs: Surface<TabItem>;
	panelSections: Surface<PanelSectionItem>;
	/** The replay: clears every surface, then runs every source's `refresh` in run order. */
	refresh: () => Promise<void>;
	fireEvent: (event: string) => Promise<void>;
	/** True once the first replay has run — before it, surfaces are only built-ins. */
	ready: Ref<boolean>;
}

export function createRecordPage(host: RecordPageHost): RecordPageController {
	const quickActions = new Surface<QuickAction>();
	const headerActions = new Surface<HeaderAction>();
	const tabs = new Surface<TabItem>();
	const panelSections = new Surface<PanelSectionItem>();
	const surfaces = [quickActions, headerActions, tabs, panelSections];

	const page: RecordPageApi = {
		doctype: host.doctype,
		docname: host.docname,
		get doc() {
			return host.doc.value;
		},
		get meta() {
			return host.meta.value;
		},
		get perms() {
			return host.perms();
		},
		get isDirty() {
			return host.isDirty();
		},
		quickActions,
		headerActions,
		tabs,
		panelSections,
		save: () => host.save(),
		reload: () => host.reload(),
		refresh: () => refresh(),
		toast: {
			success: (message) => toast.success(message),
			error: (message) => toast.error(message),
		},
		call: (method, params) => call(method, params),
		router: host.router,
	};

	const ready = ref(false);

	async function refresh() {
		for (const surface of surfaces) surface.reset();
		await fireEvent("refresh");
		ready.value = true;
	}

	async function fireEvent(event: string) {
		for (const { source, handlers } of registrationsFor(host.doctype)) {
			const handler = handlers[event];
			if (!handler) continue;
			await withRunningSource(source, async () => {
				try {
					await handler(page);
				} catch (error) {
					console.error(`[record-page] ${source}.${event} on ${host.doctype} threw`, error);
				}
			});
		}
	}

	return { page, quickActions, headerActions, tabs, panelSections, refresh, fireEvent, ready };
}
