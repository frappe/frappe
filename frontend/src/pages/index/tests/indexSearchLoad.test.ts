// The index when its search chunk cannot load: the tiles still filter, and the box says the search failed.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import IndexPage from "../IndexPage.vue";

const chunk = vi.hoisted(() => ({ failures: 0 }));

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	runMethod: async (method: string) => ({
		data:
			method === "frappe.shell.palette.places"
				? { doctypes: [], apps: [], titles: {}, recent: [] }
				: method === "frappe.shell.settings.get_panes"
				? { panes: [], index: [], titles: {} }
				: [],
	}),
}));

vi.mock("../indexSearch", async (original) => {
	if (chunk.failures-- > 0) throw new Error("the chunk is gone");
	return original();
});

afterEach(() => {
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

function mount() {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(IndexPage);
	const apps = [{ app: "crm", title: "CRM", logo: null, kind: "prefix", route: "/apps/crm", hidden: false }];
	app.provide("boot", { app: null, apps, session: { user: {} }, prefixes: {} } as unknown as Boot);
	app.provide("addresses", new Addresses({ doctypes: {}, modules: {}, singles: [] }));
	app.use(createRouter({ history: createMemoryHistory(), routes: [{ path: "/", component: {} }] }));
	app.mount(host);
	return { host, app };
}

async function type(host: HTMLElement, text: string) {
	const box = host.querySelector<HTMLInputElement>("input")!;
	box.value = text;
	box.dispatchEvent(new Event("input"));
	await nextTick();
}

function state(host: HTMLElement) {
	return host.querySelector("[data-index-state]")?.textContent?.trim();
}

describe("the index when its search fails to load", () => {
	it("says the search failed, filters the tiles, and asks again on the next keystroke", async () => {
		vi.spyOn(console, "error").mockImplementation(() => {});
		chunk.failures = 1;
		const { host, app } = mount();
		await nextTick();

		await type(host, "zzz");
		await vi.waitFor(() => expect(state(host)).toBe("Could not search for “zzz”"));
		expect(console.error).toHaveBeenCalled();

		await type(host, "cr");
		expect(host.querySelector("[data-app='crm']")).not.toBeNull();
		expect(state(host)).toBeUndefined();

		await type(host, "zzzz");
		await vi.waitFor(() => expect(state(host)).toBe("No results for “zzzz”"), { timeout: 60000 });
		app.unmount();
	}, 90000);
});
