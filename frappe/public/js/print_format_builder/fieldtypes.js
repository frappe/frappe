const IMAGE_FIELDTYPES = new Set(["Attach Image", "Image", "Attach"]);
const MERGE_IMAGE_FIELDTYPES = new Set(["Attach Image", "Attach"]);
export const HTML_CONTENT_FIELDTYPES = new Set(["Text Editor", "Long Text"]);
const MERGE_HTML_FIELDTYPES = new Set(["Text Editor", "HTML Editor"]);
const BLOCK_FIELDTYPES = new Set(["Spacer", "Divider", "Repeater", "HTML"]);
const CONTENT_FIELDTYPES = new Set([
	"HTML",
	"Divider",
	"Spacer",
	"Field Template",
	"Image",
	"Barcode",
]);
const NON_TEXT_FIELDTYPES = new Set([
	...CONTENT_FIELDTYPES,
	"Static Text",
	"Typst",
	"Table",
	"Repeater",
]);
const BREAKABLE_FIELDTYPES = new Set([
	"Text Editor",
	"Text",
	"Long Text",
	"Small Text",
	"Code",
	"HTML Editor",
]);
const UNALIGNED_FIELDTYPES = new Set(["HTML", "Typst", "Spacer", "Divider", "Table", "Repeater"]);

export const is_image = (df) => IMAGE_FIELDTYPES.has(df?.fieldtype);
export const is_text = (df) => !NON_TEXT_FIELDTYPES.has(df?.fieldtype);
export const is_block = (df) => BLOCK_FIELDTYPES.has(df?.fieldtype);
export const is_breakable = (df) => BREAKABLE_FIELDTYPES.has(df?.fieldtype);
export const is_merge_image = (df) => MERGE_IMAGE_FIELDTYPES.has(df?.fieldtype);
export const is_merge_html = (df) => MERGE_HTML_FIELDTYPES.has(df?.fieldtype);
export const has_align = (df) => !UNALIGNED_FIELDTYPES.has(df?.fieldtype);
export const always_has_content = (df) => CONTENT_FIELDTYPES.has(df?.fieldtype);
