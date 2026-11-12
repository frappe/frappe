// The tag writes. Apart from tagColors, which every list row imports, so the list page never loads the API.
import { runMethod, runPartMethod } from "@framework/ui/api";
import { seedTagColors } from "@/tagColors";

const SET_TAG_COLOR = "frappe.desk.doctype.tag.tag.set_tag_color";
const UPDATE_RECORD_TAGS = "frappe.desk.doctype.tag.tag.update_record_tags";

/** Saves a colour on the Tag itself and repaints every chip of it. */
export async function recolourTag(tag: string, color: string) {
	// set_tag_color returns nothing, so the reply has no `data`.
	await runMethod(SET_TAG_COLOR, { tag, color }, { nullable: true });
	seedTagColors({ [tag]: color });
}

/** Saves one picker session on a record in one call; answers the record's tags and their colours. */
export async function updateRecordTags(
	dt: string,
	dn: string,
	{ added, removed }: { added: { tag: string; color?: string }[]; removed: string[] }
) {
	// Fed as the record's `tags` part, so cached list rows and the record show the new tags.
	const { data } = await runPartMethod<{ tags: string[]; tag_colors: Record<string, string> }>(
		UPDATE_RECORD_TAGS,
		{ dt, dn, added, removed },
		dt,
		dn,
		"tags"
	);
	seedTagColors(data.tag_colors);
	return { tags: data.tags };
}
