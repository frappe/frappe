// The rows composable on its own: when the first query runs, what a page-size change fetches,
// and how the count beside the first page reads in the footer.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import { useListRows, type RowsQuery } from "../useListRows";

const fake = vi.hoisted(() => ({
	listDocuments: vi.fn(),
	countDocuments: vi.fn(),
	deleteDocument: vi.fn(),
}));

vi.mock("@framework/ui/api", () => ({
	listDocuments: fake.listDocuments,
	countDocuments: fake.countDocuments,
	deleteDocument: fake.deleteDocument,
}));

type Answer = {
	data: { name: string }[];
	has_next_page: boolean;
	count?: number | null;
	count_capped?: boolean;
};

const answers: ((answer: Answer) => void)[] = [];

function fakeList() {
	return new Promise<Answer>((resolve) => answers.push(resolve));
}

function queryOf(limit: number): RowsQuery {
	return { key: "q", fields: ["name"], filters: { status: "Open" }, orderBy: "modified desc", limit };
}

function fetches() {
	return fake.listDocuments.mock.calls.map(([, query]) => [query.start, query.limit]);
}

async function settle() {
	await Promise.resolve();
	await nextTick();
}

beforeEach(() => {
	answers.length = 0;
	fake.listDocuments.mockReset().mockImplementation(fakeList);
	fake.countDocuments.mockReset().mockResolvedValue({ data: 1234 });
	fake.deleteDocument.mockReset().mockResolvedValue({ data: "ok" });
});

describe("useListRows", () => {
	it("runs the first query at once, also when it lands after a null one", async () => {
		const query = ref<RowsQuery | null>(null);
		useListRows("ToDo", () => query.value);
		await nextTick();
		expect(fake.listDocuments).not.toHaveBeenCalled();
		query.value = queryOf(20);
		await nextTick();
		expect(fetches()).toEqual([[0, 20]]);
		expect(fake.listDocuments.mock.calls[0][2]).toEqual({ include: ["count"] });
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

	it("asks only the first page for the count", async () => {
		const rows = useListRows("ToDo", () => queryOf(20));
		await nextTick();
		const data = Array.from({ length: 20 }, (_, i) => ({ name: `T-${i}` }));
		answers[0]({ data, has_next_page: true, count: 50 });
		await settle();
		rows.next();
		expect(fake.listDocuments.mock.calls[1][2]).toEqual({ include: undefined });
		expect(rows.totalCount.value).toBe(50);
		expect(rows.totalCapped.value).toBe(false);
	});

	it("reads a capped count as a floor, and the exact count on request", async () => {
		const rows = useListRows("ToDo", () => queryOf(20));
		await nextTick();
		answers[0]({ data: [{ name: "T-1" }], has_next_page: true, count: 1000, count_capped: true });
		await settle();
		expect(rows.hasCounts.value).toBe(true);
		expect(rows.totalCount.value).toBe(1000);
		expect(rows.totalCapped.value).toBe(true);
		expect(rows.totalUnknown.value).toBe(false);

		await rows.countExact();
		expect(fake.countDocuments).toHaveBeenCalledWith("ToDo", { filters: { status: "Open" } });
		expect(rows.totalCount.value).toBe(1234);
		expect(rows.totalCapped.value).toBe(false);
	});

	it("shows the rows as a floor when the server gave up counting", async () => {
		const rows = useListRows("ToDo", () => queryOf(20));
		await nextTick();
		answers[0]({ data: [{ name: "T-1" }], has_next_page: true, count: null });
		await settle();
		expect(rows.hasCounts.value).toBe(true);
		expect(rows.totalUnknown.value).toBe(true);
		expect(rows.totalCount.value).toBe(1);
		expect(rows.totalCapped.value).toBe(true);
	});

	it("deletes a row through the wrapper", async () => {
		const rows = useListRows("ToDo", () => queryOf(20));
		await rows.remove("T-1");
		expect(fake.deleteDocument).toHaveBeenCalledWith("ToDo", "T-1");
	});
});
