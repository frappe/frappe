// The index when its search chunk cannot load: the tiles still filter, and no match still says so.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import IndexPage from "../IndexPage.vue";

vi.mock("../indexSearch", () => {
	throw new Error("the chunk is gone");
});

afterEach(() => {
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

describe("the index without its search", () => {
	it("says no result matched when the search chunk failed to load", async () => {
		vi.spyOn(console, "error").mockImplementation(() => {});
		const host = document.createElement("div");
		document.body.appendChild(host);
		const app = createApp(IndexPage);
		const apps = [
			{ app: "crm", title: "CRM", logo: null, kind: "prefix", route: "/apps/crm", hidden: false },
		];
		app.provide("boot", { app: null, apps, session: { user: {} }, prefixes: {} } as unknown as Boot);
		app.provide("addresses", new Addresses({ doctypes: {}, modules: {}, singles: [] }));
		app.use(createRouter({ history: createMemoryHistory(), routes: [{ path: "/", component: {} }] }));
		app.mount(host);
		await nextTick();

		const box = host.querySelector<HTMLInputElement>("input")!;
		box.value = "zzz";
		box.dispatchEvent(new Event("input"));
		await vi.waitFor(() =>
			expect(host.querySelector("[data-index-state='no-match']")?.textContent?.trim()).toBe(
				"No results for “zzz”"
			)
		);
		expect(console.error).toHaveBeenCalled();
		app.unmount();
	});
});
