// The index's filter box searches as the palette does: its rows under the tiles, in the one selection.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { acts, type ActEntry } from "@/acts/dispatcher";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import IndexPage from "../IndexPage.vue";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	runMethod: fake.runMethod,
}));

type BootApp = NonNullable<Boot["apps"]>[number];

const APPS: BootApp[] = [
	{ app: "frappe", title: "Framework", logo: null, kind: "prefix", route: "/apps/desk", hidden: false },
	{ app: "erpnext", title: "ERPNext", logo: null, kind: "prefix", route: "/apps/erpnext", hidden: false },
	{ app: "crm", title: "CRM", logo: null, kind: "prefix", route: "/apps/crm", hidden: false },
];

const ERPNEXT = "/apps/erpnext";
const CRM = "/apps/crm";

const PLACES = {
	doctypes: [
		{ name: "Sales Invoice", app: "erpnext", route: `${ERPNEXT}/sales-invoice`, can_create: true },
		{ name: "Customer", app: "erpnext", route: `${ERPNEXT}/customer`, can_create: true },
		{ name: "CRM Deal", app: "crm", route: `${CRM}/crm-deal`, can_create: false },
	],
	apps: [{ app: "crm", title: "CRM", route: "/apps/crm" }],
	titles: { erpnext: "ERPNext", crm: "CRM" },
};

const PALMER = {
	doctype: "Customer",
	name: "Palmer Productions",
	label: "Palmer Productions",
	route: `${ERPNEXT}/customer/Palmer%20Productions`,
};

const mounted: App[] = [];
const releases: (() => void)[] = [];
let assign: ReturnType<typeof vi.fn>;

// The search's chunk loads on the first keystroke; its first transform here outlasts a `waitFor`.
beforeAll(() => import("../indexSearch"), 60000);

beforeEach(() => {
	fake.runMethod.mockReset().mockImplementation(async (method: string, args: { txt?: string }) => {
		if (method === "frappe.shell.palette.places") return { data: PLACES };
		if (method === "frappe.shell.settings.get_panes") return { data: { panes: [], index: [], titles: {} } };
		return { data: args.txt?.toLowerCase().startsWith("palmer") ? [PALMER] : [] };
	});
	assign = vi.fn();
	vi.stubGlobal("location", { ...window.location, assign });
});

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	releases.splice(0).forEach((release) => release());
	document.body.innerHTML = "";
	delete document.documentElement.dataset.flow;
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

async function mount() {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(IndexPage);
	const session = { timezone: "Asia/Kolkata", user: { name: "reader@example.com" } };
	app.provide("boot", { app: null, apps: APPS, session, prefixes: {} } as unknown as Boot);
	app.provide("addresses", new Addresses({ doctypes: {}, modules: {}, singles: [] }));
	// The index's router: `home` only, so no record route resolves here.
	app.use(createRouter({ history: createMemoryHistory(), routes: [{ path: "/", name: "home", component: {} }] }));
	app.mount(host);
	mounted.push(app);
	await nextTick();
	return host;
}

function box(host: HTMLElement) {
	return host.querySelector<HTMLInputElement>("input")!;
}

async function type(host: HTMLElement, text: string) {
	box(host).value = text;
	box(host).dispatchEvent(new Event("input"));
	await nextTick();
}

async function press(host: HTMLElement, key: string) {
	box(host).dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
	await nextTick();
}

function rows(host: HTMLElement) {
	return [...host.querySelectorAll<HTMLElement>("[data-result]")].map((row) => row.dataset.result);
}

function headings(host: HTMLElement) {
	return [...host.querySelectorAll("[data-index-results] h2")].map((h) => h.textContent?.trim());
}

function selected(host: HTMLElement) {
	return [...host.querySelectorAll<HTMLElement>("[data-selected]")].map(
		(item) => item.dataset.app ?? item.dataset.result
	);
}

function asked(method: string) {
	return fake.runMethod.mock.calls.filter(([name]) => name === method);
}

function registerShellAct(name: string, label: string, run: () => void) {
	const entry: ActEntry = { item: { name, label, run }, hidden: false };
	releases.push(
		acts.register({
			surfaces: { shell: () => [entry] },
			context: () => ({}),
			passes: () => true,
			settled: () => undefined,
			hold: async (work) => work(),
			failed: () => {},
		})
	);
}

describe("the index's search", () => {
	it("asks nothing until the first keystroke, and the places once", async () => {
		const host = await mount();
		expect(fake.runMethod).not.toHaveBeenCalled();
		expect(host.querySelector("[data-index-results]")).toBeNull();

		await type(host, "s");
		await type(host, "sales inv");
		await vi.waitFor(() => expect(rows(host)).toContain("doctype:Sales Invoice"));
		expect(asked("frappe.shell.palette.places")).toHaveLength(1);
	});

	it("draws Go to and Create under the tiles, and Enter opens the first row", async () => {
		const host = await mount();
		await type(host, "sales inv");
		await vi.waitFor(() =>
			expect(rows(host)).toEqual(["doctype:Sales Invoice", "create:Sales Invoice"])
		);
		expect(headings(host)).toEqual(["Go to", "Create"]);
		expect(selected(host)).toEqual(["doctype:Sales Invoice"]);

		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith(`${ERPNEXT}/sales-invoice`);
	});

	it("leaves the apps out of Go to, so a matching app's tile ranks first", async () => {
		const host = await mount();
		await type(host, "crm");
		await vi.waitFor(() => expect(rows(host)).toContain("doctype:CRM Deal"));
		expect(rows(host)).not.toContain("app:crm");
		expect(selected(host)).toEqual(["crm"]);

		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/apps/crm");
	});

	it("moves from the tiles into the rows with the arrow keys", async () => {
		const host = await mount();
		await type(host, "crm");
		await vi.waitFor(() => expect(rows(host)).toContain("doctype:CRM Deal"));

		await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["doctype:CRM Deal"]);
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith(`${CRM}/crm-deal`);
	});

	it("finds a record by name and opens it at its own app's address", async () => {
		const host = await mount();
		await type(host, "Palmer");
		await vi.waitFor(() => expect(rows(host)).toEqual(["record:Customer/Palmer Productions"]));
		expect(headings(host)).toEqual(["Records"]);
		expect(asked("frappe.desk.palette.search_records").at(-1)?.[1]).toEqual({ txt: "Palmer" });

		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith(PALMER.route);
	});

	it("runs Create through the shell act, by Enter and by a click", async () => {
		const perform = vi.spyOn(acts, "perform").mockResolvedValue(undefined);
		const host = await mount();
		await type(host, "new customer");
		await vi.waitFor(() => expect(rows(host)).toEqual(["create:Customer"]));

		await press(host, "Enter");
		expect(perform).toHaveBeenLastCalledWith("shell.create", "Customer");

		perform.mockClear();
		host.querySelector<HTMLElement>("[data-result='create:Customer']")!.click();
		expect(perform).toHaveBeenLastCalledWith("shell.create", "Customer");
	});

	it("draws the shell's acts under Desk", async () => {
		const ran = vi.fn();
		registerShellAct("toggle_theme", "Toggle theme", ran);
		const host = await mount();
		await type(host, "theme");
		await vi.waitFor(() => expect(rows(host)).toEqual(["act:shell.toggle_theme"]));
		expect(headings(host)).toEqual(["Desk"]);

		await press(host, "Enter");
		await vi.waitFor(() => expect(ran).toHaveBeenCalled());
	});

	it("draws Ask Flow last, only while Flow's launcher is ready", async () => {
		const host = await mount();
		await type(host, "sales inv");
		await vi.waitFor(() => expect(rows(host)).toContain("doctype:Sales Invoice"));
		expect(rows(host)).not.toContain("ask-flow");

		document.documentElement.dataset.flow = "ready";
		await type(host, "sales invo");
		await vi.waitFor(() => expect(rows(host).at(-1)).toBe("ask-flow"));
	});

	it("shows a row's full text on hover", async () => {
		const host = await mount();
		await type(host, "sales inv");
		await vi.waitFor(() => expect(rows(host)).toContain("create:Sales Invoice"));
		const row = host.querySelector("[data-result='create:Sales Invoice'] [title]");
		expect(row?.getAttribute("title")).toBe("New Sales Invoice ERPNext");
	});

	it("clears the rows with the box on Esc", async () => {
		const host = await mount();
		await type(host, "sales inv");
		await vi.waitFor(() => expect(rows(host)).toContain("doctype:Sales Invoice"));

		await press(host, "Escape");
		await nextTick();
		expect(rows(host)).toEqual([]);
		expect(host.querySelectorAll("a[data-app]")).toHaveLength(3);
	});
});
