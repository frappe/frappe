// The shell's Create: one request per open, answered once, and every open one closed on a
// route change; the shell draws the registered dialog for each.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import {
	closeCreates,
	createRequests,
	openCreate,
	registerCreateDialog,
	type CreateRequest,
} from "../create";

const StubDialog = defineComponent({
	props: { request: { type: Object, required: true } },
	setup: (props) => () =>
		h("div", { "data-create": (props.request as CreateRequest).doctype }),
});

beforeEach(() => {
	registerCreateDialog(StubDialog);
	closeCreates();
});

describe("openCreate", () => {
	it("throws when no dialog was registered", async () => {
		vi.resetModules();
		const fresh = await import("../create");

		expect(() => fresh.openCreate("Lead")).toThrow(/before the Create dialog was registered/);
		expect(fresh.createRequests.value).toEqual([]);
	});

	it("opens a request with the doctype and a copy of the caller's values", () => {
		const values = { status: "Open" };
		void openCreate("Lead", { values });

		expect(createRequests.value).toHaveLength(1);
		expect(createRequests.value[0]).toMatchObject({ doctype: "Lead", values: { status: "Open" } });
		values.status = "Closed";
		expect(createRequests.value[0].values).toEqual({ status: "Open" });
	});

	it("opens with no values when the caller gives none", () => {
		void openCreate("Lead");

		expect(createRequests.value[0].values).toEqual({});
	});

	it("resolves with the saved record, and only the first settle counts", async () => {
		const opened = openCreate("Lead");
		const [request] = createRequests.value;

		request.settle({ name: "LEAD-1" });
		request.settle(null);
		request.settle({ name: "LEAD-2" });

		expect(await opened).toEqual({ name: "LEAD-1" });
	});

	it("stays on the stack after a settle until dismissed, and dismiss removes only that one", async () => {
		void openCreate("Lead");
		void openCreate("Contact");
		const [lead, contact] = createRequests.value;

		lead.settle(null);
		expect(createRequests.value).toHaveLength(2);
		lead.dismiss();

		expect(createRequests.value.map((one) => one.doctype)).toEqual(["Contact"]);
		expect(createRequests.value[0].id).toBe(contact.id);
	});

	it("resolves every open request null and empties the stack on closeCreates", async () => {
		const lead = openCreate("Lead");
		const contact = openCreate("Contact");

		closeCreates();

		expect(createRequests.value).toEqual([]);
		expect(await lead).toBeNull();
		expect(await contact).toBeNull();
	});

	it("keeps a saved answer when closeCreates runs after it", async () => {
		const opened = openCreate("Lead");
		createRequests.value[0].settle({ name: "LEAD-1" });

		closeCreates();

		expect(await opened).toEqual({ name: "LEAD-1" });
	});
});

describe("the shell's Create dialogs", () => {
	const addresses = new Addresses({
		doctypes: { Lead: ["lead", "crm"], Contact: ["contact", "crm"] },
		modules: { crm: "CRM" },
	});
	let app: App | null = null;

	async function settle() {
		for (let turn = 0; turn < 3; turn++) {
			await new Promise((resolve) => setTimeout(resolve, 0));
			await nextTick();
		}
	}

	async function shell(): Promise<{ host: HTMLElement; router: Router }> {
		const boot = {
			app: "crm",
			shell_base: "/apps/crm",
			prefixes: { crm: { app: "crm", modular: false } },
			navigation: { rail: [], sidebars: {} },
			session: {
				user: { name: "test@example.com", full_name: "Test", email: "test@example.com" },
			},
		} as unknown as Boot;
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [
				{ path: "/", name: "home", component: { render: () => null } },
				{ path: "/:doctype", name: "list", component: { render: () => null } },
			],
		});
		registerShell({ boot, addresses, router });
		const host = document.createElement("div");
		document.body.appendChild(host);
		app = createApp(AppShell);
		app.provide("boot", boot);
		app.provide("addresses", addresses);
		app.use(router);
		await router.push("/lead");
		await router.isReady();
		app.mount(host);
		await settle();
		return { host, router };
	}

	function drawn(host: HTMLElement) {
		return [...host.querySelectorAll("[data-create]")].map((one) => one.getAttribute("data-create"));
	}

	beforeAll(async () => {
		await registerContributions(["frappe"]);
	});

	beforeEach(() => {
		document.body.innerHTML = "";
		resetNavigationReports();
		resetSprite();
	});

	afterEach(() => {
		app?.unmount();
		app = null;
	});

	it("draws the registered dialog once for each open request", async () => {
		const { host } = await shell();

		void openCreate("Lead");
		void openCreate("Contact");
		await nextTick();

		expect(drawn(host)).toEqual(["Lead", "Contact"]);

		createRequests.value[0].dismiss();
		await nextTick();
		expect(drawn(host)).toEqual(["Contact"]);
	});

	it("closes every open Create, answering null, when the route changes", async () => {
		const { host, router } = await shell();
		const opened = openCreate("Lead");
		await nextTick();
		expect(drawn(host)).toEqual(["Lead"]);

		await router.push("/contact");
		await settle();

		expect(await opened).toBeNull();
		expect(drawn(host)).toEqual([]);
	});
});
