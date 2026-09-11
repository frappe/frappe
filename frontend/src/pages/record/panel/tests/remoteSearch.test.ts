// The server search behind the pickers: the latest answer wins, pinned options fill its gaps.
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useRemoteSearch, useTagSearch, useUserSearch, type SearchOption } from "../remoteSearch";

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
	it("looks users up by name or email and shapes the rows", async () => {
		const call = vi.fn(async () => [
			{ name: "ann@example.com", full_name: "Ann", user_image: "/ann.png" },
			{ name: "bob@example.com", full_name: "", user_image: null },
		]);
		const { options, search } = useUserSearch(call, ref([]));
		await search("an");
		expect(call).toHaveBeenCalledWith(
			"frappe.client.get_list",
			expect.objectContaining({
				doctype: "User",
				or_filters: [
					["full_name", "like", "%an%"],
					["name", "like", "%an%"],
				],
			})
		);
		expect(options.value).toEqual([
			{ label: "Ann", value: "ann@example.com", image: "/ann.png" },
			{ label: "bob@example.com", value: "bob@example.com", image: "" },
		]);
	});

	it("looks tags up for the doctype with the trimmed query", async () => {
		const call = vi.fn(async () => ["urgent"]);
		const { options, search } = useTagSearch(call, "CRM Deal", ref([]));
		await search(" urg ");
		expect(call).toHaveBeenCalledWith("frappe.desk.doctype.tag.tag.get_tags", {
			doctype: "CRM Deal",
			txt: "urg",
		});
		expect(options.value).toEqual([{ label: "urgent", value: "urgent" }]);
	});
});
