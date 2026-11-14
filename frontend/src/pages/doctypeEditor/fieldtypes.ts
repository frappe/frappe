// The data fieldtypes the field panel offers, grouped, with an icon each.
export const FIELDTYPE_GROUPS: { label: string; types: string[] }[] = [
	{
		label: "Text",
		types: [
			"Data",
			"Small Text",
			"Text",
			"Long Text",
			"Text Editor",
			"Markdown Editor",
			"HTML Editor",
			"Code",
			"Password",
			"Phone",
		],
	},
	{ label: "Number", types: ["Int", "Float", "Currency", "Percent", "Rating", "Duration"] },
	{ label: "Choice", types: ["Check", "Select", "Autocomplete", "Color"] },
	{ label: "Date and time", types: ["Date", "Datetime", "Time"] },
	{ label: "Links", types: ["Link", "Dynamic Link", "Table"] },
	{
		label: "Files and other",
		types: ["Attach", "Attach Image", "Signature", "Geolocation", "JSON", "Read Only", "HTML", "Barcode"],
	},
];

/** The types the menu lists first; "Email" is Data with the `Email` option, as the record page draws it. */
export const COMMON_TYPES = [
	"Data",
	"Email",
	"Phone",
	"Int",
	"Currency",
	"Date",
	"Datetime",
	"Check",
	"Select",
	"Link",
	"Small Text",
	"Text Editor",
	"Attach",
];

const ICONS: Record<string, string> = {
	Data: "lucide-type",
	Email: "lucide-mail",
	"Small Text": "lucide-text",
	Text: "lucide-text",
	"Long Text": "lucide-text",
	"Text Editor": "lucide-pilcrow",
	"Markdown Editor": "lucide-pilcrow",
	"HTML Editor": "lucide-file-code",
	Code: "lucide-code",
	Password: "lucide-key-round",
	Phone: "lucide-phone",
	Int: "lucide-hash",
	Float: "lucide-hash",
	Currency: "lucide-banknote",
	Percent: "lucide-percent",
	Rating: "lucide-star",
	Duration: "lucide-timer",
	Check: "lucide-square-check",
	Select: "lucide-list",
	Autocomplete: "lucide-list",
	Color: "lucide-palette",
	Date: "lucide-calendar",
	Datetime: "lucide-calendar-clock",
	Time: "lucide-clock",
	Link: "lucide-link",
	"Dynamic Link": "lucide-link-2",
	Table: "lucide-table",
	"Table MultiSelect": "lucide-tags",
	Attach: "lucide-paperclip",
	"Attach Image": "lucide-image",
	Signature: "lucide-pen-line",
	Geolocation: "lucide-map-pin",
	JSON: "lucide-braces",
	"Read Only": "lucide-lock",
	HTML: "lucide-code-xml",
	Barcode: "lucide-barcode",
};

/** The name the menu shows a field's type by: "Email" for Data with the `Email` option. */
export function typeName(fieldtype: string, options?: string | null): string {
	return fieldtype === "Data" && options === "Email" ? "Email" : fieldtype;
}

export function typeIcon(name: string): string {
	return ICONS[name] ?? "lucide-type";
}

/** A menu name back to the field's type and options. */
export function typeOf(name: string): { fieldtype: string; options?: string } {
	return name === "Email" ? { fieldtype: "Data", options: "Email" } : { fieldtype: name };
}
