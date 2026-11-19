// Settings search: what it matches, how it ranks, and that it finds only what the reply carries.
import { describe, expect, it } from "vitest";
import type { Boot } from "@/boot";
import { SettingsAddressBook } from "../settingsAddress";
import type { PanesReply, SettingsPane } from "../settingsPanes";
import { SettingsSearch, type SettingsHit } from "../settingsSearch";
import { defaultSidebars } from "./fixtures/settingsSidebars";

function pane(app: string, key: string, label: string, description?: string): SettingsPane {
	return {
		app,
		key,
		label,
		description,
		icon: "settings",
		blocks: [{ key: "main", app, save_mode: "auto", label: `${label} details` }],
	};
}

const PANES = [
	pane("frappe", "profile", "Profile"),
	pane("frappe", "system", "System", "Dates, numbers and sessions"),
	pane("crm", "general", "General"),
	pane("helpdesk", "tickets", "Tickets"),
	pane("unprefixed", "hidden", "Hidden"),
];

const REPLY: PanesReply = {
	panes: PANES,
	sidebars: defaultSidebars(PANES, { frappe: "desk", crm: "crm", helpdesk: "helpdesk" }),
	index: [
		{ app: "frappe", pane: "system", block: "main", fieldname: "date_format", label: "Date Format" },
		{ app: "frappe", pane: "system", block: "main", fieldname: "time_zone", label: "Time Zone" },
		{
			app: "frappe",
			pane: "system",
			block: "main",
			fieldname: "session_expiry",
			label: "Session Expiry",
			description: "Format: hh:mm",
		},
		{ app: "frappe", pane: "system", block: "main", fieldname: "reformat", label: "Reformat On Save" },
		{ app: "frappe", pane: "system", block: "main", fieldname: "number_format", label: "Format Of Numbers" },
		{ app: "crm", pane: "general", block: "main", fieldname: "default_format", label: "Default Format" },
		{ app: "helpdesk", pane: "tickets", block: "main", fieldname: "ticket_format", label: "Ticket Format" },
		{ app: "frappe", pane: "profile", block: "main", label: "Theme", keywords: ["dark mode"] },
		{ app: "frappe", pane: "system", block: "main", fieldname: "smtp_port" },
		{ app: "frappe", pane: "profile", block: "main", keywords: ["dark"] },
		{ app: "unprefixed", pane: "hidden", block: "main", fieldname: "format", label: "Format" },
	],
	titles: { frappe: "Frappe", crm: "CRM", helpdesk: "Helpdesk", unprefixed: "Unprefixed" },
};

const BOOT = {
	app: "crm",
	prefixes: {
		desk: { app: "frappe", modular: false },
		crm: { app: "crm", modular: false },
		helpdesk: { app: "helpdesk", modular: false },
	},
} as unknown as Boot;

function find(query: string, reply = REPLY) {
	const results = new SettingsSearch(reply, new SettingsAddressBook(reply, BOOT)).find(query);
	const names = (hits: SettingsHit[]) => hits.map((hit) => hit.fieldname ?? hit.label);
	return { own: names(results.own), elsewhere: names(results.elsewhere), results };
}

describe("settings search", () => {
	it("finds nothing for an empty query", () => {
		expect(find("  ")).toMatchObject({ own: [], elsewhere: [] });
	});

	it("ranks a label that starts with the query, then a word in it, then anywhere, then its other text", () => {
		expect(find("format").own).toEqual([
			"number_format",
			"date_format",
			"default_format",
			"reformat",
			"session_expiry",
		]);
	});

	it("lists the framework's and the current app's results first, then those elsewhere with their app's title", () => {
		const { own, elsewhere, results } = find("format");
		expect(own).toContain("default_format");
		expect(elsewhere).toEqual(["ticket_format"]);
		expect(results.elsewhere[0]).toMatchObject({ prefix: "helpdesk", where: "Helpdesk › Tickets › Tickets details" });
		expect(results.own[0]).toMatchObject({ prefix: "desk", where: "System › System details" });
		expect(results.own[2]).toMatchObject({ prefix: "crm", where: "General › General details" });
	});

	it("matches pane labels and descriptions, block labels and a component's declared keywords", () => {
		expect(find("system").own).toEqual(["System", "System details"]);
		expect(find("sessions").results.own[0]).toMatchObject({ label: "System", where: "Frappe" });
		expect(find("dark").results.own).toEqual([expect.objectContaining({ label: "Theme", block: "main" })]);
		expect(find("smtp").results.own[0]).toMatchObject({ label: "smtp_port", fieldname: "smtp_port" });
	});

	it("finds only what the filtered reply carries, so never a field the server left out, nor an app with no prefix", () => {
		const filtered = { ...REPLY, index: REPLY.index.filter((entry) => entry.fieldname !== "time_zone") };
		expect(find("zone", filtered)).toMatchObject({ own: [], elsewhere: [] });
		expect(find("hidden")).toMatchObject({ own: [], elsewhere: [] });
	});
});

describe("search on an arranged sidebar", () => {
	// CRM's desk places Profile's block in General and hides System; Profile itself is out of the sidebar.
	const arranged: PanesReply = {
		...REPLY,
		sidebars: {
			...REPLY.sidebars,
			crm: { groups: [{ panes: [{ pane: "crm/general", blocks: ["crm/general/main", "desk/profile/main"] }] }] },
		},
	};

	it("lists a block with a place first, at its first place, and the rest under elsewhere", () => {
		const { results } = find("details", arranged);
		expect(results.own.map((hit) => [hit.label, hit.where])).toEqual([
			["General details", "General"],
			["Profile details", "General"],
		]);
		expect(results.elsewhere.map((hit) => [hit.label, hit.where, hit.home])).toEqual([
			["System details", "Frappe › System", true],
			["Tickets details", "Helpdesk › Tickets", true],
		]);
	});

	it("opens a hidden pane's hit from its home pane", () => {
		const { results } = find("system", arranged);
		expect(results.elsewhere[0]).toMatchObject({ prefix: "desk", pane: { key: "system" }, home: true });
	});
});
