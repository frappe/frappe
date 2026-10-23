// Where focus lands as the Create dialog opens and closes, and Ctrl/Cmd+Enter or S from inside it.
// The real Dialog and FormLayout draw the form; the server answers through a faked fetch.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetFormLayouts } from "@/recordPage";
import { registerShell, routeFor } from "@/router/routeFor";
import { closeCreates, createRequests, openCreate, registerCreateDialog } from "@/shell/create";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import CreateDialog from "../CreateDialog.vue";

const META = {
	name: "Lead",
	autoname: "naming_series:",
	fields: [
		{ fieldname: "lead_owner", fieldtype: "Data", label: "Lead Owner", read_only: 1 },
		{ fieldname: "title", fieldtype: "Data", label: "Title", reqd: 1 },
		{ fieldname: "source", fieldtype: "Data", label: "Source" },
	],
	permissions: [{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 1 }],
};
const LAYOUTS = {
	layouts: [],
	fallback: [{ sections: [{ columns: [{ fields: ["lead_owner", "title", "source"] }] }] }],
	dialog: true,
};

const fetchMock = vi.fn<typeof fetch>();
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

async function open(onSettled = () => {}) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/:doctype", name: "list", component: { render: () => null } },
			{ path: "/:doctype/new", name: "new-record", component: { render: () => null } },
			{ path: "/:doctype/:name", name: "record", component: { render: () => null } },
		],
	});
	registerShell({
		boot: { app: "crm", shell_base: "/apps/crm", prefixes: { crm: { app: "crm", modular: false } } } as unknown as Boot,
		addresses: new Addresses({ doctypes: { Lead: ["lead", "crm"] }, modules: { crm: "CRM" } }),
		router,
	});
	await router.push(routeFor("Lead"));
	const answer = { settled: false };
	void openCreate("Lead").then(() => {
		answer.settled = true;
		onSettled();
	});
	const app = createApp(CreateDialog, { request: createRequests.value.at(-1)! });
	app.use(router);
	app.mount(document.body.appendChild(document.createElement("div")));
	apps.push(app);
	await settle();
	return answer;
}

function focused() {
	return document.activeElement as HTMLElement;
}

async function typeIntoFocused(value: string) {
	(focused() as HTMLInputElement).value = value;
	focused().dispatchEvent(new Event("input", { bubbles: true }));
	await settle();
}

async function pressSave(target: Element, keys: KeyboardEventInit) {
	const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true, ...keys });
	target.dispatchEvent(event);
	await settle();
	return event;
}

function dialogButton(label: string) {
	return [...document.querySelectorAll<HTMLElement>("[role='dialog'] button")].find(
		(element) => element.textContent?.trim() === label || element.getAttribute("aria-label") === label
	)!;
}

it("opens with focus in the first editable field, past a read-only one", async () => {
	await open();

	expect(focused().closest("[data-fieldname]")?.getAttribute("data-fieldname")).toBe("title");
	expect(focused().tagName).toBe("INPUT");
});

it("inserts on Ctrl+Enter pressed where the focus opens", async () => {
	const answer = await open();
	await typeIntoFocused("Big deal");

	await pressSave(focused(), { ctrlKey: true });

	expect(inserts()).toEqual([expect.objectContaining({ title: "Big deal" })]);
	expect(answer.settled).toBe(true);
});

it("leaves focus where the caller puts it after a Ctrl+Enter save", async () => {
	const field = document.body.appendChild(document.createElement("input"));
	await open(() => field.focus());
	await typeIntoFocused("Big deal");

	await pressSave(focused(), { ctrlKey: true });

	expect(inserts()).toHaveLength(1);
	expect(focused()).toBe(field);
});

it("leaves focus where the caller puts it after an Escape", async () => {
	const field = document.body.appendChild(document.createElement("input"));
	await open(() => field.focus());

	focused().dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
	await settle();

	expect(inserts()).toEqual([]);
	expect(focused()).toBe(field);
});

it("inserts on Cmd+Enter with focus on the dialog's own buttons", async () => {
	const answer = await open();
	await typeIntoFocused("Big deal");
	dialogButton("Close").focus();
	expect(focused()).toBe(dialogButton("Close"));

	await pressSave(focused(), { metaKey: true });

	expect(inserts()).toHaveLength(1);
	expect(answer.settled).toBe(true);
});

it("inserts on Cmd+S and blocks the browser's save", async () => {
	const answer = await open();
	await typeIntoFocused("Big deal");

	const event = await pressSave(focused(), { key: "s", metaKey: true });

	expect(inserts()).toEqual([expect.objectContaining({ title: "Big deal" })]);
	expect(answer.settled).toBe(true);
	expect(event.defaultPrevented).toBe(true);
});

it("ignores the repeats of a held Ctrl+S", async () => {
	await open();
	await typeIntoFocused("Big deal");

	await pressSave(focused(), { key: "s", ctrlKey: true, repeat: true });

	expect(inserts()).toEqual([]);
});

it("does not save on Ctrl+Enter outside the dialog", async () => {
	await open();
	await typeIntoFocused("Big deal");

	await pressSave(document.body, { ctrlKey: true });

	expect(inserts()).toEqual([]);
});

it("ignores the repeats of a held Ctrl+Enter", async () => {
	await open();
	await typeIntoFocused("Big deal");

	await pressSave(focused(), { ctrlKey: true, repeat: true });

	expect(inserts()).toEqual([]);
});

it("saves only the top dialog when two Create dialogs are stacked", async () => {
	const below = await open();
	const above = await open();
	await typeIntoFocused("Top deal");

	await pressSave(focused(), { ctrlKey: true });

	expect(inserts()).toEqual([expect.objectContaining({ title: "Top deal" })]);
	expect(above.settled).toBe(true);
	expect(below.settled).toBe(false);
});
