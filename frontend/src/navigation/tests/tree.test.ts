// The flat list becoming a tree (#42420).
//
// The server sends one flat, ordered list and `parent_key` is the whole of hierarchy
// (#42227), so everything about shape is rebuilt here. #42403's whole review was defects
// in code that edited one of the two orders a flat list carries and forgot the other;
// these are the reading half of that.
import { describe, expect, it, vi } from "vitest";
import { buildTree, type ItemNode } from "../tree";
import type { NavigationItem } from "@/boot";

function item(key: string, parent_key?: string): NavigationItem {
	return { key, item_type: "DocType", link_to: key, ...(parent_key ? { parent_key } : {}) };
}

/** The tree as `parent > child` paths, depth-first — which is the flat order back. */
function shape(nodes: ItemNode[], prefix = ""): string[] {
	return nodes.flatMap((node) => [
		prefix + node.item.key,
		...shape(node.children, `${prefix}${node.item.key} > `),
	]);
}

describe("building the tree", () => {
	it("keeps a flat list flat", () => {
		expect(shape(buildTree([item("a"), item("b")]))).toEqual(["a", "b"]);
	});

	it("files a row under the row its parent_key names", () => {
		expect(shape(buildTree([item("s"), item("a", "s"), item("b", "s")]))).toEqual([
			"s",
			"s > a",
			"s > b",
		]);
	});

	it("nests to any depth, because parent_key sets no limit", () => {
		const tree = buildTree([item("a"), item("b", "a"), item("c", "b"), item("d", "c")]);
		expect(shape(tree)).toEqual(["a", "a > b", "a > b > c", "a > b > c > d"]);
	});

	it("files a child that arrives before its parent", () => {
		// The order rows come back in is `idx` within a layer, and the merge interleaves
		// three of them — so a child preceding its parent is ordinary, not malformed.
		expect(shape(buildTree([item("a", "s"), item("s")]))).toEqual(["s", "s > a"]);
	});

	it("leaves an orphan at the top level", () => {
		// The server promotes these already (`_promote_orphans`), so this is the belt to
		// that braces: a row whose parent never arrived is drawn, never dropped.
		expect(shape(buildTree([item("a", "gone")]))).toEqual(["a"]);
	});

	it("reads a repeated key as ONE row written twice, last one winning", () => {
		// One row, not two. Placing the same node twice puts duplicate rows on screen under
		// a duplicate Vue `:key`, and the second is the one nobody can explain.
		const tree = buildTree([item("a"), { ...item("a"), label: "second" }]);
		expect(tree.map((node) => node.item.label)).toEqual(["second"]);
	});
});

describe("a parent_key cycle", () => {
	it("lifts a row that is its own parent", () => {
		const onCycle = vi.fn();
		expect(shape(buildTree([item("a", "a")], onCycle))).toEqual(["a"]);
		expect(onCycle).toHaveBeenCalledWith("a");
	});

	it("lifts every row in a two-row cycle rather than rendering neither", () => {
		// Both rows have a parent that is PRESENT, so the server's orphan promotion passes
		// them through untouched; each attaches to the other and neither reaches a root.
		// Rendering the tree would then simply omit authored navigation with nothing said.
		const onCycle = vi.fn();
		expect(shape(buildTree([item("a", "b"), item("b", "a")], onCycle))).toEqual(["a", "b"]);
		expect(onCycle.mock.calls.flat()).toEqual(["a", "b"]);
	});

	it("lifts every row of a longer ring too", () => {
		// Breaking only the row that closes the ring would leave the rest hanging off a row
		// that is now a root, which reads as a nesting somebody authored. Three flat rows are
		// visibly the odd ones out, which is what a reader needs in order to go and fix it.
		expect(shape(buildTree([item("a", "c"), item("b", "a"), item("c", "b")]))).toEqual([
			"a",
			"b",
			"c",
		]);
	});

	it("does not mistake two siblings under one parent for a cycle", () => {
		const onCycle = vi.fn();
		buildTree([item("s"), item("a", "s"), item("b", "s")], onCycle);
		expect(onCycle).not.toHaveBeenCalled();
	});
});
