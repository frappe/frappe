// The index's frame: no rail and no panel, the avatar menu alone at the rail's foot, and the index page.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, nextTick, type App } from "vue";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";

registerStandardPages(standardPages);
registerContributions(["frappe"]);

const addresses = new Addresses({ doctypes: { ToDo: ["todo", "desk"] }, modules: {} });
const session = { user: { name: "jane@example.com", full_name: "Jane Doe", email: "jane@example.com" } };

const index = {
	app: null,
	shell_base: "/apps",
	prefixes: { desk: { app: "frappe", modular: false } },
	session,
	apps: [{ app: "frappe", title: "Framework", logo: null, kind: "prefix", route: "/apps/desk", hidden: false }],
} as unknown as Boot;

const desk = {
	app: "frappe",
	app_title: "Framework",
	shell_base: "/apps/desk",
	prefixes: { desk: { app: "frappe", modular: false } },
	navigation: { rail: [], sidebars: {} },
	session,
} as unknown as Boot;

const mounted: App[] = [];

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
});

async function shell(boot: Boot, path = "/") {
	const router = createShellRouter(boot, addresses);
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
	mounted.push(app);
	return host;
}

/** Until the lazy page's code is in and drawn. */
async function settled(host: HTMLElement, selector: string) {
	for (let tries = 0; tries < 50 && !host.querySelector(selector); tries++) {
		await new Promise((resolve) => setTimeout(resolve, 10));
		await nextTick();
	}
	return host.querySelector(selector);
}

describe("the index frame", () => {
	it("draws no rail and no panel, and the avatar menu at the rail's foot", async () => {
		const host = await shell(index);
		expect(host.querySelector("[data-slot='sidebar-rail']")).toBeNull();
		expect(host.querySelector("[data-slot='sidebar']")).toBeNull();
		expect(host.querySelector("[data-index-foot] [data-key='user-menu']")).not.toBeNull();
	});

	it("draws the index page at /apps, after its own loading state", async () => {
		const host = await shell(index);
		expect(host.querySelector("[data-index-skeleton]")).not.toBeNull();
		expect(await settled(host, "[data-index] a[data-app='frappe']")).not.toBeNull();
		expect(host.querySelector("[data-index-skeleton]")).toBeNull();
	});

	it("shows not found for any other address on the index", async () => {
		const host = await shell(index, "/todo");
		expect(await settled(host, "[data-page-state='notFound']")).not.toBeNull();
	});

	it("keeps the avatar menu at the rail's foot inside an app, and draws no index foot", async () => {
		const host = await shell(desk, "/todo");
		expect(host.querySelector("[data-slot='sidebar-rail'] [data-key='user-menu']")).not.toBeNull();
		expect(host.querySelector("[data-index-foot]")).toBeNull();
	});
});
