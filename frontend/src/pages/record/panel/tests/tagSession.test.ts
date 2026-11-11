import { describe, expect, it, vi } from "vitest";
import { appliedFirst, splitTags, tagBatch, useTagSession, type TagBatch } from "../tagSession";

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

	it("sends nothing when the draft equals the record, or when no session is open", async () => {
		const write = vi.fn(async () => {});
		const session = useTagSession(() => ["a"], write, async () => {});
		session.begin();
		await session.commit();
		await session.commit();
		expect(write).not.toHaveBeenCalled();
	});

	it("shows the record's tags again when the write fails", async () => {
		const write = vi.fn(async () => {
			throw new Error("no");
		});
		const session = useTagSession(() => ["a"], write, async () => {});
		session.begin();
		session.addNew("n", "Red");
		expect(session.tags.value).toEqual(["a", "n"]);
		await session.commit().catch(() => undefined);
		expect(write).toHaveBeenCalledTimes(1);
		expect(session.tags.value).toEqual(["a"]);
	});

	it("keeps a session reopened during a write, and diffs it against what that write sent", async () => {
		let server = ["a"];
		let release = () => {};
		const write = vi.fn(async (batch: TagBatch) => {
			if (write.mock.calls.length === 1) await new Promise<void>((resolve) => (release = resolve));
			server = server.filter((tag) => !batch.removed.includes(tag)).concat(batch.added.map((item) => item.tag));
		});
		const session = useTagSession(() => server, write, async () => {});
		session.begin();
		session.set(["a", "b"]);
		const first = session.commit();
		session.begin();
		session.set(["a", "b", "c"]);
		const second = session.commit();
		await vi.waitFor(() => expect(write).toHaveBeenCalledTimes(1));
		release();
		await Promise.all([first, second]);
		expect(write.mock.calls.map(([batch]) => batch)).toEqual([
			{ added: [{ tag: "b", color: undefined }], removed: [] },
			{ added: [{ tag: "c", color: undefined }], removed: [] },
		]);
		expect(session.tags.value).toEqual(["a", "b", "c"]);
	});

	it("recolours a tag only after the write that creates it has settled", async () => {
		const order: string[] = [];
		let release = () => {};
		const write = vi.fn(async () => {
			await new Promise<void>((resolve) => (release = resolve));
			order.push("write");
		});
		const recolour = vi.fn(async () => {
			order.push("recolour");
		});
		const session = useTagSession(() => [], write, recolour);
		session.begin();
		session.addNew("n", "Red");
		void session.commit();
		const recoloured = session.recolour("n", "Blue");
		await vi.waitFor(() => expect(write).toHaveBeenCalledTimes(1));
		release();
		await recoloured;
		expect(order).toEqual(["write", "recolour"]);
	});
});
