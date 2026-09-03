// The panel a linked rail item opens. Mounted through `AppShell`: which sidebar is open is
// a fact about the address, so handing the panel its own rows would test a list renderer.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { loadSprite, resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";

// `Module Contents` is the one kind that reads the list it is in, so it is the one that can
// tell the panel's context from the rail's.
const fetchContents = vi.hoisted(() => vi.fn());
vi.mock("@/contents", () => ({ fetchContents }));

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"CRM Lead": ["crm-lead", "fcrm"],
		"Sales Invoice": ["sales-invoice", "accounts"],
	},
	modules: { fcrm: "FCRM", accounts: "Accounts" },
});

const stub = { render: () => null };

async function flush() {
	await Promise.resolve();
	await nextTick();
}

/** The shell, mounted at `path` over one navigation payload. */
async function shell(
	rail: NavigationItem[],
	sidebars: Record<string, NavigationItem[]>,
	path: string
): Promise<{ host: HTMLElement; router: Router }> {
	const boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: { rail, sidebars },
		user: { name: "reader@example.com", full_name: "Reader" },
	} as unknown as Boot;

	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: stub },
			{ path: "/:doctype", name: "list", component: stub },
			{ path: "/:doctype/view/:viewName", name: "saved-view", component: stub },
			{ path: "/:doctype/:name", name: "record", component: stub },
		],
	});
	registerShell({ boot, addresses, router });

	const host = document.createElement("div");
	document.body.appendChild(host);

	const app = createApp(AppShell);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);

	await router.push(path);
	await router.isReady();
	app.mount(host);
	await flush();

	return { host, router };
}

function panel(host: HTMLElement) {
	return host.querySelector("aside");
}

function marked(scope: Element | null) {
	return Array.from(scope?.querySelectorAll("[aria-current='page']") ?? []).map((node) =>
		node.getAttribute("data-key")
	);
}

const invoice: NavigationItem = {
	key: "invoice",
	item_type: "DocType",
	link_to: "Sales Invoice",
};
const lead: NavigationItem = { key: "lead", item_type: "DocType", link_to: "CRM Lead" };
const accounts: NavigationItem = {
	key: "accounts",
	item_type: "Sidebar",
	link_to: "module_def_accounts",
	label: "Accounts",
};
const sidebars = { module_def_accounts: [invoice, lead] };

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	// The shell stamps the sidebar it resolves onto the history entry, and these mount over
	// one window.
	window.history.replaceState(null, "", "/");

	resetNavigationReports();
	resetSprite();
	vi.unstubAllGlobals();
});

describe("what opens the panel", () => {
	it("opens it because of where you are, not because of a click", async () => {
		const { host } = await shell([accounts], sidebars, "/crm-lead");

		// Nothing was clicked: `/crm-lead` is a row inside the Accounts sidebar, and that is all.
		expect(panel(host)?.textContent).toContain("Sales Invoice");
		expect(panel(host)?.textContent).toContain("CRM Lead");
	});

	it("heads it with the rail item's own label", async () => {
		// `sidebars` carries rows, not a record, so the rail item's label is the only title there is.
		const { host } = await shell([accounts], sidebars, "/sales-invoice");
		expect(panel(host)?.textContent).toContain("Accounts");
	});

	it("shows no panel where the address is not inside a sidebar", async () => {
		const deal: NavigationItem = { key: "deal", item_type: "DocType", link_to: "CRM Deal" };
		const { host } = await shell([deal, accounts], sidebars, "/crm-deal");
		expect(panel(host)).toBeNull();
	});

	it("swaps the panel away when navigation leaves it", async () => {
		// No selection is stored, so leaving the sidebar's rows closes it. There is no last
		// panel to fall back to.
		const deal: NavigationItem = { key: "deal", item_type: "DocType", link_to: "CRM Deal" };
		const { host, router } = await shell([accounts, deal], sidebars, "/sales-invoice");
		expect(panel(host)).not.toBeNull();

		await router.push("/crm-deal");
		await flush();
		expect(panel(host)).toBeNull();
	});
});

describe("the empty case", () => {
	it("draws no panel and no rail item when the sidebar has no rows", async () => {
		// A linked rail item whose sidebar is empty renders as independent, and a `Sidebar` item's
		// whole content is the sidebar, so it is not drawn at all.
		const { host } = await shell([accounts], { module_def_accounts: [] }, "/sales-invoice");
		expect(panel(host)).toBeNull();
		expect(host.querySelector("[data-key='accounts']")).toBeNull();
	});

	it("draws no panel when the sidebar is absent from the payload altogether", async () => {
		const { host } = await shell([accounts], {}, "/sales-invoice");
		expect(panel(host)).toBeNull();
	});
});

describe("what is marked current", () => {
	it("marks the row you are on and the rail item that opens it", async () => {
		const { host } = await shell([accounts], sidebars, "/crm-lead");

		expect(marked(host.querySelector("nav"))).toEqual(["accounts"]);
		expect(marked(panel(host))).toEqual(["lead"]);
	});

	it("keeps the rail item marked from the second row on", async () => {
		// The rail item's own link points at the sidebar's FIRST row, so `router-link-active`
		// would go out here and the reader would lose the only sign of where they are.
		const { host } = await shell([accounts], sidebars, "/crm-lead");
		const railItem = host.querySelector("nav [data-key='accounts']");
		expect(railItem?.getAttribute("aria-current")).toBe("page");
	});

	it("marks exactly one row across the rail and the panel together", async () => {
		// `lead` is on the rail and in the sidebar. Two independent highlights would light both.
		const { host } = await shell([accounts, lead], sidebars, "/crm-lead");
		expect(marked(host)).toEqual(["accounts", "lead"]);
		expect(marked(panel(host))).toEqual(["lead"]);
		// The rail's own `lead` points exactly here, so `RouterLink` would mark it by itself.
		// Binding `aria-current` explicitly is what suppresses that and keeps the count at one.
		expect(
			host.querySelector("nav [data-key='lead']")?.getAttribute("aria-current")
		).toBeNull();
	});

	it("keeps the list marked while a record of it is open", async () => {
		const { host } = await shell([accounts], sidebars, "/crm-lead/CRM-LEAD-01");
		expect(marked(panel(host))).toEqual(["lead"]);
	});
});

describe("two containers, one key", () => {
	it("does not confuse a rail row with a sidebar row of the same name", async () => {
		// A key identifies a row within one container: the rail's `lead` must not light up
		// because the panel's `lead` is current.
		const { host } = await shell(
			[accounts, { ...lead, link_to: "CRM Deal" }],
			sidebars,
			"/crm-lead"
		);

		expect(marked(host.querySelector("nav"))).toEqual(["accounts"]);
		expect(marked(panel(host))).toEqual(["lead"]);
	});
});

describe("the panel is a container, not a view of the rail", () => {
	it("offers its own Arrange, addressed at the sidebar", async () => {
		// The arrangement endpoints take the container as an argument, so the panel arranges on
		// the rail's terms.
		const { host } = await shell([accounts], sidebars, "/sales-invoice");
		expect(panel(host)?.textContent).toContain("Arrange");
	});
});

describe("what the panel draws", () => {
	const section: NavigationItem = { key: "billing", item_type: "Section", label: "Billing" };
	const nested = { ...invoice, parent_key: "billing" };

	it("draws sections and what nests under them", async () => {
		const { host } = await shell([accounts], { module_def_accounts: [section, nested] }, "/sales-invoice");

		const heading = panel(host)?.querySelector("[data-key='billing']");
		expect(heading?.textContent?.trim()).toBe("Billing");
		// The row is inside the section's list, not beside it.
		expect(heading?.parentElement?.querySelector("[data-key='invoice']")).not.toBeNull();
	});

	it("marks a nested row, and the rail item above it", async () => {
		const { host } = await shell([accounts], { module_def_accounts: [section, nested] }, "/sales-invoice");

		expect(marked(panel(host))).toEqual(["invoice"]);
		expect(marked(host.querySelector("nav"))).toEqual(["accounts"]);
	});

	it("reports a cycle in each container it happens in", async () => {
		// A key is unique within one container, so a shared "reported once" set would swallow
		// the panel's report as a repeat of the rail's.
		const errors: string[] = [];
		const original = console.error;
		console.error = (...args: unknown[]) => errors.push(String(args[0]));

		const loop = (key: string, parent_key: string): NavigationItem => ({
			key,
			item_type: "DocType",
			link_to: "CRM Lead",
			parent_key,
		});

		try {
			await shell(
				[accounts, loop("a", "b"), loop("b", "a")],
				{ module_def_accounts: [invoice, loop("a", "b"), loop("b", "a")] },
				"/sales-invoice"
			);
		} finally {
			console.error = original;
		}

		expect(errors.filter((line) => line.includes("in the rail")).length).toBe(2);
		expect(errors.filter((line) => line.includes("module_def_accounts sidebar")).length).toBe(2);
	});
});

describe("the panel's own context", () => {
	it("measures what is left of a module against the sidebar, not against the rail", async () => {
		// A context is composed once per list: a row handed the rail's context would hide the
		// doctypes the rail shows and repeat its own.
		fetchContents.mockResolvedValue([
			{ doctype: "CRM Lead", slug: "crm-lead", module: "FCRM" },
			{ doctype: "Sales Invoice", slug: "sales-invoice", module: "Accounts" },
		]);

		const { host } = await shell(
			[accounts, invoice],
			{
				module_def_accounts: [
					lead,
					{ key: "rest", item_type: "Module Contents", link_to: "FCRM" },
				],
			},
			"/crm-lead"
		);

		const more = panel(host)?.querySelector<HTMLElement>("[data-key='rest']");
		more?.click();
		await flush();
		await flush();

		// `CRM Lead` is already in this panel, so it is not repeated...
		expect(panel(host)?.querySelectorAll("[data-key='rest:CRM Lead']").length).toBe(0);
		// ...and `Sales Invoice`, which the RAIL shows and this panel does not, is offered.
		expect(panel(host)?.querySelector("[data-key='rest:Sales Invoice']")).not.toBeNull();
	});
});

describe("the panel's heading", () => {
	it("is the rail item's authored label", async () => {
		const { host } = await shell([accounts], sidebars, "/sales-invoice");
		expect(panel(host)?.querySelector("p")?.textContent?.trim()).toBe("Accounts");
	});

	it("is absent rather than a scrubbed address when nobody labelled the item", async () => {
		// `labelOf` would fall through to `link_to`, here the scrubbed address; no heading beats that.
		const { host } = await shell([{ ...accounts, label: undefined }], sidebars, "/sales-invoice");

		expect(panel(host)).not.toBeNull();
		expect(panel(host)?.textContent).not.toContain("module_def_accounts");
	});
});


describe("icons in the panel", () => {
	// One model, two presentations, so the icon question is answered once for both.
	function withSprite() {
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue({
				ok: true,
				text: () =>
					Promise.resolve(
						'<svg id="frappe-symbols"><symbol id="icon-users"/></svg>'
					),
			})
		);
		return loadSprite();
	}

	it("draws one", async () => {
		await withSprite();

		const { host } = await shell(
			[accounts],
			{ module_def_accounts: [{ ...invoice, icon: "users" }, lead] },
			"/sales-invoice"
		);

		expect(
			panel(host)?.querySelector('[data-key="invoice"] use')?.getAttribute("href")
		).toBe("#icon-users");
	});

	it("holds the slot open on the rest of that panel", async () => {
		// The mixed container is CRM's case, where one jutting row would read as a mistake.
		await withSprite();

		const { host } = await shell(
			[accounts],
			{ module_def_accounts: [{ ...invoice, icon: "users" }, lead] },
			"/sales-invoice"
		);

		expect(
			panel(host)?.querySelector('[data-key="lead"] span[aria-hidden]')
		).not.toBeNull();
	});
});
