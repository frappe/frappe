// The Cards renderer hands the page its part of the `list` act context: its rows, selection and reload,
// and selects as the List does: a shift-click range, the bulk keys and the bar's Edit, Export and Copy.
import { createListPageLists } from "@/listPage/createListPage";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, ref, type Ref } from "vue";
import CardsView from "../CardsView.vue";

const reload = vi.fn();
const fake = vi.hoisted(() => ({
	picked: [] as string[],
	rows: [] as { name: string }[],
	selection: null as null | Ref<string[]>,
}));

vi.mock("../useCardsView", () => ({
	useCardsView: () => ({
		selection: (fake.selection = ref([...fake.picked])),
		scope: {
			all: ref(false),
			count: ref(0),
			total: ref(0),
			approx: ref(false),
			canSelectAll: ref(false),
			clear: () => {},
			selected: () => ({ names: [...fake.selection!.value] }),
		},
		deleteSelection: () => {},
		fields: { title: "title", body: "content", bodyIsHtml: true },
		rowActions: ref([]),
		people: {},
		pageSize: ref(20),
		rows: ref(fake.rows),
		readFields: () => ["name"],
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
		titleClassOf: () => "",
		deleteOne: () => {},
	}),
}));
vi.mock("@framework/ui/useDoctypeMeta", () => ({ useDoctypeMeta: () => ({ meta: ref(null) }) }));
vi.mock("@framework/ui/experimental/List", async (original) => ({
	...(await original<typeof import("@framework/ui/experimental/List")>()),
	ListFooter: { template: "<div />" },
}));
vi.mock("@/pages/list/DeleteDialog.vue", () => ({ default: { template: "<div />" } }));
vi.mock("@/pages/list/ExportDialog.vue", () => ({
	__esModule: true,
	default: { props: ["selection"], template: `<div class="export">{{ selection.names.join(",") }}</div>` },
}));
vi.mock("@/shell/PageFrame.vue", () => ({ pageGutter: "" }));
vi.mock("@/shell/PageState.vue", () => ({ default: { template: "<div />" } }));
vi.mock("../CardSettings.vue", () => ({ default: { template: "<div />" } }));
vi.mock("../CardItem.vue", () => ({
	default: { emits: ["toggle"], template: `<div class="card" @click="$emit('toggle', $event.shiftKey)" />` },
}));

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	fake.picked = [];
	fake.rows = [];
});

async function mountView(acts: ReturnType<typeof vi.fn>) {
	const host = { controls: ref(null), lists: createListPageLists(), acts, onCreate: () => {} };
	const app = createApp(CardsView, { view: { doctype: "Note", filters: [], update: () => {} }, host });
	app.provide("boot", { bulk_actions: 1, bulk_operation_limit: 500, session: { user: { name: "jane@example.com" } } });
	const root = document.createElement("div");
	app.mount(root);
	mounted.push(app);
	await vi.dynamicImportSettled();
	await nextTick();
	return root;
}

type Entries = () => { item: { name: string; run?: () => void }; hidden: boolean }[];
type State = { rows: () => unknown[]; selection: () => string[]; reload: () => void };

describe("CardsView acts", () => {
	it("passes host.acts its entries and a state with its rows, selection and reload", async () => {
		fake.picked = ["NOTE-1"];
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		await mountView(acts);

		expect(acts).toHaveBeenCalledTimes(1);
		const [entries, state] = acts.mock.calls[0] as unknown as [Entries, State];
		expect(entries().map((entry) => entry.item.name)).toEqual(expect.arrayContaining(["delete", "delete_card"]));
		expect(state.selection()).toEqual(["NOTE-1"]);
		expect(state.reload).toBe(reload);
	});

	it("offers the bulk actions only while cards are selected, and a card's own delete always", async () => {
		fake.picked = [];
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		await mountView(acts);

		const [entries] = acts.mock.calls[0] as unknown as [Entries];
		expect(shown(entries)).toEqual(["delete_card"]);
	});

	it("gives the bar Edit, Export and Copy, and the keys the List has, while cards are selected", async () => {
		fake.picked = ["NOTE-1"];
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		await mountView(acts);

		const [entries] = acts.mock.calls[0] as unknown as [Entries];
		expect(shown(entries)).toEqual(expect.arrayContaining(["edit", "export", "copy", "clear_selection"]));
		expect(entries().map((entry) => entry.item.name)).toEqual(
			expect.arrayContaining(["toggle_row", "extend_row", "open_bulk_menu"])
		);
	});

	it("selects a range on a shift-click, and toggles and extends from the card under the pointer", async () => {
		fake.picked = [];
		fake.rows = ["NOTE-1", "NOTE-2", "NOTE-3", "NOTE-4"].map((name) => ({ name }));
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		const root = await mountView(acts);
		const cards = root.querySelectorAll<HTMLElement>(".card");
		const [entries] = acts.mock.calls[0] as unknown as [Entries];
		const run = (name: string) => entries().find((entry) => entry.item.name === name)!.item.run!();

		cards[0].click();
		cards[2].dispatchEvent(new MouseEvent("click", { shiftKey: true }));
		expect(fake.selection!.value).toEqual(["NOTE-1", "NOTE-2", "NOTE-3"]);

		cards[3].dispatchEvent(new PointerEvent("pointerenter"));
		run("toggle_row");
		expect(fake.selection!.value).toEqual(["NOTE-1", "NOTE-2", "NOTE-3", "NOTE-4"]);
		run("toggle_row");
		cards[1].dispatchEvent(new PointerEvent("pointerenter"));
		run("toggle_row");
		expect(fake.selection!.value).toEqual(["NOTE-1", "NOTE-3"]);
		cards[3].dispatchEvent(new PointerEvent("pointerenter"));
		run("extend_row");
		expect(fake.selection!.value).toEqual(["NOTE-1", "NOTE-2", "NOTE-3", "NOTE-4"]);
	});

	it("opens Export from the bar with the selected cards", async () => {
		fake.picked = ["NOTE-1", "NOTE-2"];
		const acts = vi.fn(() => ({ drawn: () => undefined }));
		const root = await mountView(acts);
		const [entries] = acts.mock.calls[0] as unknown as [Entries];

		entries().find((entry) => entry.item.name === "export")!.item.run!();
		await vi.dynamicImportSettled();
		await nextTick();
		expect(root.querySelector(".export")?.textContent).toBe("NOTE-1,NOTE-2");
	});
});

function shown(entries: Entries) {
	return entries()
		.filter((entry) => !entry.hidden)
		.map((entry) => entry.item.name);
}
