// The depth cap as the editor asks it. `nesting.cases.json` is shared with the server's
// `frappe/tests/test_navigation_nesting.py`, so the two languages cannot drift apart.
import { describe, expect, it } from "vitest";
import cases from "./nesting.cases.json";
import { canNestUnder, type NavigationContainer } from "../nesting";
import type { NavigationItem } from "@/boot";

type Case = {
	name: string;
	container: NavigationContainer;
	items: NavigationItem[];
	moves: { key: string; parent: string | null; allowed: boolean }[];
};

describe("canNestUnder", () => {
	for (const { name, container, items, moves } of cases.cases as Case[]) {
		for (const { key, parent, allowed } of moves) {
			const move = `${key} under ${parent ?? "the top level"}`;

			it(`${allowed ? "allows" : "refuses"} ${move}: ${name}`, () => {
				const byKey = new Map(items.map((row) => [row.key, row]));
				const target = parent ? byKey.get(parent)! : null;

				expect(canNestUnder(byKey.get(key)!, target, container, items)).toBe(allowed);
			});
		}
	}
});
