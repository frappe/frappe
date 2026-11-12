import { describe, expect, it } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { useBulkScope } from "../useBulkScope";

const named = (names: string[]) => names.map((name) => ({ name }));

function setup(loaded = ["A", "B", "C"], total = 1240) {
	const rows = ref(named(loaded));
	const selection = ref<string[]>([]);
	const filters = ref<Record<string, unknown>>({ status: ["=", "Open"] });
	const more = ref(true);
	const exact = ref(true);
	const scope = effectScope().run(() =>
		useBulkScope({
			selection,
			rows: () => rows.value,
			filters: () => filters.value,
			hasNextPage: () => more.value,
			totalCount: () => total,
			totalApprox: () => false,
			exact: () => exact.value,
		})
	)!;
	return { scope, rows, selection, filters, more, exact };
}

describe("useBulkScope", () => {
	it("offers Select all only when every loaded row is selected and more match", () => {
		const { scope, selection, more } = setup();
		expect(scope.canSelectAll.value).toBe(false);
		selection.value = ["A", "B"];
		expect(scope.canSelectAll.value).toBe(false);
		selection.value = ["A", "B", "C"];
		expect(scope.canSelectAll.value).toBe(true);
		more.value = false;
		expect(scope.canSelectAll.value).toBe(false);
	});

	it("holds Select all back while the total or the filters do not match the rows", () => {
		const { scope, selection, exact } = setup();
		selection.value = ["A", "B", "C"];
		exact.value = false;
		expect(scope.canSelectAll.value).toBe(false);
		exact.value = true;
		expect(scope.canSelectAll.value).toBe(true);
	});

	it("keeps Select all on while a reload empties the rows", async () => {
		const { scope, rows, selection } = setup();
		selection.value = ["A", "B", "C"];
		scope.selectAll();
		await nextTick();
		rows.value = [];
		await nextTick();
		expect(scope.all.value).toBe(true);
		rows.value = named(["C", "B"]);
		await nextTick();
		expect(selection.value).toEqual(["C", "B"]);
	});

	it("sends the names until Select all, then the list's filters", () => {
		const { scope, selection } = setup();
		selection.value = ["A", "B", "C"];
		expect(scope.selected()).toEqual({ names: ["A", "B", "C"] });
		expect(scope.count.value).toBe(3);

		scope.selectAll();
		expect(scope.selected()).toEqual({ filters: { status: ["=", "Open"] } });
		expect(scope.count.value).toBe(1240);
		expect(scope.canSelectAll.value).toBe(false);
	});

	it("drops all-matching when a row is unchecked, keeping the other rows selected", async () => {
		const { scope, selection } = setup();
		selection.value = ["A", "B", "C"];
		scope.selectAll();
		selection.value = ["A", "B"];
		await nextTick();
		expect(scope.all.value).toBe(false);
		expect(scope.selected()).toEqual({ names: ["A", "B"] });
	});

	it("keeps all-matching across a load-more and selects the rows that join", async () => {
		const { scope, rows, selection } = setup();
		selection.value = ["A", "B", "C"];
		scope.selectAll();
		await nextTick();
		rows.value = named(["A", "B", "C", "D"]);
		await nextTick();
		expect(scope.all.value).toBe(true);
		expect(selection.value).toEqual(["A", "B", "C", "D"]);
	});

	it("drops the selection altogether when the filters change", async () => {
		const { scope, selection, filters } = setup();
		selection.value = ["A", "B", "C"];
		scope.selectAll();
		await nextTick();
		filters.value = { status: ["=", "Closed"] };
		await nextTick();
		expect(scope.all.value).toBe(false);
		expect(selection.value).toEqual([]);
	});

	it("lets a row that left the page leave the selection", async () => {
		const { scope, rows, selection } = setup();
		selection.value = ["A", "B"];
		rows.value = named(["B", "C"]);
		await nextTick();
		expect(selection.value).toEqual(["B"]);
		expect(scope.all.value).toBe(false);
	});
});
