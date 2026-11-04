// The Cards renderer hands the page its part of the `list` act context: no selection, and its reload.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, ref } from "vue";
import CardsView from "../CardsView.vue";

const reload = vi.fn();

vi.mock("../useCardsView", () => ({
	useCardsView: () => ({
		fields: { title: "title", body: "content", bodyIsHtml: true },
		rowActions: [],
		people: {},
		pageSize: ref(20),
		rows: ref([]),
		loading: ref(false),
		error: ref(null),
		rowCount: ref(0),
		totalCount: ref(0),
		totalCapped: ref(false),
		totalUnknown: ref(false),
		hasCounts: ref(false),
		hasNextPage: ref(false),
		next: () => {},
		show: () => {},
		countExact: () => {},
		reload,
		cardLink: () => "",
		deleteOne: () => {},
	}),
}));
vi.mock("@framework/ui/useDoctypeMeta", () => ({ useDoctypeMeta: () => ({ meta: ref(null) }) }));
vi.mock("@framework/ui/experimental/List", () => ({ ListFooter: { template: "<div />" } }));
vi.mock("@/pages/list/DeleteDialog.vue", () => ({ default: { template: "<div />" } }));
vi.mock("@/shell/PageFrame.vue", () => ({ pageGutter: "" }));
vi.mock("@/shell/PageState.vue", () => ({ default: { template: "<div />" } }));
vi.mock("../CardSettings.vue", () => ({ default: { template: "<div />" } }));
vi.mock("../CardItem.vue", () => ({ default: { template: "<div />" } }));

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
});

describe("CardsView acts", () => {
	it("passes host.acts its entries and a context with no selection and its reload", async () => {
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		const host = { controls: ref(null), acts, onCreate: () => {} };
		const app = createApp(CardsView, { view: { doctype: "Note", filters: [], update: () => {} }, host });
		app.mount(document.createElement("div"));
		mounted.push(app);
		await nextTick();

		expect(acts).toHaveBeenCalledTimes(1);
		const [entries, context] = acts.mock.calls[0] as unknown as [() => { item: { name: string } }[], () => unknown];
		expect(entries().map((entry) => entry.item.name)).toEqual(["delete"]);
		expect(context()).toEqual({ selection: [], reload });
	});
});
