// A generated block's layout as settings rows: the block's field list, or the doctype's tabs and
// sections in one column, without the fields the pane may not draw and with its read-only marks.
import { buildLayoutFromMeta, layoutFields } from "@framework/ui/FormLayout";
import type { FieldNode, FormLayoutSchema, RawMetaField } from "@framework/ui/FormLayout/types";
import type { SettingsBlock } from "@/shell/settingsPanes";

const NOT_DRAWN = new Set(["HTML", "Button", "Heading"]);

/** Fields whose control sits under the row's title, not beside it. */
const LONG = new Set([
	"Small Text",
	"Text",
	"Long Text",
	"Text Editor",
	"Code",
	"JSON",
	"Markdown Editor",
	"HTML Editor",
	"Table",
	"Table MultiSelect",
	"Attach",
	"Attach Image",
	"Signature",
	"Geolocation",
]);

export function isLong(field: FieldNode): boolean {
	return LONG.has(field.fieldtype);
}

export function blockLayout(
	block: SettingsBlock,
	meta: RawMetaField[],
	childMetas: Record<string, RawMetaField[]>
): FormLayoutSchema {
	const built = buildLayoutFromMeta(meta, { childMetas });
	const readOnly = new Set(block.read_only_fields);
	const marked = (field: FieldNode) =>
		block.read_only || readOnly.has(field.fieldname) ? { ...field, readOnly: true } : field;
	if (block.fields?.length) {
		const byName = new Map(layoutFields(built).map((field) => [field.fieldname, field]));
		const fields = block.fields
			.map((fieldname) => byName.get(fieldname))
			.filter((field): field is FieldNode => !!field)
			.map(marked);
		return [{ name: block.key, sections: [{ name: block.key, columns: [{ fields }] }] }];
	}
	const leftOut = new Set(block.left_out_fields);
	const drawn = (field: FieldNode) =>
		!NOT_DRAWN.has(field.fieldtype) && !leftOut.has(field.fieldname);
	return built
		.map((tab) => ({
			...tab,
			sections: tab.sections
				.map((section) => ({
					...section,
					columns: [
						{
							fields: section.columns
								.flatMap((column) => column.fields)
								.filter(drawn)
								.map(marked),
						},
					],
				}))
				.filter((section) => section.columns[0].fields.length),
		}))
		.filter((tab) => tab.sections.length);
}
