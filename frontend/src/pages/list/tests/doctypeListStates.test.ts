// The list page's states: a failed meta read takes the whole page, a failed or empty rows read the
// table's place under the controls, and an address with no doctype is not found.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { ApiError } from "@framework/ui/api";

const page = vi.hoisted(() => ({
	state: null as unknown as Record<string, { value: unknown }>,
	reload: vi.fn(),
	reloadMeta: vi.fn(),
}));

function stub(name: string) {
	return defineComponent({ setup: () => () => h("div", { [`data-stub-${name}`]: "" }) });
}

vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent, h } = await import("vue");
	const PageState = (await import("@/shell/PageState.vue")).default;
	return {
		default: defineComponent({
			props: ["state"],
			setup: (props, { slots }) => () => [
				slots.header?.(),
				props.state ? h(PageState, props.state) : slots.default?.(),
			],
		}),
		pageGutter: "",
	};
});
vi.mock("@framework/ui/QuickFilter", () => ({ QuickFilter: stub("quick-filter") }));
vi.mock("@framework/ui/Filter", () => ({ Filter: stub("filter") }));
vi.mock("@framework/ui/SortBy", () => ({ SortBy: stub("sort") }));
vi.mock("@framework/ui/ColumnSettings", () => ({ ColumnSettings: stub("columns") }));
// The list draws its `empty` slot when it has no rows, as the real one does once loaded.
vi.mock("@framework/ui/experimental/List", async () => {
	const { defineComponent, h } = await import("vue");
	return {
		List: defineComponent({
			setup: (_, { slots }) => () => h("div", { "data-stub-list": "" }, slots.empty?.()),
		}),
		ListBulkBar: stub("bulk-bar"),
		ListFooter: stub("footer"),
	};
});
vi.mock("@/list/useScrollMemory", () => ({ useScrollMemory: () => {} }));
vi.mock("@/list/useListPage", async () => {
	const { ref } = await import("vue");
	return {
		useListPage: () => {
			const empty = () => ref([]);
			page.state = {
				filters: empty(),
				rows: empty(),
				error: ref(null),
				metaError: ref(null),
			};
			return {
				...page.state,
				sort: empty(),
				columns: empty(),
				quickFilterFields: ref(undefined),
				customizing: ref(false),
				selection: empty(),
				pageSize: ref(20),
				rowsKey: () => "",
				loading: ref(false),
				seeded: ref(true),
				rowCount: ref(0),
				totalCount: ref(0),
				totalCapped: ref(false),
				totalUnknown: ref(false),
				hasCounts: ref(true),
				hasNextPage: ref(false),
				reload: page.reload,
				reloadMeta: page.reloadMeta,
			};
		},
	};
});

import List from "../../List.vue";
import DoctypeList from "../DoctypeList.vue";

const apps: App[] = [];

// The Create button reads meta and the session; no server answers here.
beforeEach(() => {
	vi.stubGlobal(
		"fetch",
		async () =>
			new Response(JSON.stringify({ errors: [{ type: "NotFound" }] }), { status: 404 })
	);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
	page.reload.mockReset();
	page.reloadMeta.mockReset();
});

async function mount(component = DoctypeList, doctype: string | null = "Contact") {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:doctype", component: { render: () => null } }],
	});
	await router.push("/contact");
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(component, { doctype }) }));
	app.use(router).provide("addresses", {
		moduleName: () => null,
		doctypeOf: () => doctype,
	});
	app.mount(root);
	apps.push(app);
	await nextTick();
	return {
		state: () => root.querySelector<HTMLElement>("[data-page-state]")?.dataset.pageState,
		text: () => root.textContent ?? "",
		has: (selector: string) => root.querySelector(selector) !== null,
		tryAgain: () =>
			[...root.querySelectorAll("button")]
				.find((button) => button.textContent?.trim() === "Try again")!
				.click(),
	};
}

async function set(key: string, value: unknown) {
	page.state[key].value = value;
	await nextTick();
}

describe("a failed meta read", () => {
	it("draws the no permission state in place of the controls and the table", async () => {
		const list = await mount();
		await set("metaError", new ApiError({ type: "PermissionError", message: "No" }, 403));

		expect(list.state()).toBe("noPermission");
		expect(list.has("[data-stub-filter]")).toBe(false);
		expect(list.has("[data-stub-list]")).toBe(false);
		expect(list.text()).toContain("Contact");
	});

	it("draws the offline state on a network failure, and Try again reads the meta again", async () => {
		const list = await mount();
		await set("metaError", new ApiError({ type: "NetworkError", message: "Failed" }, 0));

		expect(list.state()).toBe("offline");
		list.tryAgain();
		expect(page.reloadMeta).toHaveBeenCalledOnce();
	});
});

describe("a rows read", () => {
	it("that failed draws the failed state under the controls, and Try again reads the rows again", async () => {
		const list = await mount();
		await set("error", new ApiError({ type: "Error", message: "<b>Query</b> timed out" }, 500));

		expect(list.state()).toBe("failed");
		expect(list.text()).toContain("Query timed out");
		expect(list.has("[data-page-state] b")).toBe(false);
		expect(list.has("[data-stub-filter]")).toBe(true);

		list.tryAgain();
		expect(page.reload).toHaveBeenCalledOnce();
	});

	it("that failed past rows on show draws the failed state in the table's place", async () => {
		const list = await mount();
		await set("rows", [{ name: "LEAD-1" }]);
		await set("error", new ApiError({ type: "Error", message: "Timed out" }, 500));

		expect(list.state()).toBe("failed");
		expect(list.has("[data-stub-list]")).toBe(false);
	});

	it("with no rows draws the empty state", async () => {
		const list = await mount();
		expect(list.state()).toBe("empty");
	});

	it("with no rows under a filter draws the filtered state", async () => {
		const list = await mount();
		await set("filters", [["status", "=", "Open"]]);
		expect(list.state()).toBe("filtered");
	});
});

describe("an address with no doctype", () => {
	it("draws the not found state", async () => {
		const list = await mount(List, null);
		expect(list.state()).toBe("notFound");
	});
});
