// A record's title: the title field as plain text, else the name.
import { describe, expect, it } from "vitest";
import { recordTitle } from "@/recordTitle";

const meta = { title_field: "description" };

describe("recordTitle", () => {
	it("draws a Text Editor title as plain text", () => {
		const doc = { description: "<p>Call <strong>Ann</strong></p><p>today &amp; tomorrow</p>" };
		expect(recordTitle(meta, doc, "gmicfv0aqn")).toBe("Call Ann today & tomorrow");
	});

	it("falls back to the name when the title has no text or the doctype has no title field", () => {
		expect(recordTitle(meta, { description: "<p><br></p>" }, "gmicfv0aqn")).toBe("gmicfv0aqn");
		expect(recordTitle(null, { description: "Call Ann" }, "gmicfv0aqn")).toBe("gmicfv0aqn");
	});
});
