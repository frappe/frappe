// The page an app declares in place of a doctype's list or record page, at the main address.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, useAttrs, type Component } from "vue";
import {
	createMemoryHistory,
	createRouter,
	isNavigationFailure,
	NavigationFailureType,
	RouterView,
} from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import type { ReplacementContribution } from "@/contributions/types";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { clearLoadedPages, loadedPage } from "@/router/mainPage";
import { registerShell, routeFor, urlFor } from "@/router/routeFor";

registerStandardPages(standardPages);

const setups = vi.hoisted(() => ({ count: 0, attrs: [] as object[] }));
// Set by a test: the standard record page's leave and update guards refuse the navigation.
const guard = vi.hoisted(() => ({ block: false }));
const fake = vi.hoisted(() => ({ replacements: [] as ReplacementContribution[] }));
// Set by a test: how many more times the flaky page fails to load before it loads.
const flaky = vi.hoisted(() => ({ failures: 0 }));
// Set by a test: the slow page's code, which arrives when the test says.
const slow = vi.hoisted(() => ({ load: new Promise<unknown>(() => {}) }));

const DeclaredPage = defineComponent({
	props: { doctype: String, name: String },
	setup(props) {
		setups.count++;
		setups.attrs.push({ ...useAttrs() });
		return () =>
			h("div", {
				"data-page": "declared",
				"data-doctype": props.doctype,
				"data-name": props.name,
			});
	},
});

const salesInvoicePage = vi.fn(async () => DeclaredPage);
const singleListPage = vi.fn(async () => DeclaredPage);
const flakyPage = vi.fn(async () => {
	if (flaky.failures-- > 0) throw new Error("the page failed to load once");
	return DeclaredPage;
});

function declared(
	doctype: string,
	key: "record" | "list",
	component: ReplacementContribution["component"] = async () => DeclaredPage
): ReplacementContribution {
	return { app: "erpnext", doctype, key, foreign: false, component };
}

vi.mock("virtual:frappe/contributions", () => ({
	default: {
		doctypes: [],
		pages: [],
		itemTypes: [],
		acts: [],
		get replacements() {
			return fake.replacements;
		},
	},
}));

vi.mock("@/pages/List.vue", () => ({
	default: { render: () => h("div", { "data-page": "list" }) },
}));
vi.mock("@/pages/Record.vue", async () => {
	const { onBeforeRouteLeave, onBeforeRouteUpdate } = await import("vue-router");
	return {
		default: defineComponent({
			setup() {
				onBeforeRouteLeave(() => !guard.block);
				onBeforeRouteUpdate(() => !guard.block);
				return () => h("div", { "data-page": "record" });
			},
		}),
	};
});
vi.mock("@/pages/NewRecord.vue", async () => {
	const { onBeforeRouteLeave } = await import("vue-router");
	return {
		default: defineComponent({
			setup() {
				onBeforeRouteLeave(() => !guard.block);
				return () => h("div", { "data-page": "new-record" });
			},
		}),
	};
});
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NothingToOpen.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		"Purchase Invoice": ["purchase-invoice", "accounts"],
		"Accounts Settings": ["accounts-settings", "accounts"],
		"Journal Entry": ["journal-entry", "accounts"],
		"Payment Entry": ["payment-entry", "accounts"],
		"Delivery Note": ["delivery-note", "accounts"],
	},
	modules: { accounts: "Accounts" },
	singles: ["Accounts Settings"],
});

function boot(modular: boolean): Boot {
	return {
		app: "erpnext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular } },
	} as unknown as Boot;
}

const apps: ReturnType<typeof createApp>[] = [];
let warn: ReturnType<typeof vi.spyOn>;

beforeAll(async () => {
	fake.replacements = [
		declared("Sales Invoice", "record", salesInvoicePage),
		declared("Sales Invoice", "list"),
		declared("Accounts Settings", "list", singleListPage),
		declared("Journal Entry", "record", async () => {
			throw new Error("the page failed to load");
		}),
		declared("Payment Entry", "record", flakyPage),
		declared("Delivery Note", "record", () => slow.load),
	];
	await registerContributions(["frappe", "erpnext"]);
});

beforeEach(() => {
	setups.count = 0;
	setups.attrs = [];
	guard.block = false;
	flaky.failures = 0;
	for (const page of [salesInvoicePage, singleListPage, flakyPage]) page.mockClear();
	clearLoadedPages();
	warn = vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

async function settle() {
	for (let turn = 0; turn < 5; turn++) {
		await nextTick();
		await new Promise((resolve) => setTimeout(resolve));
	}
}

async function mount(modular: boolean, path: string) {
	const router = createShellRouter(boot(modular), addresses);
	registerShell({ boot: boot(modular), addresses, router });
	await router.push(path);
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(RouterView) }));
	app.use(router);
	app.provide("addresses", addresses);
	app.mount(root);
	apps.push(app);
	await settle();
	return { root, router };
}

async function blocked(navigation: Promise<unknown>) {
	return isNavigationFailure(await navigation, NavigationFailureType.aborted);
}

function failure(root: HTMLElement) {
	return root.querySelector("[role='alert']")?.textContent;
}

function tryAgain(root: HTMLElement) {
	const retry = [...root.querySelectorAll("button")].find(
		(button) => button.textContent?.trim() === "Try again"
	);
	retry!.click();
}

function shown(root: HTMLElement) {
	const page = root.querySelector<HTMLElement>("[data-page]");
	return page && { ...page.dataset };
}

describe.each([
	{ shape: "flat", modular: false, prefix: "" },
	{ shape: "modular", modular: true, prefix: "/accounts" },
])("a declared page on a $shape app", ({ modular, prefix }) => {
	it("opens the declared record page at the main address, with doctype and name", async () => {
		const { root, router } = await mount(modular, `${prefix}/sales-invoice/SI-001`);

		expect(router.currentRoute.value.name).toBe("record");
		expect(shown(root)).toEqual({ page: "declared", doctype: "Sales Invoice", name: "SI-001" });
		expect(setups.attrs).toEqual([{}]);
	});

	it("opens the declared list page at the main address, with the doctype only", async () => {
		const { root, router } = await mount(modular, `${prefix}/sales-invoice`);

		expect(router.currentRoute.value.name).toBe("list");
		expect(shown(root)).toEqual({ page: "declared", doctype: "Sales Invoice" });
		expect(setups.attrs).toEqual([{}]);
	});

	it("keeps the standard record page at the second address", async () => {
		const { root } = await mount(modular, `${prefix}/sales-invoice/SI-001/record`);

		expect(shown(root)).toEqual({ page: "record" });
	});

	it("keeps the standard list page at the second address and for a saved view", async () => {
		const standard = await mount(modular, `${prefix}/sales-invoice/view/list`);
		const saved = await mount(modular, `${prefix}/sales-invoice/view/list/open`);

		expect(shown(standard.root)).toEqual({ page: "list" });
		expect(shown(saved.root)).toEqual({ page: "list" });
	});

	it("opens the standard pages at the main address when nothing is declared", async () => {
		const list = await mount(modular, `${prefix}/purchase-invoice`);
		const record = await mount(modular, `${prefix}/purchase-invoice/PI-001`);

		expect(shown(list.root)).toEqual({ page: "list" });
		expect(shown(record.root)).toEqual({ page: "record" });
	});

	it("sets the declared record page up again for another record", async () => {
		const { root, router } = await mount(modular, `${prefix}/sales-invoice/SI-001`);
		await router.push(`${prefix}/sales-invoice/SI-002`);
		await settle();

		expect(shown(root)?.name).toBe("SI-002");
		expect(setups.count).toBe(2);
	});

	it("changes the address and shows the error page when the declared page does not load", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/PI-001`);
		const error = vi.spyOn(console, "error").mockImplementation(() => {});

		await router.push(`${prefix}/journal-entry/JE-001`);
		await settle();
		error.mockRestore();

		expect(router.currentRoute.value.params.name).toBe("JE-001");
		expect(shown(root)).toBeNull();
		expect(failure(root)).toContain("This page could not load.");
	});

	it("changes the address and draws the frame's skeleton while the page's code loads", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/PI-001`);
		let arrive!: (page: Component) => void;
		slow.load = new Promise((resolve) => (arrive = resolve));

		await router.push(`${prefix}/delivery-note/DN-001`);
		await nextTick();

		expect(router.currentRoute.value.params.name).toBe("DN-001");
		expect(root.querySelector("[data-frame-skeleton]")).not.toBeNull();
		expect(shown(root)).toBeNull();

		arrive(DeclaredPage);
		await settle();

		expect(root.querySelector("[data-frame-skeleton]")).toBeNull();
		expect(shown(root)).toEqual({ page: "declared", doctype: "Delivery Note", name: "DN-001" });
	});

	it("keeps the standard record page's guard between two records", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/PI-001`);
		guard.block = true;

		expect(await blocked(router.push(`${prefix}/purchase-invoice/PI-002`))).toBe(true);
		expect(router.currentRoute.value.params.name).toBe("PI-001");
		expect(shown(root)).toEqual({ page: "record" });
	});

	it("keeps the standard record page's guard when it leaves for the list", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice`);
		await router.push(`${prefix}/purchase-invoice/PI-001`);
		await settle();
		guard.block = true;

		expect(await blocked(router.push(`${prefix}/purchase-invoice`))).toBe(true);
		expect(router.currentRoute.value.name).toBe("record");
		expect(shown(root)).toEqual({ page: "record" });
	});

	it("keeps the standard record page's guard at its second address", async () => {
		const { root, router } = await mount(modular, `${prefix}/sales-invoice/SI-001/record`);
		guard.block = true;

		expect(await blocked(router.push(`${prefix}/sales-invoice/SI-002/record`))).toBe(true);
		expect(await blocked(router.push(`${prefix}/sales-invoice`))).toBe(true);
		expect(router.currentRoute.value.params.name).toBe("SI-001");
		expect(shown(root)).toEqual({ page: "record" });
	});

	it("keeps the new record page's guard", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/new`);
		guard.block = true;

		expect(await blocked(router.push(`${prefix}/purchase-invoice`))).toBe(true);
		expect(router.currentRoute.value.name).toBe("new-record");
		expect(shown(root)).toEqual({ page: "new-record" });
	});

	it("keeps the standard record page's guard on the way to a declared record", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/PI-001`);
		guard.block = true;

		expect(await blocked(router.push(`${prefix}/sales-invoice/SI-001`))).toBe(true);
		expect(router.currentRoute.value.params.name).toBe("PI-001");
		expect(shown(root)).toEqual({ page: "record" });
	});

	it.each([
		["a standard record", "/purchase-invoice/PI-001", { page: "record" }],
		["a standard list", "/purchase-invoice", { page: "list" }],
		[
			"a declared page",
			"/sales-invoice/SI-001",
			{ page: "declared", doctype: "Sales Invoice", name: "SI-001" },
		],
	])("shows %s on a return one tick after the navigation, with no skeleton", async (_, path, page) => {
		const { root, router } = await mount(modular, `${prefix}${path}`);
		await router.push("/");
		await settle();
		await router.push(`${prefix}${path}`);
		await nextTick();

		expect(shown(root)).toEqual(page);
		expect(root.querySelector("[data-frame-skeleton]")).toBeNull();
	});

	it("loads the declared page once, for the canonical address", async () => {
		const { root, router } = await mount(modular, `${prefix}/Sales Invoice/SI-001`);

		expect(router.currentRoute.value.path).toBe(`${prefix}/sales-invoice/SI-001`);
		expect(shown(root)).toEqual({ page: "declared", doctype: "Sales Invoice", name: "SI-001" });
		expect(salesInvoicePage).toHaveBeenCalledOnce();
	});

	it("never loads the list page declared for a single", async () => {
		const { root, router } = await mount(modular, `${prefix}/accounts-settings`);

		expect(router.currentRoute.value.name).toBe("record");
		expect(shown(root)).toEqual({ page: "record" });
		expect(singleListPage).not.toHaveBeenCalled();
	});

	it("opens the declared page on the next try after it failed to load", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/PI-001`);
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		flaky.failures = 1;

		await router.push(`${prefix}/payment-entry/PE-001`);
		await settle();
		expect(failure(root)).toContain("This page could not load.");
		error.mockRestore();
		await router.push(`${prefix}/purchase-invoice/PI-001`);
		await settle();
		await router.push(`${prefix}/payment-entry/PE-001`);
		await settle();

		expect(shown(root)).toEqual({ page: "declared", doctype: "Payment Entry", name: "PE-001" });
		expect(flakyPage).toHaveBeenCalledTimes(2);
	});

	it("reloads the address from Try again when its declared page fails to load", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/PI-001`);
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		const reload = vi.spyOn(window.location, "reload").mockImplementation(() => {});

		await router.push(`${prefix}/journal-entry/JE-001`);
		await settle();
		error.mockRestore();
		tryAgain(root);

		expect(reload).toHaveBeenCalledOnce();
	});

	it("shows the next page once the reader leaves a page that failed to load", async () => {
		const { root, router } = await mount(modular, `${prefix}/purchase-invoice/PI-001`);
		const error = vi.spyOn(console, "error").mockImplementation(() => {});

		await router.push(`${prefix}/journal-entry/JE-001`);
		await settle();
		error.mockRestore();
		await router.push(`${prefix}/purchase-invoice/PI-002`);
		await settle();

		expect(failure(root)).toBeUndefined();
		expect(shown(root)).toEqual({ page: "record" });
	});

	it("builds the second address with standard only when the page is replaced", async () => {
		await mount(modular, "/");
		const base = `/apps/erpnext${prefix}`;

		expect(urlFor("Sales Invoice", "SI-001", { standard: true })).toBe(
			`${base}/sales-invoice/SI-001/record`
		);
		expect(urlFor("Sales Invoice", null, { standard: true })).toBe(
			`${base}/sales-invoice/view/list`
		);
		expect(urlFor("Purchase Invoice", "PI-001", { standard: true })).toBe(
			`${base}/purchase-invoice/PI-001`
		);
		expect(urlFor("Purchase Invoice", null, { standard: true })).toBe(`${base}/purchase-invoice`);
	});

	it("leaves every other link at the main address", async () => {
		await mount(modular, "/");

		expect(routeFor("Sales Invoice", "SI-001")).toMatchObject({ name: "record" });
		expect(routeFor("Sales Invoice")).toMatchObject({ name: "list" });
		expect(routeFor("Sales Invoice", null, { view: "open", standard: true })).toMatchObject({
			name: "saved-view",
		});
	});
});

describe("a list page declared for a single", () => {
	it("warns once, naming the doctype and the app, when the router is created", () => {
		createShellRouter(boot(false), addresses);

		expect(warn).toHaveBeenCalledOnce();
		expect(warn).toHaveBeenCalledWith(
			"[frappe] 'erpnext' replaces the list page of 'Accounts Settings', a single with no " +
				"list; the declaration is ignored."
		);
	});

	it("still sends the list address to the document", async () => {
		const { root, router } = await mount(false, "/accounts-settings");

		expect(router.currentRoute.value.name).toBe("record");
		expect(router.currentRoute.value.params.name).toBe("Accounts Settings");
		expect(shown(root)).toEqual({ page: "record" });
	});
});

describe("a page whose code failed to load", () => {
	it("loads again at the next address that uses the same page", async () => {
		let failures = 1;
		const loader = vi.fn(async () => {
			if (failures-- > 0) throw new Error("the page failed to load once");
			return { default: DeclaredPage };
		});
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [{ path: "/note/:name", component: loadedPage(loader), props: true }],
		});
		const root = document.createElement("div");
		document.body.appendChild(root);
		const app = createApp(defineComponent({ render: () => h(RouterView) }));
		app.use(router);
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		await router.push("/note/one");
		app.mount(root);
		apps.push(app);
		await settle();
		error.mockRestore();

		expect(failure(root)).toContain("This page could not load.");

		await router.push("/note/two");
		await settle();

		expect(failure(root)).toBeUndefined();
		expect(shown(root)).toEqual({ page: "declared", name: "two" });
		expect(loader).toHaveBeenCalledTimes(2);
	});
});
