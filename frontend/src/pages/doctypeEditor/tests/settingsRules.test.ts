// The Settings tab's rules: which rows each kind shows, the naming rules and the permission rights.
import { describe, expect, it } from "vitest";
import { autonameOf, namingProperties, patternRefusal, ruleOf, ruleRefusal } from "../namingRules";
import { columns, moreRights, rightRefusal } from "../permissionColumns";
import type { PermissionRow, SettingsState } from "../settingsModel";
import { kindProperties, settingRows, settingSections, type DoctypeKind } from "../settingsRows";

function settings(overrides: Partial<SettingsState> = {}): SettingsState {
	return {
		properties: {},
		settable: null,
		permissions: [],
		pending: false,
		kindFixed: true,
		records: 3,
		savedAutoname: "hash",
		app: null,
		sitePermissions: false,
		permissionsRefusal: "",
		...overrides,
	};
}

const ofKind = (kind: DoctypeKind, pending = false) => settings({ properties: kindProperties(kind), pending, kindFixed: !pending });
const keys = (state: SettingsState) => settingRows(state).map((row) => row.key);
const sections = (state: SettingsState) => settingSections(state).map((section) => section.key);

describe("the rows each kind shows", () => {
	it("gives a child table no naming or permissions, only its rows and bulk edit, and a Single no naming", () => {
		expect(sections(ofKind("regular"))).toEqual(["naming", "form", "list", "permissions"]);
		expect(sections(ofKind("child"))).toEqual(["form", "list"]);
		expect(keys(ofKind("child"))).toContain("editable_grid");
		expect(keys(ofKind("child")).filter((key) => ["allow_import", "allow_bulk_edit"].includes(key))).toEqual(["allow_bulk_edit"]);
		expect(sections(ofKind("single"))).not.toContain("naming");
	});

	it("shows the kind row only before the first save", () => {
		expect(keys(ofKind("regular", true))).toContain("kind");
		expect(keys(ofKind("regular"))).not.toContain("kind");
	});

	it("hides the kind row on a new child table its parent made", () => {
		expect(keys(settings({ properties: kindProperties("child"), pending: true, kindFixed: true }))).not.toContain("kind");
	});
});

describe("the naming rules", () => {
	it("reads the rule from autoname and naming_rule", () => {
		expect(ruleOf({})).toBe("hash");
		expect(ruleOf({ autoname: "field:title" })).toBe("field");
		expect(ruleOf({ autoname: "naming_series:" })).toBe("naming_series");
		expect(ruleOf({ autoname: "format:WS-{#####}" })).toBe("format");
		expect(ruleOf({ autoname: "WS-.#####" })).toBe("format");
		expect(ruleOf({ autoname: "Prompt" })).toBe("prompt");
		expect(ruleOf({ autoname: "make_name", naming_rule: "By script" })).toBe("script");
	});

	it("refuses a typed pattern that would read as another rule", () => {
		expect(["WS-.#####", "format:WS-{#####}", "format:WS-#####"].map(patternRefusal)).toEqual(["", "", ""]);
		expect(["WS-#####", "hash", "Prompt"].every((pattern) => patternRefusal(pattern))).toBe(true);
	});

	it("names a braced pattern the old style expression, as v1 does", () => {
		expect(namingProperties("format:WS-{#####}")).toEqual({ autoname: "format:WS-{#####}", naming_rule: "Expression (old style)" });
		expect(namingProperties("WS-.#####").naming_rule).toBe("Expression");
		expect(autonameOf("By fieldname", "title")).toBe("field:title");
	});

	it("refuses Number in order while records exist, and Customize's switch to it", () => {
		expect(ruleRefusal(settings(), [], "autoincrement")).toBe("Only while there are no records: this DocType has 3.");
		expect(ruleRefusal(settings({ records: 0 }), [], "autoincrement")).toBe("");
		const app = { properties: {}, permissions: [] };
		expect(ruleRefusal(settings({ app }), [], "autoincrement")).toBe("Customize cannot switch to or from Number in order.");
	});

	it("refuses a naming series in Customize without the field, and any switch from a script", () => {
		const app = { properties: {}, permissions: [] };
		expect(ruleRefusal(settings({ app }), [], "naming_series")).toBe("Needs a Naming Series field. Add one in the Editor first.");
		expect(ruleRefusal(settings({ app }), [{ fieldname: "naming_series" }] as never, "naming_series")).toBe("");
		const scripted = settings({ properties: { naming_rule: "By script", autoname: "x" } });
		expect(ruleRefusal(scripted, [], "hash")).toBe("The app's code names each record. Change it there.");
	});
});

describe("the permission rights", () => {
	const row = (permlevel: number) => ({ role: "Writer", permlevel, if_owner: 0 }) as PermissionRow;

	it("gives a submittable DocType its submit columns, and a Single only read and write", () => {
		expect(columns("submittable")).toEqual(["read", "write", "create", "delete", "submit", "cancel", "amend"]);
		expect(columns("single")).toEqual(["read", "write"]);
		expect(moreRights("single")).not.toContain("import");
		expect(moreRights("regular")).toContain("import");
	});

	it("refuses create above level 0, and import while the DocType does not allow it", () => {
		expect(rightRefusal(row(1), "create", true)).toBe("A rule above level 0 only reads and writes its fields.");
		expect(rightRefusal(row(0), "create", true)).toBe("");
		expect(rightRefusal(row(0), "import", false)).toBe("Turn on Allow import in List and search first.");
	});
});
