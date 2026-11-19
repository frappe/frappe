// What a field may be called and typed as, by the server's rules.
import type { RawMetaField } from "@framework/ui/FormLayout/types";

export const LAYOUT_BREAKS = ["Section Break", "Column Break", "Tab Break"];

/** `SPECIAL_CHAR_PATTERN` in `frappe/database/schema.py`: Python's `\W`. */
const SPECIAL_CHAR = /[^\p{L}\p{N}_]/u;

/** `frappe.scrub(label)` without the characters a fieldname refuses. */
export function fieldnameFromLabel(label: string): string {
	return label
		.replaceAll(" ", "_")
		.replaceAll("-", "_")
		.toLowerCase()
		.replace(new RegExp(SPECIAL_CHAR, "gu"), "");
}

export function validFieldname(fieldname: string): boolean {
	return Boolean(fieldname) && fieldname === fieldname.toLowerCase() && !SPECIAL_CHAR.test(fieldname);
}

// Customize Form's `ALLOWED_FIELDTYPE_CHANGE`: the type changes that keep a column's values.
const ALLOWED_FIELDTYPE_CHANGE = [
	["Currency", "Float", "Percent"],
	["Small Text", "Data"],
	["Text", "Data"],
	["Text", "Text Editor", "Code", "Signature", "HTML Editor"],
	["Data", "Select"],
	["Text", "Small Text", "Long Text"],
	["Text", "Data", "Barcode"],
	["Code", "Geolocation"],
	["Table", "Table MultiSelect"],
];

/** The types a field may become: any, until its column holds a value; then only those that keep it. */
export function allowedFieldtypes(
	field: RawMetaField,
	saved: boolean,
	valueCount: number,
): "any" | string[] {
	if (!saved || !valueCount) return "any";
	const keeping = ALLOWED_FIELDTYPE_CHANGE.filter((group) => group.includes(field.fieldtype)).flat();
	return [...new Set(keeping)].filter((fieldtype) => fieldtype !== field.fieldtype).sort();
}

export interface FieldtypeGuess {
	fieldtype: string;
	/** The Link's DocType, or Data's `Email`. */
	options?: string;
	/** The words of the label that made the guess; empty for the Data default. */
	because: string;
}

const GUESSES: { test: RegExp; fieldtype: string; options?: string }[] = [
	{ test: /\be-?mail\b/i, fieldtype: "Data", options: "Email" },
	{ test: /\b(phone|mobile)\b/i, fieldtype: "Phone" },
	{ test: /\bdate\b|\S\s+on$/i, fieldtype: "Date" },
	{ test: /\b(amount|price|cost)\b/i, fieldtype: "Currency" },
	{ test: /^(is|has)\b/i, fieldtype: "Check" },
	{ test: /\b(notes?|description)\b/i, fieldtype: "Text Editor" },
];

/** The type "Add field" offers for a label; a label that names a DocType links to it. */
export function guessFieldtype(label: string, doctypes: readonly string[] = []): FieldtypeGuess {
	const typed = label.trim();
	if (!typed) return { fieldtype: "Data", because: "" };
	const target = doctypes.find((doctype) => doctype.toLowerCase() === typed.toLowerCase());
	if (target) return { fieldtype: "Link", options: target, because: target };
	for (const guess of GUESSES) {
		const match = typed.match(guess.test);
		if (!match) continue;
		const options = guess.options ? { options: guess.options } : {};
		return { fieldtype: guess.fieldtype, ...options, because: match[0].trim() };
	}
	return { fieldtype: "Data", because: "" };
}
