import { describe, expect, it } from "vitest";
import { LoopCheck } from "../loopCheck.mjs";

const known = [
	["app/a", "app/b"],
	["app/c", "app/d", "app/e"],
];

describe("LoopCheck", () => {
	it("passes when today's groups are the known groups", () => {
		const check = new LoopCheck([["app/b", "app/a"], ["app/c", "app/d", "app/e"]], known);
		expect(check.passes).toBe(true);
		expect(check.report()).toEqual([]);
	});

	it("fails on a new group", () => {
		const check = new LoopCheck([...known, ["app/x", "app/y"]], known);
		expect(check.report()).toEqual(["NEW LOOP   app/x <-> app/y"]);
	});

	it("fails on a group that took in a new folder, and names the folder", () => {
		const check = new LoopCheck([["app/a", "app/b", "app/x"], known[1]], known);
		expect(check.report()).toEqual(["LOOP GREW  app/a <-> app/b <-> app/x: added app/x"]);
	});

	it("reports two known groups that joined as one grown group, not as two that shrank", () => {
		const check = new LoopCheck([["app/a", "app/b", "app/c", "app/d", "app/e"]], known);
		expect(check.report()).toEqual([
			"LOOP GREW  app/a <-> app/b <-> app/c <-> app/d <-> app/e: added a link between two known groups",
		]);
	});

	it("fails on a group that shrank or went, so the baseline follows the cut", () => {
		const check = new LoopCheck([["app/c", "app/d"]], known);
		expect(check.report()).toEqual([
			"LOOP SHRANK app/a <-> app/b: update it in knownLoops",
			"LOOP SHRANK app/c <-> app/d <-> app/e: update it in knownLoops",
		]);
	});
});
