import { describe, expect, it } from "vitest";
import {
	type Arrangements,
	type EditorRow,
	dirty,
	fromArrangements,
	openedSidebars,
	originOf,
	RAIL,
	resetToDefault,
	revert,
	toPayload,
} from "../draft";
import { dropBefore, moveAmongSiblings, nest, refused, toggleHidden, update } from "../edits";

const row = (key: string, more: Partial<EditorRow> = {}): EditorRow => ({
	key,
	item_type: "DocType",
	link_to: key,
	...more,
});

const response = (rail: EditorRow[], sidebars: Arrangements["sidebars"] = {}): Arrangements => ({
	version: "v1",
	can_edit_site: true,
	has_saved: true,
	navigation_layouts: { standard: "", site: "sidebar_only", user: "" },
	rail,
	sidebars,
});

const opened = fromArrangements(
	response([row("a"), row("b"), row("c")], {
		side: [row("s", { item_type: "Section" }), row("t", { parent_key: "s" }), row("u")],
	}),
	"site"
);

describe("the draft", () => {
	it("reads this level's layout and is clean until it changes", () => {
		expect(opened.layout).toBe("sidebar_only");
		expect(dirty(opened, opened)).toBe(false);
		expect(dirty(opened, { ...opened, layout: "" })).toBe(true);
	});

	it("ignores markers and key order when it compares", () => {
		const marked = { ...opened, rail: opened.rail.map((r) => ({ ...r, hidden_by: "site" as const })) };
		const reordered = { ...opened, rail: opened.rail.map((r) => ({ link_to: r.link_to, item_type: r.item_type, key: r.key })) };
		expect(dirty(opened, marked)).toBe(false);
		expect(dirty(opened, reordered)).toBe(false);
	});

	it("sends only the containers that changed, without markers", () => {
		const next = update(opened, "side", "u", { label: "Mine" }) as typeof opened;
		expect(toPayload(opened, next)).toEqual({
			sidebars: { side: [...opened.sidebars.side.slice(0, 2), { ...row("u"), label: "Mine" }] },
		});
		const hidden = toggleHidden(opened, RAIL, "a") as typeof opened;
		expect(Object.keys(toPayload(opened, hidden))).toEqual(["rail"]);
		expect(toPayload(opened, revert(opened))).toEqual({});
	});

	it("resets to the level below and clears own sidebars", () => {
		const below = { rail: [row("a")], sidebars: {} };
		const reset = resetToDefault({ ...opened, rail: [row("a"), row("user:x")] }, below);
		expect(reset).toEqual({ rail: [row("a")], sidebars: {}, layout: "" });
	});

	it("reads origin from the key", () => {
		expect([originOf("user:abc"), originOf("site:abc"), originOf("crm-deals")]).toEqual(["user", "site", "app"]);
	});
});

describe("the Sidebar tab rule", () => {
	const sidebars = { side: [row("s")], orphan: [row("o")], mine: [row("m")] };

	it("offers only the sidebars a rail row opens", () => {
		const draft = fromArrangements(
			response([row("a", { item_type: "Sidebar", link_to: "side" }), row("b", { opens_sidebar: "mine" })], sidebars),
			"user"
		);
		expect(openedSidebars(draft)).toEqual(["side", "mine"]);
	});

	it("offers none when no rail row opens one, so the tab is gone", () => {
		const draft = fromArrangements(response([row("a")], sidebars), "user");
		expect(openedSidebars(draft)).toEqual([]);
	});

	it("follows the draft: a row given a sidebar adds the tab, hiding the opener does not remove it", () => {
		const draft = fromArrangements(response([row("a", { item_type: "Sidebar", link_to: "side", hidden: 1 })], sidebars), "user");
		expect(openedSidebars(draft)).toEqual(["side"]);
	});
});

describe("the edits", () => {
	it("gives an inherited row only its label, icon and sidebar", () => {
		const next = update(opened, RAIL, "a", { label: "A", link_to: "other", icon: "star" }) as typeof opened;
		expect(next.rail[0]).toEqual({ ...row("a"), label: "A", icon: "star" });
	});

	it("gives an own row every field, and a blank label drops the field", () => {
		const own = { ...opened, rail: [row("user:q", { label: "Q" })] };
		const next = update(own, RAIL, "user:q", { link_to: "x", label: "" }) as typeof opened;
		expect(next.rail[0]).toEqual({ ...row("user:q"), link_to: "x" });
	});

	it("hides and shows, including a row the site hid", () => {
		const siteHid = { ...opened, rail: [row("a", { hidden: 1, hidden_by: "site" })] };
		const shown = toggleHidden(siteHid, RAIL, "a") as typeof opened;
		expect(shown.rail[0].hidden).toBeUndefined();
		expect((toggleHidden(shown, RAIL, "a") as typeof opened).rail[0].hidden).toBe(1);
	});

	it("moves among siblings with the children in tow, and stops at the end", () => {
		expect(moveAmongSiblings(opened, RAIL, "a", -1)).toBe(opened);
		const next = moveAmongSiblings(opened, RAIL, "a", 1);
		expect(next.rail.map((r) => r.key)).toEqual(["b", "a", "c"]);
		const down = moveAmongSiblings(opened, "side", "s", 1);
		expect(down.sidebars.side.map((r) => r.key)).toEqual(["u", "s", "t"]);
	});

	it("moves past hidden siblings unless they are on show", () => {
		const hid = { ...opened, rail: [row("a"), row("h", { hidden: 1 }), row("b"), row("c")] };
		expect(moveAmongSiblings(hid, RAIL, "a", 1, false).rail.map((r) => r.key)).toEqual(["h", "b", "a", "c"]);
		expect(moveAmongSiblings(hid, RAIL, "b", -1, false).rail.map((r) => r.key)).toEqual(["b", "a", "h", "c"]);
		expect(moveAmongSiblings(hid, RAIL, "a", 1, true).rail.map((r) => r.key)).toEqual(["h", "a", "b", "c"]);
		// Only hidden rows ahead: nothing visible to pass, so it stays.
		const tail = { ...opened, rail: [row("a"), row("h", { hidden: 1 })] };
		expect(moveAmongSiblings(tail, RAIL, "a", 1, false)).toBe(tail);
	});

	it("drops before a row, under that row's parent", () => {
		const next = dropBefore(opened, "side", "u", "t") as typeof opened;
		expect(next.sidebars.side.map((r) => [r.key, r.parent_key])).toEqual([
			["s", undefined],
			["u", "s"],
			["t", "s"],
		]);
	});

	it("refuses a nest through canNestUnder, in the rail and under an item", () => {
		expect(refused(nest(opened, RAIL, "b", "a"))).toBe(true);
		const deep = { ...opened, sidebars: { side: [row("p"), row("q", { parent_key: "p" }), row("r")] } };
		expect(refused(nest(deep, "side", "r", "q"))).toBe(true);
		expect(refused(nest(deep, "side", "p", "r"))).toBe(true);
		expect(refused(nest(deep, "side", "r", "p"))).toBe(false);
	});

	it("places a nested row last under its parent, wherever it was", () => {
		const flat = { ...opened, sidebars: { side: [row("a"), row("b"), row("c")] } };
		const next = nest(flat, "side", "c", "a") as typeof opened;
		expect(next.sidebars.side.map((r) => [r.key, r.parent_key])).toEqual([
			["a", undefined],
			["c", "a"],
			["b", undefined],
		]);
		expect(nest(flat, "side", "b", null)).toBe(flat);
	});

	it("refuses a row under its own child", () => {
		expect(refused(nest(opened, "side", "s", "t"))).toBe(true);
	});

	it("nests under a section and lifts back to the top level", () => {
		const under = nest(opened, "side", "u", "s") as typeof opened;
		expect(under.sidebars.side.find((r) => r.key === "u")?.parent_key).toBe("s");
		const top = nest(under, "side", "u", null) as typeof opened;
		expect(top.sidebars.side.find((r) => r.key === "u")?.parent_key).toBeUndefined();
	});
});
