// The fields a card reads: the view's settings when they name a readable field, else the doctype's own pick.
import { describe, expect, it } from "vitest";
import { cardFields } from "../cardFields";

const meta = {
	title_field: "subject",
	fields: [
		{ fieldname: "subject", fieldtype: "Data" },
		{ fieldname: "summary", fieldtype: "Small Text" },
		{ fieldname: "content", fieldtype: "Text Editor" },
	],
};

describe("cardFields", () => {
	it("defaults the title to the doctype's title field and the body to its first text field", () => {
		expect(cardFields(meta, {})).toEqual({ title: "subject", body: "summary", bodyIsHtml: false });
	});

	it("falls back to the name and no body for a doctype with neither", () => {
		const bare = { fields: [{ fieldname: "status", fieldtype: "Select" }] };
		expect(cardFields(bare, {})).toEqual({ title: "name", body: null, bodyIsHtml: false });
	});

	it("takes the settings, and marks a Text Editor body as HTML", () => {
		expect(cardFields(meta, { title_field: "name", body_field: "content" })).toEqual({
			title: "name",
			body: "content",
			bodyIsHtml: true,
		});
	});

	it("shows no body when the setting is empty", () => {
		expect(cardFields(meta, { body_field: "" }).body).toBeNull();
	});

	it("ignores a setting for a field that is gone or unreadable", () => {
		const readable = (fieldname: string) => fieldname !== "content";
		expect(cardFields(meta, { title_field: "gone", body_field: "content" }, readable)).toMatchObject({
			title: "subject",
			body: "summary",
		});
	});
});
