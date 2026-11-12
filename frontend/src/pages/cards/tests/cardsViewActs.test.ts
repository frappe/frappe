// The Cards renderer hands the page its part of the `list` act context: its rows, selection and reload.
import { createListPageLists } from "@/listPage/createListPage";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, ref } from "vue";
import CardsView from "../CardsView.vue";

const reload = vi.fn();
const picked = vi.hoisted(() => ({ value: [] as string[] }));

vi.mock("../useCardsView", () => ({
	useCardsView: () => ({
		selection: picked,
		scope: {
			all: ref(false),
			count: ref(0),
			total: ref(0),
			approx: ref(false),
			canSelectAll: ref(false),
			clear: () => {},
			selected: () => ({ names: [] }),
		},
		deleteSelection: () => {},
		fields: { title: "title", body: "content", bodyIsHtml: true },
		rowActions: ref([]),
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

function mountView(acts: ReturnType<typeof vi.fn>) {
	const host = { controls: ref(null), bar: ref(null), selecting: ref(false), lists: createListPageLists(), acts, onCreate: () => {} };
	const app = createApp(CardsView, { view: { doctype: "Note", filters: [], update: () => {} }, host });
	app.provide("boot", { bulk_actions: 1, bulk_operation_limit: 500 });
	app.mount(document.createElement("div"));
	mounted.push(app);
	return nextTick();
}

type Entries = () => { item: { name: string } }[];
type State = { rows: () => unknown[]; selection: () => string[]; reload: () => void };

describe("CardsView acts", () => {
	it("passes host.acts its entries and a state with its rows, selection and reload", async () => {
		picked.value = ["NOTE-1"];
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		await mountView(acts);

		expect(acts).toHaveBeenCalledTimes(1);
		const [entries, state] = acts.mock.calls[0] as unknown as [Entries, State];
		expect(entries().map((entry) => entry.item.name)).toEqual(["delete", "delete_card"]);
		expect(state.selection()).toEqual(["NOTE-1"]);
		expect(state.reload).toBe(reload);
	});

	it("offers the bulk actions only while cards are selected, and a card's own delete always", async () => {
		picked.value = [];
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		await mountView(acts);

		const [entries] = acts.mock.calls[0] as unknown as [Entries];
		expect(entries().map((entry) => entry.item.name)).toEqual(["delete_card"]);
	});
});
