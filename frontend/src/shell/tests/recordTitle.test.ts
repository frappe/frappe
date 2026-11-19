// A record's title: the title field as text without its markup, else the name.
import { describe, expect, it } from "vitest";
import { recordTitle } from "@/recordTitle";

const meta = {
	title_field: "description",
	fields: [
		{ fieldname: "description", fieldtype: "Text Editor" },
		{ fieldname: "subject", fieldtype: "Data" },
	],
};

describe("recordTitle", () => {
	it("draws a Text Editor title as plain text", () => {
		const doc = { description: "<p>Call <strong>Ann</strong></p><p>today &amp; tomorrow</p>" };
		expect(recordTitle(meta, doc, "gmicfv0aqn")).toBe("Call Ann today & tomorrow");
	});

	it("keeps a Data title as typed", () => {
		const doc = { subject: "Q3 <Q4 plan &amp; budget" };
		expect(recordTitle({ ...meta, title_field: "subject" }, doc, "gmicfv0aqn")).toBe(
			"Q3 <Q4 plan &amp; budget"
		);
	});

	it("reads the field the caller names", () => {
		const doc = { subject: "Call Ann", description: "<p>Notes</p>" };
		expect(recordTitle(meta, doc, "gmicfv0aqn", "subject")).toBe("Call Ann");
	});

	it("falls back to the name when the title has no text or the doctype has no title field", () => {
		expect(recordTitle(meta, { description: "<p><br></p>" }, "gmicfv0aqn")).toBe("gmicfv0aqn");
		expect(recordTitle(null, { description: "Call Ann" }, "gmicfv0aqn")).toBe("gmicfv0aqn");
	});
});
