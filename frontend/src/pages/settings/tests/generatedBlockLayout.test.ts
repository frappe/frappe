// A generated block with no field list draws its Single's Details layout when a row applies,
// folded to one column, and the Single's breaks when none does.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetFormLayouts } from "@/recordPage";
import type { SettingsBlock } from "@/shell/settingsPanes";
import { PaneDrafts } from "../paneDrafts";
import { SettingsServer } from "./settingsServer";

const SYSTEM = { type: "Single" as const, doctype: "System Settings" };

function block(key: string, extra: Partial<SettingsBlock> = {}): SettingsBlock {
	return { key, app: "frappe", save_mode: "auto", binding: SYSTEM, ...extra };
}

async function opened(...blocks: SettingsBlock[]) {
	const drafts = new PaneDrafts({ app: "frappe", key: "system", label: "System", blocks }, "a@example.com", vi.fn());
	await drafts.loaded;
	return drafts;
}

function drawn(layout: FormLayoutSchema) {
	return layout.map((tab) => [
		tab.label ?? tab.name,
		tab.sections.map((section) => [
			section.label ?? section.name,
			section.columns.map((column) =>
				column.fields.map((field) => (field.readOnly ? `${field.fieldname} (read only)` : field.fieldname))
			),
		]),
	]);
}

const DETAILS_ROW = {
	name: "system-details",
	condition: null,
	omitted: [],
	layout: [
		{
			name: "general",
			label: "General",
			sections: [
				{ name: "region", label: "Region", columns: [{ fields: ["country"] }, { fields: ["time_zone"] }] },
			],
		},
		{ name: "brand", label: "Brand", sections: [{ name: "brand", label: "Branding", columns: [{ fields: ["app_name"] }] }] },
	],
};

let server: SettingsServer;

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	clearDataCache();
	server = new SettingsServer();
	vi.stubGlobal("fetch", server.fetch);
});

afterEach(() => vi.unstubAllGlobals());

describe("a generated block with no field list", () => {
	it("draws the Details row's tabs and sections in one column, with More fields as one more heading", async () => {
		server.layouts["System Settings"] = [DETAILS_ROW];
		const drafts = await opened(
			block("whole", { left_out_fields: ["enable_onboarding"], read_only_fields: ["app_name"] })
		);
		expect(drawn(drafts.bound.get("whole")!.layout.value)).toEqual([
			[
				"General",
				[
					["Region", [["country", "time_zone"]]],
					["More fields", [["rules"]]],
				],
			],
			["Brand", [["Branding", [["app_name (read only)"]]]]],
		]);
	});

	it("chooses a conditional row against the saved Single", async () => {
		server.layouts["System Settings"] = [
			{ ...DETAILS_ROW, name: "elsewhere", condition: "eval:doc.country == 'Spain'" },
			{ ...DETAILS_ROW, name: "france", condition: "eval:doc.country == 'France'", layout: [DETAILS_ROW.layout[1]] },
		];
		const drafts = await opened(block("whole"));
		const [tab] = drafts.bound.get("whole")!.layout.value;
		expect(tab.label).toBe("Brand");
	});

	it("draws the Single's breaks when no row applies", async () => {
		const drafts = await opened(block("whole", { left_out_fields: ["rules"] }));
		expect(drawn(drafts.bound.get("whole")!.layout.value)).toEqual([
			["first_tab", [[undefined, [["country", "enable_onboarding", "time_zone", "app_name"]]]]],
		]);
	});
});

describe("the layout read", () => {
	it("is one per Single, however many of its blocks draw it whole", async () => {
		await opened(block("one"), block("two"), block("listed", { fields: ["country"] }));
		expect(server.layoutReads).toEqual(["System Settings"]);
	});

	it("is not made for a block that lists its fields, which keeps the meta's fields", async () => {
		server.layouts["System Settings"] = [DETAILS_ROW];
		const drafts = await opened(block("listed", { fields: ["country", "enable_onboarding"] }));
		expect(server.layoutReads).toEqual([]);
		expect(drawn(drafts.bound.get("listed")!.layout.value)).toEqual([
			["listed", [["listed", [["country", "enable_onboarding"]]]]],
		]);
	});
});
