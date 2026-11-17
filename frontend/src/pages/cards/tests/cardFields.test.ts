// The fields a card reads: the view's settings when they name a readable field, else the doctype's own pick.
import { describe, expect, it } from "vitest";
import { cardFields } from "../cardFields";

const meta = {
	title_field: "subject",
	fields: [
		{ fieldname: "subject", fieldtype: "Data" },
		{ fieldname: "summary", fieldtype: "Small Text" },
		{ fieldname: "content", fieldtype: "Text Editor" },
		{ fieldname: "cover", fieldtype: "Attach Image" },
		{ fieldname: "photo", fieldtype: "Attach Image" },
		{ fieldname: "file", fieldtype: "Attach" },
	],
};

describe("cardFields", () => {
	it("defaults the title to the doctype's title field and the body to its first text field", () => {
		expect(cardFields(meta, {})).toEqual({ title: "subject", body: "summary", bodyIsHtml: false, image: null });
	});

	it("falls back to the name and no body for a doctype with neither", () => {
		const bare = { fields: [{ fieldname: "status", fieldtype: "Select" }] };
		expect(cardFields(bare, {})).toEqual({ title: "name", body: null, bodyIsHtml: false, image: null });
	});

	it("takes the settings, and marks a Text Editor body as HTML", () => {
		expect(cardFields(meta, { title_field: "name", body_field: "content" })).toEqual({
			title: "name",
			body: "content",
			bodyIsHtml: true,
			image: null,
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

	describe("image", () => {
		it("defaults to the doctype's image field", () => {
			expect(cardFields({ ...meta, image_field: "cover" }, {}).image).toBe("cover");
		});

		it("takes the setting over the doctype's, and none for an empty one", () => {
			const withImage = { ...meta, image_field: "cover" };
			expect(cardFields(withImage, { image_field: "photo" }).image).toBe("photo");
			expect(cardFields(withImage, { image_field: "" }).image).toBeNull();
		});

		it("shows no image when nothing names one", () => {
			expect(cardFields(meta, {}).image).toBeNull();
		});

		it("ignores a setting that is gone, unreadable or not an Attach Image field", () => {
			const readable = (fieldname: string) => fieldname !== "photo";
			const withImage = { ...meta, image_field: "cover" };
			expect(cardFields(withImage, { image_field: "gone" }).image).toBe("cover");
			expect(cardFields(withImage, { image_field: "file" }).image).toBe("cover");
			expect(cardFields(withImage, { image_field: "photo" }, readable).image).toBe("cover");
			expect(cardFields(meta, { image_field: "summary" }).image).toBeNull();
		});
	});
});
