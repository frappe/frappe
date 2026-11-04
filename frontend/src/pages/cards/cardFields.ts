// What a card shows from a doctype and the view's settings: the title and body fields it reads.
import type { ListMeta } from "@/list/defaults";
import type { ViewSettings } from "@/list/view";

export const BODY_FIELDTYPES = new Set(["Text Editor", "Text", "Small Text", "Long Text"]);

export interface CardFields {
	title: string;
	/** Null when the doctype has no text field and none is set. */
	body: string | null;
	/** True for a Text Editor body, which holds HTML; the others hold plain text. */
	bodyIsHtml: boolean;
}

/** The setting when it names a field the person can read, else the doctype's own pick. */
export function cardFields(
	meta: ListMeta,
	settings: ViewSettings,
	readable: (fieldname: string) => boolean = () => true
): CardFields {
	const fields = meta.fields ?? [];
	const has = (fieldname: unknown): fieldname is string =>
		typeof fieldname === "string" && readable(fieldname) && fields.some((one) => one.fieldname === fieldname);

	const titleSetting = settings.title_field;
	const title =
		titleSetting === "name" || has(titleSetting)
			? (titleSetting as string)
			: meta.title_field && readable(meta.title_field)
				? meta.title_field
				: "name";

	const firstText = fields.find((one) => BODY_FIELDTYPES.has(one.fieldtype) && readable(one.fieldname));
	// An empty setting is the person's choice of no body, not an unset one.
	const body = settings.body_field === "" ? null : has(settings.body_field) ? settings.body_field : (firstText?.fieldname ?? null);
	const bodyIsHtml = fields.find((one) => one.fieldname === body)?.fieldtype === "Text Editor";
	return { title, body, bodyIsHtml };
}
