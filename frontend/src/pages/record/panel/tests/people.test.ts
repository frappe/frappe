// What `docinfo` says about people and tags, and the list arithmetic behind each pick.
import { describe, expect, it } from "vitest";
import {
	assigneesOf,
	canCreateTag,
	listDiff,
	matchingTags,
	sharedWith,
	tagColor,
	tagsOf,
} from "../people";

const docinfo = {
	assignments: [{ owner: "ann@example.com" }, { owner: "bob@example.com" }],
	shared: [
		{ user: "ann@example.com", write: 1 as const },
		{ user: "", everyone: 1 as const },
	],
	tags: "urgent, q3 ,,",
	user_info: { "ann@example.com": { fullname: "Ann", image: "/ann.png" } },
};

describe("people", () => {
	it("names an assignee from user_info and falls back to the id", () => {
		expect(assigneesOf(docinfo)).toEqual([
			{ id: "ann@example.com", name: "Ann", image: "/ann.png" },
			{ id: "bob@example.com", name: "bob@example.com", image: undefined },
		]);
	});

	it("draws a share with everyone as such, and carries the write right", () => {
		expect(sharedWith(docinfo)).toEqual([
			{ id: "ann@example.com", name: "Ann", image: "/ann.png", everyone: false, canWrite: true },
			{ id: "everyone", name: "Everyone", everyone: true, canWrite: false },
		]);
	});

	it("reads nothing from a sidecar that has not landed", () => {
		expect(assigneesOf(null)).toEqual([]);
		expect(sharedWith(null)).toEqual([]);
		expect(tagsOf(null)).toEqual([]);
	});

	it("splits the comma-joined tags", () => {
		expect(tagsOf(docinfo)).toEqual(["urgent", "q3"]);
	});
});

describe("picks", () => {
	it("tells what a new selection adds and drops", () => {
		expect(listDiff(["a", "c"], ["a", "b"])).toEqual({ added: ["c"], dropped: ["b"] });
	});

	it("matches the record's own tags case-insensitively", () => {
		expect(matchingTags(["Urgent", "later"], "URG")).toEqual(["Urgent"]);
	});

	it("offers to create a tag only when the query names none that exist", () => {
		expect(canCreateTag(["urgent"], " Urgent ")).toBe(false);
		expect(canCreateTag(["urgent"], "")).toBe(false);
		expect(canCreateTag(["urgent"], "a, b")).toBe(false);
		expect(canCreateTag(["urgent"], "later")).toBe(true);
	});

	it("colours a tag by its name, the same on every record", () => {
		expect(tagColor("urgent")).toBe(tagColor("urgent"));
		expect(tagColor("urgent")).toMatch(/^bg-/);
	});
});
