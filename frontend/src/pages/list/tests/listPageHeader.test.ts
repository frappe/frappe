// The list page's controls row: the Sort control is a skeleton of its size until the page has
// read meta, the stored settings and the URL, and the controls that do not depend on them show at once.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

/** A stand-in that draws a marker, so the test sees which controls are on the page. */
function stub(name: string) {
	return defineComponent({ setup: () => () => h("div", { [`data-stub-${name}`]: "" }) });
}

vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent } = await import("vue");
	return {
		default: defineComponent({
			setup: (_, { slots }) => () => [slots.header?.(), slots.default?.()],
		}),
		pageGutter: "",
	};
});
vi.mock("@framework/ui/QuickFilter", () => ({ QuickFilter: stub("quick-filter") }));
vi.mock("@framework/ui/Filter", () => ({ Filter: stub("filter") }));
vi.mock("@framework/ui/SortBy", () => ({ SortBy: stub("sort") }));
vi.mock("@framework/ui/ColumnSettings", () => ({ ColumnSettings: stub("columns") }));
vi.mock("@framework/ui/experimental/List", () => ({
	List: stub("list"),
	ListFooter: stub("footer"),
}));
vi.mock("@/list/useScrollMemory", () => ({ useScrollMemory: () => {} }));
vi.mock("@/list/useListPage", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/list/useListPage")>()),
	useListPage: (await import("./fakeListPage")).useListPage,
}));
vi.mock("@/list/useListView", async () => ({
	useListView: (await import("./fakeListPage")).useListView,
}));

import { PLAIN_LIST } from "@/list/useListPage";
import ViewPage from "../ViewPage.vue";
import { fake, installListRenderer, resetFake } from "./fakeListPage";

const apps: App[] = [];

// The Create button reads meta and the session; no server answers here.
beforeEach(async () => {
	resetFake();
	fake.seeded = false;
	await installListRenderer();
	vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ errors: [{ type: "NotFound" }] }), { status: 404 }));
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
});

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function mount() {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:rest(.*)*", component: { render: () => null } }],
	});
	await router.push("/contact");
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(ViewPage, { doctype: "Contact", opened: PLAIN_LIST }) }));
	app.use(router).provide("boot", { bulk_actions: true, bulk_operation_limit: 500 }).provide("addresses", { moduleName: () => null });
	app.mount(root);
	apps.push(app);
	await settle();
	return root;
}

describe("the list page controls row", () => {
	it("draws the Sort control as a skeleton of its size until the page is seeded", async () => {
		const root = await mount();
		const skeleton = root.querySelector("[data-sort-skeleton]");
		expect(skeleton?.classList.contains("fui-skeleton")).toBe(true);
		expect(skeleton?.className).toContain("h-7 w-36 shrink-0 rounded-4");
		expect(root.querySelector("[data-stub-sort]")).toBeNull();

		fake.state.seeded.value = true;
		await nextTick();
		expect(root.querySelector("[data-sort-skeleton]")).toBeNull();
		expect(root.querySelector("[data-stub-sort]")).not.toBeNull();
	});

	it("draws the crumbs, Filter, Columns and More at once", async () => {
		const root = await mount();
		expect(root.textContent).toContain("Contact");
		expect(root.querySelector("[data-stub-filter]")).not.toBeNull();
		expect(root.querySelector("[data-stub-columns]")).not.toBeNull();
		expect(root.querySelector("button[aria-label='More']")).not.toBeNull();
		expect(root.querySelectorAll(".fui-skeleton")).toHaveLength(1);
	});
});
