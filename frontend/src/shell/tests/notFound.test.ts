// The router's catch-all page: the shared not found state, with the way back to the app's home.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import { RouterView } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";

registerStandardPages(standardPages);

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({ doctypes: { "CRM Lead": ["crm-lead", "crm"] }, modules: {} });
const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function open(boot: Partial<Boot>, address: string) {
	const router = createShellRouter({ prefixes: {}, ...boot } as Boot, addresses);
	await router.push(address);
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({ render: () => h(RouterView) });
	app.use(router).provide("boot", boot);
	app.mount(root);
	apps.push(app);
	await nextTick();
	return root.querySelector<HTMLAnchorElement>('[data-page-state="notFound"] a');
}

describe("the catch-all page", () => {
	it("offers the app's home, labelled with the app's title", async () => {
		const crm = { app: "crm", app_title: "CRM", shell_base: "/apps/crm" };
		const home = await open(crm, "/crm-lead/CRM-LEAD-1/no/such/page");
		expect(home?.textContent?.trim()).toBe("Go to CRM home");
		expect(home?.getAttribute("href")).toBe(`${crm.shell_base}/`);
	});

	it("offers all apps on the index, which belongs to no app", async () => {
		const home = await open({ app: null, shell_base: "/apps" }, "/no/such/page");
		expect(home?.textContent?.trim()).toBe("Go to all apps");
		expect(home?.getAttribute("href")).toBe("/apps/");
	});
});
