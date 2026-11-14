import { beforeEach, describe, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => ({ listed: vi.fn(), find: vi.fn() }));

vi.mock("@/acts/dispatcher", () => ({ acts: { listed: fake.listed, find: fake.find } }));

import { addTypes, addable, buildRow, missing, startValues } from "../addTypes";
import { actRow, hasNoPageToOpen, keyOf, optionRefusal, pickableActs } from "../actPicker";
import { RAIL } from "../draft";
import type { EditorRow } from "../draft";
import { canGiveSidebar } from "../edits";

const theme = { name: "shell.theme", label: "Theme", icon: "lucide-sun-moon", argument: { label: "Theme" } };
const create = { name: "shell.create", label: "Create" };

beforeEach(() => {
	fake.listed.mockReturnValue([theme, create, { name: "list.create", label: "New" }]);
	fake.find.mockImplementation((name: string) => [theme, create].find((act) => act.name === name));
});

describe("the Act step", () => {
	it("lists the palette's acts that are a shell act or an app's, by label", () => {
		expect(pickableActs().map((act) => act.name)).toEqual(["shell.create", "shell.theme"]);
	});

	it("is a type of both the rail and a sidebar, and a row of it is addable", () => {
		expect(addTypes(RAIL).some((entry) => entry.type === "Act")).toBe(true);
		expect(addTypes("sidebar:a").some((entry) => entry.type === "Act")).toBe(true);
		expect(addable("Act")).toBe(true);
	});

	it("writes a preset row's payload, label and the option's icon", () => {
		const option = { value: "dark", label: "Dark", icon: "lucide-moon" };
		expect(actRow(theme as never, option)).toEqual({
			item_type: "Act",
			payload: { act: "shell.theme", value: "dark" },
			label: "Theme: Dark",
			icon: "lucide-moon",
		});
	});

	it("falls back to the act's icon, and writes no value for Ask on click", () => {
		expect(actRow(theme as never, { value: "dark", label: "Dark" }).icon).toBe("lucide-sun-moon");
		expect(actRow(theme as never)).toEqual({
			item_type: "Act",
			payload: { act: "shell.theme" },
			label: "Theme",
			icon: "lucide-sun-moon",
		});
		expect(actRow(create as never)).not.toHaveProperty("icon");
	});

	it("asks for an act, and for a value when Preset is chosen", () => {
		expect(missing("Act", startValues())?.field).toBe("act");
		const picked = { ...startValues(), act: "shell.theme", preset: true };
		expect(missing("Act", picked)?.field).toBe("option");
		expect(missing("Act", { ...picked, preset: false })).toBeNull();
	});

	it("builds the row from the form's values", () => {
		const values = {
			...startValues(),
			act: "shell.theme",
			preset: true,
			option: { value: "dark", label: "Dark" },
		};
		expect(buildRow("Act", values)).toMatchObject({ item_type: "Act", label: "Theme: Dark" });
	});
});

describe("an act name", () => {
	it("takes shell.<item> and shell.<app>.<item>, not a third segment, and fits the cap with its wrapper", () => {
		const names = [
			"shell.erpnext.stock",
			"shell.a.b.c",
			`shell.${"a".repeat(119)}`,
			`shell.${"a".repeat(100)}`,
		];
		fake.listed.mockReturnValue(names.map((name) => ({ name, label: name })));
		expect(pickableActs().map((act) => act.name)).toEqual([
			`shell.${"a".repeat(100)}`,
			"shell.erpnext.stock",
		]);
	});
});

describe("an option as a preset", () => {
	it("disables a Map, a Set and a class instance, which JSON turns into {}", () => {
		class Box {}
		for (const value of [new Map([[1, 2]]), new Set([1]), new Box()]) {
			expect(optionRefusal("shell.theme", { label: "x", value })).toBe("Can't be saved");
		}
	});

	it("keys an option by its label and value, so a re-asked list keeps the pick", () => {
		expect(keyOf({ label: "Dark", value: "dark" })).toBe(keyOf({ label: "Dark", value: "dark" }));
		expect(keyOf({ label: "Dark", value: "dark" })).not.toBe(keyOf({ label: "Dark", value: "light" }));
	});

	it("disables a value that does not survive JSON", () => {
		for (const value of [undefined, () => 1, NaN, { gone: undefined }, new Date(0)]) {
			expect(optionRefusal("shell.theme", { value, label: "X" })).toBe("Can't be saved");
		}
		expect(optionRefusal("shell.theme", { value: { a: [1, "b"] }, label: "X" })).toBeNull();
	});

	it("disables a payload over 128 bytes and takes one of exactly 128", () => {
		const act = "shell.theme";
		const room = 128 - JSON.stringify({ act, value: "" }).length;
		expect(optionRefusal(act, { value: "x".repeat(room), label: "X" })).toBeNull();
		expect(optionRefusal(act, { value: "x".repeat(room + 1), label: "X" })).toBe("Too long to save");
		// Bytes, not characters.
		expect(optionRefusal(act, { value: "é".repeat(Math.floor(room / 2) + 1), label: "X" })).toBe(
			"Too long to save"
		);
	});
});

describe("a sidebar of acts", () => {
	const act = { key: "user:a", item_type: "Act" } as EditorRow;
	const link = { key: "user:l", item_type: "Link" } as EditorRow;
	const section = { key: "user:s", item_type: "Section" } as EditorRow;

	it("has no page to open when its drawn rows are acts alone", () => {
		expect(hasNoPageToOpen([act, section])).toBe(true);
		expect(hasNoPageToOpen([act, link])).toBe(false);
		expect(hasNoPageToOpen([])).toBe(false);
	});

	it("does not count a hidden row or a row with no access", () => {
		expect(hasNoPageToOpen([act, { ...link, hidden: 1 } as EditorRow])).toBe(true);
		expect(hasNoPageToOpen([{ ...act, hidden: 1 } as EditorRow])).toBe(false);
	});

	it("is not offered a sidebar of its own", () => {
		const draft = { rail: [act], sidebars: {}, layout: "", scope: "user" } as never;
		expect(canGiveSidebar(draft, act)).toBe(false);
		expect(canGiveSidebar(draft, link)).toBe(true);
	});
});
