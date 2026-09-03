// A section that ships shut, and the two things that open it: the address, and the reader.
// Driven off a real resolved payload: the defect only shows where a route points inside one.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, Navigation, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";
import navigation from "./fixtures/crmNavigation.json";

const READER = "reader@example.com";
const stub = { render: () => null };

// Every doctype the fixture points at, addressable the way the server scrubs one. Derived
// from the payload so a regenerated fixture needs no second edit here.
const addresses = new Addresses({
	doctypes: Object.fromEntries(
		[...(navigation as Navigation).rail, ...Object.values((navigation as Navigation).sidebars).flat()]
			.filter((item) => item.link_doctype === "DocType" && item.link_to)
			.map((item) => [item.link_to!, [item.link_to!.toLowerCase().replaceAll(" ", "-"), "fcrm"]])
	),
	modules: { fcrm: "FCRM" },
});

async function flush() {
	await Promise.resolve();
	await nextTick();
}

async function shell(
	path: string,
	user = READER,
	payload: unknown = navigation
): Promise<{ host: HTMLElement; router: Router }> {
	const boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: payload,
		user: { name: user, full_name: "Reader" },
	} as unknown as Boot;

	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: stub },
			{ path: "/:doctype", name: "list", component: stub },
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

function row(host: HTMLElement, key: string) {
	return host.querySelector(`aside [data-key="${CSS.escape(key)}"]`);
}

function marked(host: HTMLElement) {
	return Array.from(host.querySelectorAll("aside [aria-current='page']")).map((node) =>
		node.getAttribute("data-key")
	);
}

async function click(node: Element | null) {
	node!.dispatchEvent(new Event("click"));
	await flush();
}

function addressOf(item: NavigationItem) {
	return `/${item.link_to!.toLowerCase().replaceAll(" ", "-")}`;
}

/** Every row the fixture puts behind a section that ships shut. */
function behindShutSections(): { sidebar: string; section: string; item: NavigationItem }[] {
	return Object.entries((navigation as Navigation).sidebars).flatMap(([sidebar, rows]) => {
		const shut = new Set(rows.filter((item) => item.keep_closed).map((item) => item.key));

		return rows
			.filter((item) => item.parent_key && shut.has(item.parent_key))
			.map((item) => ({ sidebar, section: item.parent_key!, item }));
	});
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	localStorage.clear();
	// The shell stamps the sidebar it resolves onto the history entry, and these mount over
	// one window.
	window.history.replaceState(null, "", "/");

	resetNavigationReports();
	resetSprite();
	vi.unstubAllGlobals();
});

describe("the fixture this is driven off", () => {
	it("ships sections shut with destinations behind them", () => {
		// If a payload change empties this, every test below passes by testing nothing.
		expect(behindShutSections().length).toBeGreaterThan(0);
	});
});

describe("the address opens the section it is standing in", () => {
	// Asserted on the row, not a named section: one fixture row sits behind a shut section in
	// two panels. A row renders only if its section is open, so this covers both.
	it.each(behindShutSections())(
		"shows $item.key, shipped behind $section",
		async ({ item }) => {
			const { host } = await shell(addressOf(item));

			expect(row(host, item.key)).not.toBeNull();
			expect(marked(host)).toEqual([item.key]);
		}
	);

	it("leaves every other section as the app ships it", async () => {
		const { host } = await shell("/crm-lead-status");
		const { host: shut } = await shell("/crm-deal");

		expect(row(host, "lead-statuses")).not.toBeNull();
		expect(row(shut, "deals-configure")?.getAttribute("aria-expanded")).toBe("false");
		expect(row(shut, "deal-statuses")).toBeNull();
	});

	it("offers no control to shut it over the row you are on", async () => {
		const { host } = await shell("/crm-lead-status");
		const heading = row(host, "leads-configure")!;

		// A plain heading, not a button reporting a state a click would not change.
		expect(heading.tagName).toBe("P");
		expect(heading.getAttribute("aria-expanded")).toBeNull();

		await click(heading);
		expect(row(host, "lead-statuses")).not.toBeNull();
		expect(localStorage.getItem("frappe:desk:sections")).toBeNull();
	});

	it("gives the control back on the way out", async () => {
		const { host, router } = await shell("/crm-lead-status");

		await router.push("/crm-lead");
		await flush();

		expect(row(host, "leads-configure")!.tagName).toBe("BUTTON");
	});

	it("shuts it again on the way out, and records nothing", async () => {
		const { host, router } = await shell("/crm-lead-status");

		await router.push("/crm-lead");
		await flush();

		expect(row(host, "leads-configure")?.getAttribute("aria-expanded")).toBe("false");
		expect(row(host, "lead-statuses")).toBeNull();
		expect(localStorage.getItem("frappe:desk:sections")).toBeNull();
	});
});

describe("a reader's own toggle", () => {
	it("survives a reload", async () => {
		const { host } = await shell("/crm-lead");
		await click(row(host, "leads-configure"));
		expect(row(host, "lead-statuses")).not.toBeNull();

		const { host: again } = await shell("/crm-lead");
		expect(again.querySelector('aside [data-key="lead-statuses"]')).not.toBeNull();
	});

	it("does not reach another user on the same browser", async () => {
		const { host } = await shell("/crm-lead");
		await click(row(host, "leads-configure"));

		const { host: colleague } = await shell("/crm-lead", "colleague@example.com");
		expect(row(colleague, "leads-configure")?.getAttribute("aria-expanded")).toBe("false");
	});

	it("is cleared by toggling it back", async () => {
		const { host } = await shell("/crm-lead");
		await click(row(host, "leads-configure"));
		await click(row(host, "leads-configure"));

		const { host: again } = await shell("/crm-lead");
		expect(row(again, "leads-configure")?.getAttribute("aria-expanded")).toBe("false");
	});
});

// The fixture ships no section that starts open, so this one direction is over rows built
// here: shutting one is what `settled()` answers `false` for.
describe("shutting a section the app ships open", () => {
	const shippedOpen = {
		rail: [{ key: "leads", item_type: "Sidebar", link_to: "doctype_crm_lead", label: "Leads" }],
		sidebars: {
			doctype_crm_lead: [
				{ key: "all", item_type: "DocType", link_doctype: "DocType", link_to: "CRM Lead" },
				{ key: "more", item_type: "Section", collapsible: 1, label: "More" },
				{
					key: "sources",
					parent_key: "more",
					item_type: "DocType",
					link_doctype: "DocType",
					link_to: "CRM Lead Source",
				},
			],
		},
	};

	it("survives a reload", async () => {
		const { host } = await shell("/crm-lead", READER, shippedOpen);
		expect(row(host, "sources")).not.toBeNull();

		await click(row(host, "more"));

		const { host: again } = await shell("/crm-lead", READER, shippedOpen);
		expect(row(again, "more")?.getAttribute("aria-expanded")).toBe("false");
		expect(row(again, "sources")).toBeNull();
	});
});
