import { describe, expect, it } from "vitest";
import { allowedFieldtypes, fieldnameFromLabel, guessFieldtype, validFieldname } from "../fieldRules";

describe("fieldnameFromLabel", () => {
	it("scrubs the label and drops what a fieldname refuses", () => {
		expect(fieldnameFromLabel("Due Date")).toBe("due_date");
		expect(fieldnameFromLabel("Follow-up (days)?")).toBe("follow_up_days");
		expect(fieldnameFromLabel("Größe")).toBe("größe");
	});
});

describe("validFieldname", () => {
	it("takes lowercase letters, digits and underscores", () => {
		expect(validFieldname("due_date_2")).toBe(true);
		expect(validFieldname("Due")).toBe(false);
		expect(validFieldname("due-date")).toBe(false);
		expect(validFieldname("due date")).toBe(false);
		expect(validFieldname("")).toBe(false);
	});
});

describe("allowedFieldtypes", () => {
	const field = { fieldname: "notes", fieldtype: "Small Text" };

	it("lets a field not yet saved take any type", () => {
		expect(allowedFieldtypes(field, false, 0)).toBe("any");
	});

	it("lets a saved field with no values take any type", () => {
		expect(allowedFieldtypes(field, true, 0)).toBe("any");
	});

	it("keeps a saved field with values to the types that keep them", () => {
		expect(allowedFieldtypes(field, true, 13)).toEqual(["Data", "Long Text", "Text"]);
		expect(allowedFieldtypes({ fieldname: "total", fieldtype: "Currency" }, true, 2)).toEqual(["Float", "Percent"]);
	});

	it("keeps a type no group names to itself", () => {
		expect(allowedFieldtypes({ fieldname: "due", fieldtype: "Date" }, true, 4)).toEqual([]);
	});
});

describe("guessFieldtype", () => {
	it("guesses from the words of the label", () => {
		expect(guessFieldtype("Due date")).toEqual({ fieldtype: "Date", because: "date" });
		expect(guessFieldtype("Work Email")).toEqual({ fieldtype: "Data", options: "Email", because: "Email" });
		expect(guessFieldtype("Mobile")).toEqual({ fieldtype: "Phone", because: "Mobile" });
		expect(guessFieldtype("Total amount")).toEqual({ fieldtype: "Currency", because: "amount" });
		expect(guessFieldtype("Is active")).toEqual({ fieldtype: "Check", because: "Is" });
		expect(guessFieldtype("Notes")).toEqual({ fieldtype: "Text Editor", because: "Notes" });
	});

	it("links to a DocType the label names", () => {
		expect(guessFieldtype("customer", ["Customer", "Item"])).toEqual({
			fieldtype: "Link",
			options: "Customer",
			because: "Customer",
		});
	});

	it("falls back to Data", () => {
		expect(guessFieldtype("Subject")).toEqual({ fieldtype: "Data", because: "" });
		expect(guessFieldtype("  ")).toEqual({ fieldtype: "Data", because: "" });
	});
});
