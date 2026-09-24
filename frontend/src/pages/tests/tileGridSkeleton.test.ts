// The app home and a module page draw a tile grid skeleton while their contents load, and only then.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

const runMethod = vi.hoisted(() => vi.fn());
vi.mock("@framework/ui/api", () => ({ runMethod }));

// The frame's header teleports into a shell target this test does not draw.
vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent } = await import("vue");
	return { default: defineComponent({ setup: (_, { slots }) => () => slots.default?.() }) };
});

vi.mock("@/router/routeFor", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/router/routeFor")>()),
	routeFor: () => "/",
}));

import Home from "../Home.vue";
import Module from "../Module.vue";

const boot = { app: "crm", shell_base: "/apps/crm", prefixes: { crm: { app: "crm" } } };
const addresses = { moduleName: (slug: string) => slug.toUpperCase() };
const apps: App[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	runMethod.mockReset();
});

/** A contents read the test answers by hand, so the pending state can be looked at. */
function pendingContents() {
	let answer!: (data: unknown) => void;
	let fail!: (error: Error) => void;
	runMethod.mockReturnValueOnce(
		new Promise((resolve, reject) => {
			answer = (data) => resolve({ data });
			fail = reject;
		})
	);
	return {
		answer: async (data: unknown) => {
			answer(data);
			await settle();
		},
		fail: async () => {
			fail(new Error("no"));
			await settle();
		},
	};
}

async function settle() {
	await Promise.resolve();
	await Promise.resolve();
	await nextTick();
}

async function mount(page: typeof Home) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:rest(.*)*", name: "module", component: { render: () => null } }],
	});
	await router.push("/desk");
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(page) }));
	app.use(router).provide("boot", boot).provide("addresses", addresses);
	app.mount(root);
	apps.push(app);
	await nextTick();
	return {
		tiles: () => root.querySelectorAll("[data-tile-skeleton] .fui-skeleton").length,
		skeletons: () => root.querySelectorAll(".fui-skeleton").length,
		links: () => root.querySelectorAll("li a").length,
		text: () => root.textContent ?? "",
	};
}

describe("Home", () => {
	it("draws six tile skeletons while the contents load, then the tiles", async () => {
		const read = pendingContents();
		const page = await mount(Home);
		expect(page.tiles()).toBe(6);
		expect(page.links()).toBe(0);

		await read.answer([{ doctype: "Note", slug: "note", module: "desk" }]);
		expect(page.skeletons()).toBe(0);
		expect(page.links()).toBe(1);
	});

	it("draws no skeleton for an app with no tiles once loaded", async () => {
		const read = pendingContents();
		const page = await mount(Home);
		await read.answer([]);
		expect(page.skeletons()).toBe(0);
		expect(page.links()).toBe(0);
	});

	it("draws no skeleton when the read fails", async () => {
		const read = pendingContents();
		const page = await mount(Home);
		await read.fail();
		expect(page.skeletons()).toBe(0);
		expect(page.text()).toContain("Could not load this app's navigation.");
	});
});

describe("Module", () => {
	it("draws a count bar and six tile skeletons while the contents load", async () => {
		const read = pendingContents();
		const page = await mount(Module);
		expect(page.tiles()).toBe(6);
		expect(page.skeletons()).toBe(7);
		expect(page.text()).not.toContain("Loading");

		await read.answer([{ doctype: "Note", slug: "note", module: "desk" }]);
		expect(page.skeletons()).toBe(0);
		expect(page.text()).toContain("1 doctype you can read.");
		expect(page.links()).toBe(1);
	});

	it("draws no skeleton for a module with no readable doctypes once loaded", async () => {
		const read = pendingContents();
		const page = await mount(Module);
		await read.answer([]);
		expect(page.skeletons()).toBe(0);
		expect(page.text()).toContain("0 doctypes you can read.");
	});
});
