// Which field the picture lives in, and when an upload there would be thrown away.
import { describe, expect, it } from "vitest";
import { imageFieldOf, initialsOf } from "../imageField";

const meta = (fields: Record<string, any>[], image_field = "image") => ({
	image_field,
	fields,
});

describe("imageFieldOf", () => {
	it("is nothing for a doctype that names no image field", () => {
		expect(imageFieldOf({ fields: [] })).toBeNull();
		expect(imageFieldOf(null)).toBeNull();
	});

	it("is editable for a plain field, even one the meta does not list", () => {
		expect(imageFieldOf(meta([{ fieldname: "image", fieldtype: "Attach Image" }]))).toEqual({
			fieldname: "image",
			editable: true,
			reason: "",
			source: null,
			permlevel: 0,
		});
		expect(imageFieldOf(meta([]))?.editable).toBe(true);
	});

	it("refuses a read-only field", () => {
		const field = imageFieldOf(meta([{ fieldname: "image", read_only: 1 }]));
		expect(field?.editable).toBe(false);
		expect(field?.reason).toBe("This image is read-only");
	});

	it("refuses a hidden field, and carries the permlevel for the reader's access", () => {
		const field = imageFieldOf(meta([{ fieldname: "image", hidden: 1, permlevel: 2 }]));
		expect(field?.editable).toBe(false);
		expect(field?.reason).toBe("This image is hidden");
		expect(field?.permlevel).toBe(2);
	});

	it("names the linked record a fetched image comes from", () => {
		const fields = [
			{ fieldname: "image", fetch_from: "contact.image" },
			{ fieldname: "contact", fieldtype: "Link", options: "Contact", label: "Contact" },
		];
		const titled = imageFieldOf(meta(fields), { contact: "CONT-1" }, (_, name) => `Ann (${name})`);
		expect(titled).toEqual({
			fieldname: "image",
			editable: false,
			reason: "This image comes from Ann (CONT-1), open it to change",
			source: { doctype: "Contact", name: "CONT-1" },
			permlevel: 0,
		});

		const unlinked = imageFieldOf(meta(fields), {});
		expect(unlinked?.source).toBeNull();
		expect(unlinked?.reason).toBe("This image is fetched from the record linked in Contact");
	});

	it("lets a fetch that fills only an empty field be replaced", () => {
		const fields = [
			{ fieldname: "image", fetch_from: "contact.image", fetch_if_empty: 1 },
			{ fieldname: "contact", fieldtype: "Link", options: "Contact" },
		];
		expect(imageFieldOf(meta(fields), { contact: "CONT-1" })?.editable).toBe(true);
	});
});

describe("initialsOf", () => {
	it("takes the first letter of the first two words", () => {
		expect(initialsOf("Ann  Example")).toBe("AE");
		expect(initialsOf("Ann Marie Example")).toBe("AM");
		expect(initialsOf("  ")).toBe("");
	});
});
