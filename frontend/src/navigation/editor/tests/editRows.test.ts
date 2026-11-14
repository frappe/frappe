import { describe, expect, it } from "vitest";
import { type Draft, type EditorRow, newKey, RAIL, rowsOf } from "../draft";
import {
	OWN_ROWS_PER_APP,
	OWN_ROWS_PER_CONTAINER,
	add,
	canGiveSidebar,
	dropAcross,
	dropInto,
	giveSidebar,
	moveTo,
	refused,
	remove,
	removeSidebar,
} from "../edits";

const row = (key: string, more: Partial<EditorRow> = {}): EditorRow => ({
	key,
	item_type: "DocType",
	link_to: key,
	...more,
});

const own = (n: number, more: Partial<EditorRow> = {}) => row(`user:${String(n).padStart(6, "0")}`, more);

const draft = (rail: EditorRow[], sidebars: Draft["sidebars"] = {}): Draft => ({ rail, sidebars, layout: "" });

const keys = (d: Draft, container: string) => rowsOf(d, container).map((r) => r.key);
const ok = <T>(value: T | string): T => {
	expect(typeof value).not.toBe("string");
	return value as T;
};

describe("newKey", () => {
	it("is the scope and six base36 characters", () => {
		expect(newKey("user")).toMatch(/^user:[0-9a-z]{6}$/);
		expect(newKey("site")).toMatch(/^site:[0-9a-z]{6}$/);
	});
});

describe("add", () => {
	it("puts the row last, or last under its parent", () => {
		const d = draft([row("a"), row("b")], { s: [row("sec", { item_type: "Section" }), row("x")] });
		expect(keys(ok(add(d, RAIL, own(1), null, "user")), RAIL)).toEqual(["a", "b", "user:000001"]);
		const under = ok(add(d, "s", own(2), "sec", "user"));
		expect(keys(under, "s")).toEqual(["sec", "user:000002", "x"]);
		expect(rowsOf(under, "s")[1].parent_key).toBe("sec");
	});

	it("refuses a section on the rail and a row past the depth cap", () => {
		expect(refused(add(draft([row("a")]), RAIL, own(1, { item_type: "Section" }), null, "user"))).toBe(true);
		expect(refused(add(draft([row("a")]), RAIL, own(1), "a", "user"))).toBe(true);
	});

	it("stops at the caps", () => {
		const full = draft(Array.from({ length: OWN_ROWS_PER_CONTAINER }, (_, n) => own(n)));
		expect(refused(add(full, RAIL, own(900), null, "user"))).toBe(true);

		const spread = draft(
			[],
			Object.fromEntries(
				[0, 1].map((s) => [`k${s}`, Array.from({ length: OWN_ROWS_PER_CONTAINER }, (_, n) => own(s * 100 + n))])
			)
		);
		expect(refused(add(spread, RAIL, own(900), null, "user"))).toBe(true);
		expect(OWN_ROWS_PER_APP).toBe(100);
		expect(refused(add(spread, RAIL, own(900), null, "site"))).toBe(false);
	});
});

describe("remove", () => {
	it("deletes own descendants and lifts inherited children", () => {
		const d = draft([
			own(1, { item_type: "Section" }),
			own(2, { parent_key: "user:000001" }),
			row("app-child", { parent_key: "user:000001" }),
		]);
		const next = ok(remove(d, RAIL, "user:000001", "user"));
		expect(keys(next, RAIL)).toEqual(["app-child"]);
		expect(rowsOf(next, RAIL)[0].parent_key).toBeUndefined();
	});

	it("refuses an inherited row, and takes an own sidebar with its row", () => {
		const d = draft([row("a"), own(1, { opens_sidebar: "user:00000s" })], { "user:00000s": [own(3)] });
		expect(refused(remove(d, RAIL, "a", "user"))).toBe(true);
		expect(ok(remove(d, RAIL, "user:000001", "user")).sidebars).toEqual({});
		expect(refused(remove(d, RAIL, "user:000001", "site"))).toBe(true);
	});
});

describe("moveTo", () => {
	it("moves an own row with its key and children", () => {
		const d = draft([], {
			s: [own(2, { item_type: "Section" }), own(3, { parent_key: "user:000002" })],
			t: [row("x")],
		});
		const { draft: next, key } = ok(moveTo(d, "s", "user:000002", "t", "user")) as { draft: Draft; key: string };
		expect(key).toBe("user:000002");
		expect(keys(next, "s")).toEqual([]);
		expect(keys(next, "t")).toEqual(["x", "user:000002", "user:000003"]);
		expect(rowsOf(next, "t")[2].parent_key).toBe("user:000002");
	});

	it("refuses to put a row with children, or a section, on the rail", () => {
		const d = draft([], { s: [own(1, { item_type: "Section" }), own(2, { parent_key: "user:000001" }), own(3)] });
		expect(refused(moveTo(d, "s", "user:000001", RAIL, "user"))).toBe(true);
		expect(refused(moveTo(d, "s", "user:000003", RAIL, "user"))).toBe(false);
	});

	it("hides an inherited row in place and adds an own copy with a new key", () => {
		const d = draft([row("a", { label: "A", icon: "star" }), row("b")], { s: [row("x")] });
		const { draft: next, key } = ok(moveTo(d, RAIL, "a", "s", "user")) as { draft: Draft; key: string };
		expect(rowsOf(next, RAIL)[0]).toMatchObject({ key: "a", hidden: 1 });
		expect(keys(next, "s")).toEqual(["x", key]);
		expect(key).toMatch(/^user:/);
		expect(rowsOf(next, "s")[1]).toMatchObject({ item_type: "DocType", link_to: "a", label: "A", icon: "star" });
		expect(rowsOf(next, "s")[1].hidden).toBeUndefined();
	});

	it("copies an inherited row's children and hides them with it", () => {
		const d = draft([], { s: [row("sec", { item_type: "Section" }), row("c", { parent_key: "sec" })], t: [] });
		const { draft: next, key } = ok(moveTo(d, "s", "sec", "t", "user")) as { draft: Draft; key: string };
		const [parent, child] = rowsOf(next, "t");
		expect(parent.key).toBe(key);
		expect(child.parent_key).toBe(key);
		expect(rowsOf(next, "s").every((r) => r.hidden === 1)).toBe(true);
	});

	it("refuses a row going into the sidebar it opens", () => {
		const d = draft([row("a", { opens_sidebar: "s" })], { s: [row("x")] });
		expect(refused(moveTo(d, RAIL, "a", "s", "user"))).toBe(true);
		expect(refused(dropInto(d, RAIL, "a", "a", "user"))).toBe(true);
	});

	it("counts the target's cap", () => {
		const d = draft([row("a")], { s: Array.from({ length: OWN_ROWS_PER_CONTAINER }, (_, n) => own(n)) });
		expect(refused(moveTo(d, RAIL, "a", "s", "user"))).toBe(true);
	});
});

describe("drops", () => {
	const d = draft([row("a"), row("b", { opens_sidebar: "user:00000s" })], { "user:00000s": [own(1)] });

	it("drops into a linked rail row's sidebar, last", () => {
		const { draft: next } = ok(dropInto(d, RAIL, "a", "b", "user")) as { draft: Draft };
		expect(keys(next, "user:00000s")).toHaveLength(2);
		expect(refused(dropInto(d, RAIL, "a", "a", "user"))).toBe(true);
	});

	it("drops across containers before a row", () => {
		const { draft: next, key } = ok(dropAcross(d, RAIL, "a", "user:00000s", "user:000001", "user")) as {
			draft: Draft;
			key: string;
		};
		expect(keys(next, "user:00000s")[0]).toBe(key);
	});
});

describe("sidebars", () => {
	it("gives a rail row a sidebar whose first row copies its target", () => {
		const d = draft([row("a", { label: "A" })]);
		const { draft: next, key } = ok(giveSidebar(d, "a", "user")) as { draft: Draft; key: string };
		const sidebar = rowsOf(next, RAIL)[0].opens_sidebar!;
		expect(sidebar).toMatch(/^user:/);
		expect(rowsOf(next, sidebar)).toEqual([expect.objectContaining({ key, item_type: "DocType", link_to: "a", label: "A" })]);
		expect(canGiveSidebar(next, rowsOf(next, RAIL)[0])).toBe(false);
		expect(refused(giveSidebar(next, "a", "user"))).toBe(true);
	});

	it("removes an own sidebar and refuses an inherited one", () => {
		const d = draft([own(1, { opens_sidebar: "user:00000s" }), row("a", { opens_sidebar: "sb" })], {
			"user:00000s": [own(2)],
			sb: [row("x")],
		});
		const next = ok(removeSidebar(d, "user:000001", "user"));
		expect(rowsOf(next, RAIL)[0].opens_sidebar).toBeUndefined();
		expect(Object.keys(next.sidebars)).toEqual(["sb"]);
		expect(refused(removeSidebar(d, "a", "user"))).toBe(true);
	});
});
