import { describe, expect, it, vi } from "vitest";
import { appliedFirst, splitTags, tagBatch, useTagSession } from "../tagSession";

describe("tagBatch", () => {
	it("adds what the draft gained, with its colour, and drops what it lost", () => {
		const batch = tagBatch(["a", "b"], ["b", "c"], new Map([["c", "Teal"]]));
		expect(batch).toEqual({ added: [{ tag: "c", color: "Teal" }], removed: ["a"] });
	});

	it("is empty when ticks and unticks cancel", () => {
		expect(tagBatch(["a"], ["a"], new Map())).toEqual({ added: [], removed: [] });
	});
});

describe("splitTags", () => {
	it("draws three chips and hides the rest, only past four tags", () => {
		expect(splitTags(["a", "b", "c", "d"])).toEqual({ shown: ["a", "b", "c", "d"], hidden: [] });
		expect(splitTags(["a", "b", "c", "d", "e"])).toEqual({ shown: ["a", "b", "c"], hidden: ["d", "e"] });
	});
});

describe("appliedFirst", () => {
	it("lists the applied tags first, then A to Z", () => {
		const options = ["pear", "fig", "apple", "kiwi"].map((value) => ({ value }));
		expect(appliedFirst(options, ["pear", "kiwi"]).map((option) => option.value)).toEqual([
			"kiwi",
			"pear",
			"apple",
			"fig",
		]);
	});
});

describe("useTagSession", () => {
	it("shows the draft at once, sends one batch on commit, then shows the record again", async () => {
		let server = ["a"];
		const write = vi.fn(async () => {
			server = ["b"];
		});
		const session = useTagSession(() => server, write, async () => {});
		session.begin();
		session.set(["b"]);
		expect(session.tags.value).toEqual(["b"]);
		expect(write).not.toHaveBeenCalled();
		await session.commit();
		expect(write).toHaveBeenCalledWith({ added: [{ tag: "b", color: undefined }], removed: ["a"] });
		expect(session.tags.value).toEqual(["b"]);
	});

	it("sends nothing when the draft equals the record, and rolls back when the write fails", async () => {
		const write = vi.fn(async () => {
			throw new Error("no");
		});
		const session = useTagSession(() => ["a"], write, async () => {});
		session.begin();
		await session.commit();
		expect(write).not.toHaveBeenCalled();
		session.begin();
		session.addNew("n", "Red");
		await session.commit().catch(() => undefined);
		expect(session.tags.value).toEqual(["a"]);
	});
});
