// The page an app declares in place of a doctype's list or record page, at the main address.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import type { ReplacementContribution } from "@/contributions/types";
import { createShellRouter } from "@/router";
import { registerShell, routeFor, urlFor } from "@/router/routeFor";

const setups = vi.hoisted(() => ({ count: 0 }));
const fake = vi.hoisted(() => ({ replacements: [] as ReplacementContribution[] }));

const DeclaredPage = defineComponent({
	props: { doctype: String, name: String },
	setup(props) {
		setups.count++;
		return () =>
			h("div", {
				"data-page": "declared",
				"data-doctype": props.doctype,
				"data-name": props.name,
			});
	},
});

function declared(doctype: string, key: "record" | "list"): ReplacementContribution {
	return { app: "erpnext", doctype, key, foreign: false, component: async () => DeclaredPage };
}

vi.mock("virtual:frappe/contributions", () => ({
	default: {
		doctypes: [],
		pages: [],
		itemTypes: [],
		get replacements() {
			return fake.replacements;
		},
	},
}));

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => h("div", { "data-page": "list" }) } }));
vi.mock("@/pages/Record.vue", () => ({
	default: { render: () => h("div", { "data-page": "record" }) },
}));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		"Purchase Invoice": ["purchase-invoice", "accounts"],
		"Accounts Settings": ["accounts-settings", "accounts"],
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
		declared("Sales Invoice", "record"),
		declared("Sales Invoice", "list"),
		declared("Accounts Settings", "list"),
	];
	await registerContributions(["frappe", "erpnext"]);
});

beforeEach(() => {
	setups.count = 0;
	warn = vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	warn.mockRestore();
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
	});

	it("opens the declared list page at the main address, with the doctype only", async () => {
		const { root, router } = await mount(modular, `${prefix}/sales-invoice`);

		expect(router.currentRoute.value.name).toBe("list");
		expect(shown(root)).toEqual({ page: "declared", doctype: "Sales Invoice" });
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
		expect(urlFor("Purchase Invoice", null, { standard: true })).toBe(
			`${base}/purchase-invoice`
		);
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
