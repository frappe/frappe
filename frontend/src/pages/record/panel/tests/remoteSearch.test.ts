// The server search behind the pickers: the latest answer wins, pinned options fill its gaps.
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useRemoteSearch, useTagSearch, useUserSearch, type SearchOption } from "../remoteSearch";
import { TAG_COLORS, tagColorClass } from "@/tagColors";

const fake = vi.hoisted(() => ({ searchDocuments: vi.fn(), listDocuments: vi.fn() }));

vi.mock("@framework/ui/api", () => ({
	searchDocuments: fake.searchDocuments,
	listDocuments: fake.listDocuments,
}));

const option = (value: string): SearchOption => ({ label: value, value });

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason: unknown) => void;
	const promise = new Promise<T>((res, rej) => ((resolve = res), (reject = rej)));
	return { promise, resolve, reject };
}

describe("useRemoteSearch", () => {
	it("keeps the server's order and fills the gaps with the pinned options", async () => {
		const pinned = ref([option("ann"), option("zed")]);
		const { options, search, searched } = useRemoteSearch(
			async () => [option("zed"), option("bob")],
			pinned
		);
		expect(options.value.map((o) => o.value)).toEqual(["ann", "zed"]);
		await search();
		expect(searched.value).toBe(true);
		expect(options.value.map((o) => o.value)).toEqual(["zed", "bob", "ann"]);
	});

	it("drops an earlier answer that lands after a later one", async () => {
		const first = deferred<SearchOption[]>();
		const second = deferred<SearchOption[]>();
		const answers = [first.promise, second.promise];
		const { options, loading, search } = useRemoteSearch(() => answers.shift()!, ref([]));
		const one = search("a");
		const two = search("ab");
		second.resolve([option("ab")]);
		await two;
		expect(loading.value).toBe(false);
		first.resolve([option("a")]);
		await one;
		expect(options.value.map((o) => o.value)).toEqual(["ab"]);
	});

	it("keeps the failure's message and the last good answer", async () => {
		const { options, error, search } = useRemoteSearch(async (query) => {
			if (query === "bad") throw { messages: ["Not permitted"] };
			return [option("ok")];
		}, ref([]));
		await search("");
		await search("bad");
		expect(error.value).toBe("Not permitted");
		expect(options.value.map((o) => o.value)).toEqual(["ok"]);
	});
});

describe("the searches", () => {
	it("searches enabled system users for the typed text and shapes the rows", async () => {
		fake.searchDocuments.mockResolvedValue({
			data: [
				{ value: "ann@example.com", label: "Ann", description: "" },
				{ value: "bob@example.com", label: "" },
			],
		});
		const { options, search } = useUserSearch(ref([]));
		await search("an");
		expect(fake.searchDocuments).toHaveBeenCalledWith("User", {
			txt: "an",
			filters: {
				enabled: 1,
				user_type: "System User",
				name: ["not in", ["Administrator", "Guest"]],
			},
			limit: 10,
		});
		expect(options.value).toEqual([
			{ label: "Ann", value: "ann@example.com" },
			{ label: "bob@example.com", value: "bob@example.com" },
		]);
	});

	it("reads the matching Tags with their colours, by name", async () => {
		fake.listDocuments.mockResolvedValueOnce({ data: [{ name: "urgent", color: "Red" }, { name: "urge" }] });
		const { options, search } = useTagSearch(ref([]));
		await search(" urg ");
		expect(fake.listDocuments).toHaveBeenCalledWith("Tag", {
			fields: ["name", "color"],
			filters: [["name", "like", "%urg%"]],
			order_by: "name asc",
			limit: 10,
		});
		expect(options.value).toEqual([
			{ label: "urgent", value: "urgent" },
			{ label: "urge", value: "urge" },
		]);
		expect(tagColorClass("urgent")).toBe(TAG_COLORS.Red);
		expect(tagColorClass("urge")).toBe(TAG_COLORS.Gray);
	});
});
