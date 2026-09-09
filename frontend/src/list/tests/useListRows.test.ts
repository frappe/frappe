// The rows composable on its own: when the first query runs, and what a page-size change fetches.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, reactive, ref } from "vue";
import { useListRows, type RowsQuery } from "../useListRows";

const fake = vi.hoisted(() => ({ useList: vi.fn(), call: vi.fn() }));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<object>()),
	useList: fake.useList,
	call: fake.call,
}));

function fakeList() {
	return reactive({ data: null, error: null, hasNextPage: true, delete: { submit: vi.fn() } });
}

function queryOf(limit: number): RowsQuery {
	return { key: "q", fields: ["name"], filters: {}, orderBy: "modified desc", limit };
}

function fetches() {
	return fake.useList.mock.calls.map(([options]) => [options.start, options.limit]);
}

beforeEach(() => {
	fake.useList.mockReset().mockImplementation(fakeList);
	fake.call.mockReset().mockResolvedValue(1);
});

describe("useListRows", () => {
	it("runs the first query at once, also when it lands after a null one", async () => {
		const query = ref<RowsQuery | null>(null);
		useListRows("ToDo", () => query.value);
		await nextTick();
		expect(fake.useList).not.toHaveBeenCalled();
		query.value = queryOf(20);
		await nextTick();
		expect(fetches()).toEqual([[0, 20]]);
	});

	it("a bigger page size while a page is in flight starts over instead of stacking", async () => {
		const limit = ref(20);
		useListRows("ToDo", () => queryOf(limit.value));
		await nextTick();
		limit.value = 100;
		await nextTick();
		expect(fetches()).toEqual([
			[0, 20],
			[0, 100],
		]);
	});
});
