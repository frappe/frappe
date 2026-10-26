// The recents the palette shows: every place and record opened by any route, per user, 20 at most.
import { beforeEach, describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { recents } from "../recents";

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"System Settings": ["system-settings", "core"],
	},
	modules: { fcrm: "FCRM", core: "Core" },
	singles: ["System Settings"],
});

const page = { render: () => null };

function bootFor(user: string) {
	return {
		app: "crm",
		app_title: "CRM",
		shell_base: "/apps/crm",
		session: { user: { name: user } },
	} as unknown as Boot;
}

function track(user = "reader@example.com") {
	const boot = bootFor(user);
	const router = createRouter({
		history: createMemoryHistory(boot.shell_base),
		routes: [
			{ path: "/", name: "home", component: page },
			{ path: "/deals", name: "page:crm:deals", component: page, meta: { title: "Deals" } },
			{ path: "/:doctype", name: "list", component: page },
			{ path: "/:doctype/new", name: "new-record", component: page },
			{ path: "/:doctype/view/list/:viewName", name: "saved-view", component: page },
			{ path: "/:doctype/:name", name: "record", component: page },
		],
	});
	recents.track(router, boot, addresses);
	return router;
}

function shown() {
	return recents.list().map(({ label, description, kind }) => [label, description, kind]);
}

beforeEach(() => localStorage.clear());

describe("recents", () => {
	it("keeps lists, records, saved views and pages, newest first, and nothing else", async () => {
		const router = track();
		await router.push("/crm-deal");
		await router.push("/crm-deal/DEAL-1");
		await router.push("/crm-deal/new");
		await router.push("/crm-deal/view/list/open");
		await router.push("/deals");
		await router.push("/system-settings/System Settings");

		expect(shown()).toEqual([
			["System Settings", "CRM", "list"],
			["Deals", "CRM", "page"],
			["open", "CRM Deal", "list"],
			["DEAL-1", "CRM Deal", "record"],
			["CRM Deal", "CRM", "list"],
		]);
	});

	it("moves a place opened again to the top, once", async () => {
		const router = track();
		await router.push("/crm-deal");
		await router.push("/crm-deal/DEAL-1");
		await router.push("/crm-deal");

		expect(shown().map(([label]) => label)).toEqual(["CRM Deal", "DEAL-1"]);
	});

	it("keeps 20 at most", async () => {
		const router = track();
		for (let index = 1; index <= 22; index++) await router.push("/crm-deal/DEAL-" + index);

		expect(recents.list()).toHaveLength(20);
		expect(recents.list()[0].label).toBe("DEAL-22");
	});

	it("keeps a record's title once its page reads it, across later visits", async () => {
		const router = track();
		await router.push("/crm-deal/DEAL-1");
		recents.retitle("/crm-deal/DEAL-1", "Acme Corp");
		await router.push("/crm-deal");
		await router.push("/crm-deal/DEAL-1");

		expect(shown()[0]).toEqual(["Acme Corp", "CRM Deal", "record"]);
	});

	it("keeps each user's own, and another tab's visits", async () => {
		const reader = track("reader@example.com");
		await reader.push("/crm-deal/DEAL-1");
		const writer = track("writer@example.com");
		await writer.push("/crm-deal/DEAL-2");
		expect(shown().map(([label]) => label)).toEqual(["DEAL-2"]);

		const readerAgain = track("reader@example.com");
		expect(shown().map(([label]) => label)).toEqual(["DEAL-1"]);

		const other = track("reader@example.com");
		await other.push("/crm-deal/DEAL-3");
		await readerAgain.push("/crm-deal/DEAL-4");
		expect(shown().map(([label]) => label)).toEqual(["DEAL-4", "DEAL-3", "DEAL-1"]);
	});
});
