// The palette's Recent: this tab's visits and the server's, one per address, newest first, 20 at most.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell, urlFor } from "@/router/routeFor";
import { recentVisits } from "../recentVisits";

const boot = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	session: { user: { name: "reader@example.com" } },
} as unknown as Boot;

const addresses = new Addresses({
	doctypes: { "CRM Deal": ["crm-deal", "fcrm"] },
	modules: { fcrm: "FCRM" },
});

let router: Router;

beforeEach(() => {
	vi.useFakeTimers({ toFake: ["Date"] });
	vi.setSystemTime(1_000_000);
	router = createRouter({
		history: createMemoryHistory(boot.shell_base),
		routes: [
			{ path: "/:doctype", name: "list", component: { render: () => null } },
			{ path: "/:doctype/view/:key", name: "saved-view", component: { render: () => null } },
			{ path: "/:doctype/:name", name: "record", component: { render: () => null } },
		],
	});
	registerShell({ boot, addresses, router });
	recentVisits.track(router, boot, addresses);
	recentVisits.heard([]);
});

afterEach(() => vi.useRealTimers());

async function visit(path: string) {
	vi.setSystemTime(Date.now() + 1000);
	await router.push(path);
}

function titles() {
	return recentVisits.list().map((one) => one.title);
}

describe("recent visits", () => {
	it("moves a revisited record to the top and keeps the title its page read", async () => {
		await visit("/crm-deal/DEAL-1");
		recentVisits.retitle("/crm-deal/DEAL-1", "Acme deal");
		await visit("/crm-deal");
		await visit("/crm-deal/DEAL-1");

		expect(titles()).toEqual(["Acme deal", "CRM Deal"]);
	});

	it("keeps a saved view as its own place, titled by the label its page read", async () => {
		await visit("/crm-deal");
		await visit("/crm-deal/view/open-deals");
		recentVisits.retitle("/crm-deal/view/open-deals", "Open deals");

		expect(recentVisits.list().map(({ title, kind, view, route }) => ({ title, kind, view, route }))).toEqual([
			{ title: "Open deals", kind: "view", view: "open-deals", route: urlFor("CRM Deal", null, { view: "open-deals" }) },
			{ title: "CRM Deal", kind: "list", view: undefined, route: urlFor("CRM Deal") },
		]);
	});

	it("keeps 20 at most", async () => {
		for (let index = 1; index <= 22; index++) await visit(`/crm-deal/DEAL-${index}`);

		expect(recentVisits.list()).toHaveLength(20);
		expect(titles()[0]).toBe("DEAL-22");
	});

	it("puts a server visit newer than this tab's above it, as another tab made it later", async () => {
		await visit("/crm-deal/DEAL-1");
		const later = Date.now() + 5000;
		recentVisits.heard([
			{ route: `${boot.shell_base}/crm-deal/DEAL-2`, doctype: "CRM Deal", name: "DEAL-2", title: "Globex deal", kind: "record", visited: later },
			{ route: `${boot.shell_base}/crm-deal/DEAL-3`, doctype: "CRM Deal", name: "DEAL-3", title: "Initech deal", kind: "record", visited: 1 },
		]);

		expect(titles()).toEqual(["Globex deal", "DEAL-1", "Initech deal"]);
		expect(recentVisits.recency(`${boot.shell_base}/crm-deal/DEAL-1`)).toBe(1);
	});

	it("moves this tab's visit up when another tab opened the same address later", async () => {
		await visit("/crm-deal/DEAL-1");
		await visit("/crm-deal");
		recentVisits.heard([
			{ route: `${boot.shell_base}/crm-deal/DEAL-1`, doctype: "CRM Deal", name: "DEAL-1", title: "Acme deal", kind: "record", visited: Date.now() + 5000 },
		]);

		expect(titles()).toEqual(["Acme deal", "CRM Deal"]);
	});
});
