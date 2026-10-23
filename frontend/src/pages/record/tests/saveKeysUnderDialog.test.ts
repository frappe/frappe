// Ctrl/Cmd+S on a record page with a dialog over it: a Create dialog saves itself, and the page never saves.
// The real Dialog draws each dialog in its portal; the server answers through a faked fetch.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetFormLayouts } from "@/recordPage";
import { createPageDialogs } from "@/recordPage/dialog";
import { registerShell } from "@/router/routeFor";
import { closeCreates, createDialog, createRequests, openCreate, registerCreateDialog } from "@/shell/create";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import CreateDialog from "@/pages/create/CreateDialog.vue";
import PageDialogs from "../dialogs/PageDialogs.vue";
import { useSaveKeys } from "../recordSave";

const META = {
	name: "Lead",
	fields: [{ fieldname: "title", fieldtype: "Data", label: "Title", reqd: 1 }],
	permissions: [{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 1 }],
};
const LAYOUTS = { layouts: [], fallback: [{ sections: [{ columns: [{ fields: ["title"] }] }] }], dialog: true };

const fetchMock = vi.fn<typeof fetch>();
const pageSave = vi.fn();
const apps: App[] = [];

function json(body: unknown) {
	return new Response(JSON.stringify(body), { status: 200 });
}

function inserts() {
	return fetchMock.mock.calls
		.filter(([, init]) => init?.method === "POST")
		.map(([, init]) => JSON.parse(String(init!.body)));
}

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	clearDataCache();
	setSession({
		user: { name: "test@example.com", full_name: "Test", email: "test@example.com", user_image: null, document_follow_notify: false },
		roles: ["Sales User"],
		lang: "en",
		timezone: "Asia/Kolkata",
		defaults: {},
	});
	registerCreateDialog(CreateDialog);
	closeCreates();
	pageSave.mockReset();
	fetchMock.mockReset().mockImplementation(async (url, init) => {
		const path = new URL(String(url), "http://x").pathname;
		if (path.endsWith("/meta")) return json({ data: META });
		if (path.endsWith(".get_form_layouts")) return json({ data: LAYOUTS });
		if (path.endsWith(".get_new_doc")) return json({ data: { doctype: "Lead", name: "new-lead-1" } });
		return json({ data: { ...JSON.parse(String(init!.body)), name: "LEAD-0001", doctype: "Lead" } });
	});
	vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	closeCreates();
	resetSession();
	vi.unstubAllGlobals();
});

async function settle() {
	for (let turn = 0; turn < 6; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 20));
		await nextTick();
	}
}

/** A record page's save keys, its own dialog stack and the shell's Create host, as the desk draws them. */
function mountRecordPage() {
	const pageDialogs = createPageDialogs({ isReplaying: () => false, hold: async (work) => work() });
	const Page = defineComponent({
		setup() {
			useSaveKeys({ save: pageSave, unsaved: () => true });
			return () => [
				h("main", [h("input", { name: "record-field" }), h(PageDialogs, { controller: { dialogs: pageDialogs.entries } })]),
				createRequests.value.map((request) => h(createDialog() as Component, { key: request.id, request })),
			];
		},
	});
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:any(.*)", component: { render: () => null } }],
	});
	registerShell({
		boot: { app: "crm", shell_base: "/apps/crm", prefixes: { crm: { app: "crm", modular: false } } } as unknown as Boot,
		addresses: new Addresses({ doctypes: { Lead: ["lead", "crm"] }, modules: { crm: "CRM" } }),
		router,
	});
	const app = createApp(Page);
	app.use(router);
	app.mount(document.body.appendChild(document.createElement("div")));
	apps.push(app);
	return pageDialogs.api;
}

function focused() {
	return document.activeElement as HTMLElement;
}

async function typeIntoFocused(value: string) {
	(focused() as HTMLInputElement).value = value;
	focused().dispatchEvent(new Event("input", { bubbles: true }));
	await settle();
}

async function pressCtrlS(target: Element) {
	const event = new KeyboardEvent("keydown", { key: "s", ctrlKey: true, bubbles: true, cancelable: true });
	target.dispatchEvent(event);
	await settle();
	return event;
}

it("inserts the new record on Ctrl+S in a Create dialog, and does not save the record page", async () => {
	mountRecordPage();
	let answer: unknown;
	void openCreate("Lead").then((result) => (answer = result));
	await settle();
	await typeIntoFocused("Big deal");

	const event = await pressCtrlS(focused());

	expect(inserts()).toEqual([expect.objectContaining({ title: "Big deal" })]);
	expect(answer).toEqual(expect.objectContaining({ name: "LEAD-0001" }));
	expect(pageSave).not.toHaveBeenCalled();
	expect(event.defaultPrevented).toBe(true);
});

it("saves nothing on Ctrl+S in a page.dialog.form, and blocks the browser's save", async () => {
	const dialog = mountRecordPage();
	void dialog.form({ title: "Pick a title", fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }] });
	await settle();
	const input = document.querySelector<HTMLInputElement>("[role='dialog'] input")!;

	const event = await pressCtrlS(input);

	expect(pageSave).not.toHaveBeenCalled();
	expect(inserts()).toEqual([]);
	expect(event.defaultPrevented).toBe(true);
});

it("saves the record page on Ctrl+S with no dialog open", async () => {
	mountRecordPage();
	await settle();

	const event = await pressCtrlS(document.querySelector("input[name='record-field']")!);

	expect(pageSave).toHaveBeenCalledTimes(1);
	expect(event.defaultPrevented).toBe(true);
});
