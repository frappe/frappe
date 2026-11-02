// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE

import assert from "node:assert/strict";
import { test } from "node:test";

// Load the real translation and search implementations; only Desk boot data and
// the jQuery formatting boundary are supplied by this site-free unit fixture.
globalThis.window = globalThis;
globalThis.$ = {
	format: (text, values) => text.replace(/\{(\d+)\}/g, (_, index) => values[index]),
};
globalThis.frappe = {
	provide: () => {},
	search: {},
	model: { can_get_report: () => true },
	utils: { escape_html: (text) => text },
};
await import("../public/js/frappe/translate.js");
await import("../public/js/frappe/ui/toolbar/search_utils.js");

for (const [type, tree, single, translated, expected] of [
	["List", false, false, true, "Restaurant Table List"],
	["Tree", true, false, true, "Restaurant Table Tree"],
	["Report", false, false, true, "Restaurant Table Report"],
	["", false, true, true, "Restaurant Table "],
	["List", false, false, false, "Example Table List"],
]) {
	test(`doctype value: ${type || "Single"}, translated=${translated}`, () => {
		frappe._messages = translated ? { "Example Table": "Restaurant Table" } : {};
		frappe.boot = {
			user: { can_read: ["Example Table"], can_search: ["Example Table"], can_create: [] },
			single_types: single ? ["Example Table"] : [],
			tree_view_doctypes: tree ? ["Example Table"] : [],
		};
		const result = frappe.search.utils.get_doctypes(translated ? "restaurant" : "example")
			.find((item) => item.type === type);
		assert.ok(result, "translated labels must remain searchable");
		assert.equal(result.value, expected);
		assert.equal(result.match, "Example Table");
		assert.deepEqual(result.route, single ? ["Form", "Example Table", "Example Table"] :
			type === "Report" ? ["List", "Example Table", "Report"] : [type, "Example Table"]);
	});
}
