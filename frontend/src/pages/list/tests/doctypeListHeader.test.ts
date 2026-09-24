// The list page's controls row: the Sort control is a skeleton of its size until the page has
// read meta, the stored settings and the URL, and the controls that do not depend on them show at once.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

const page = vi.hoisted(() => ({ seeded: null as unknown as { value: boolean } }));

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
	ListBulkBar: stub("bulk-bar"),
	ListFooter: stub("footer"),
}));
vi.mock("@/list/useScrollMemory", () => ({ useScrollMemory: () => {} }));
vi.mock("@/list/useListPage", async () => {
	const { ref } = await import("vue");
	return {
		useListPage: () => {
			page.seeded = ref(false);
			const empty = () => ref([]);
			return {
				filters: empty(),
				sort: empty(),
				columns: empty(),
				quickFilterFields: ref(undefined),
				customizing: ref(false),
				selection: empty(),
				pageSize: ref(20),
				rowsKey: () => "",
				rows: empty(),
				loading: ref(true),
				error: ref(null),
				metaError: ref(null),
				seeded: page.seeded,
				rowCount: ref(0),
				totalCount: ref(0),
				totalCapped: ref(false),
				totalUnknown: ref(false),
				hasCounts: ref(false),
				hasNextPage: ref(false),
			};
		},
	};
});

import DoctypeList from "../DoctypeList.vue";

const apps: App[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount() {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:rest(.*)*", component: { render: () => null } }],
	});
	await router.push("/contact");
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(DoctypeList, { doctype: "Contact" }) }));
	app.use(router).provide("addresses", { moduleName: () => null });
	app.mount(root);
	apps.push(app);
	await nextTick();
	return root;
}

describe("DoctypeList controls row", () => {
	it("draws the Sort control as a skeleton of its size until the page is seeded", async () => {
		const root = await mount();
		const skeleton = root.querySelector("[data-sort-skeleton]");
		expect(skeleton?.classList.contains("fui-skeleton")).toBe(true);
		expect(skeleton?.className).toContain("h-7 w-36 shrink-0 rounded-4");
		expect(root.querySelector("[data-stub-sort]")).toBeNull();

		page.seeded.value = true;
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
