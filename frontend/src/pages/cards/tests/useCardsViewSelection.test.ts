// The cards view's selection: a card that leaves the page leaves it, and the bulk delete clears it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, ref } from "vue";
import { createListPageLists } from "@/listPage/createListPage";
import { useCardsView, type CardsView } from "../useCardsView";

const fake = vi.hoisted(() => ({ rows: null as null | { value: { name: string }[] }, deleteRows: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ listDocuments: vi.fn() }));
vi.mock("@framework/ui/useDocPermissions", () => ({ useDocPermissions: () => ({ fieldAccess: () => "write" }) }));
vi.mock("@framework/ui/useDoctypeMeta", () => ({ useDoctypeMeta: () => ({ meta: ref({ fields: [] }) }) }));
vi.mock("@framework/ui/useSession", () => ({ currentSession: () => ({ user: { name: "alice@example.com" } }) }));
vi.mock("@/list/pageState", () => ({ useRememberedPageSize: () => ref(20) }));
vi.mock("@/list/useListView", () => ({ deleteRow: vi.fn(), deleteRows: fake.deleteRows, filtersDict: () => ({}) }));
vi.mock("@/list/useListRows", () => ({
	useListRows: () => ({
		rows: (fake.rows = ref([{ name: "A" }, { name: "B" }, { name: "C" }])),
		loadedKey: ref("q"),
	}),
}));

const apps: ReturnType<typeof createApp>[] = [];

function cardsView(): CardsView {
	let result!: CardsView;
	const view = { doctype: "Lead", seeded: ref(true), filters: ref([]), sort: ref([]), settings: ref({}) };
	const app = createApp({
		setup() {
			result = useCardsView(view as never, createListPageLists());
			return () => null;
		},
	});
	app.provide("boot", { session: { user: { name: "alice@example.com" } } });
	app.mount(document.createElement("div"));
	apps.push(app);
	return result;
}

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	fake.deleteRows.mockReset();
});

describe("cards view selection", () => {
	it("drops a card that left the page and keeps the rest", async () => {
		const view = cardsView();
		view.selection.value = ["A", "C"];
		fake.rows!.value = [{ name: "B" }, { name: "C" }];
		await nextTick();

		expect(view.selection.value).toEqual(["C"]);
	});

	it("deletes the selection in one bulk request and clears it", async () => {
		fake.deleteRows.mockResolvedValue({ deleted: [], failed: [] });
		const view = cardsView();
		view.selection.value = ["A", "B"];

		const outcome = await view.deleteSelection();

		expect(fake.deleteRows).toHaveBeenCalledWith("Lead", expect.anything(), { names: ["A", "B"] }, expect.any(Function));
		expect(outcome.failed).toEqual([]);
		expect(view.selection.value).toEqual([]);

		fake.deleteRows.mock.calls[0][3](["B"]);
		expect(view.selection.value).toEqual(["B"]);
	});
});
