// A tag's colour is stored on its Tag (the `color` Select, Helpdesk's names). Module state, filled
// by every read that names tags, so a chip anywhere reads it by name.
import { reactive } from "vue";
import { runMethod } from "@framework/ui/api";

const GRAY = "bg-surface-gray-5";
const SET_TAG_COLOR = "frappe.desk.doctype.tag.tag.set_tag_color";
const UPDATE_RECORD_TAGS = "frappe.desk.doctype.tag.tag.update_record_tags";

// Full class names, so Tailwind's scanner sees each one.
export const TAG_COLORS: Readonly<Record<string, string>> = {
	Gray: GRAY,
	Black: "bg-surface-gray-10",
	Blue: "bg-surface-blue-6",
	Green: "bg-surface-green-6",
	Red: "bg-surface-red-6",
	Pink: "bg-surface-pink-6",
	Orange: "bg-surface-orange-6",
	Amber: "bg-surface-amber-6",
	Yellow: "bg-surface-yellow-6",
	Cyan: "bg-surface-cyan-6",
	Teal: "bg-surface-teal-6",
	Violet: "bg-surface-violet-6",
	Purple: "bg-surface-purple-6",
};

export const TAG_COLOR_NAMES = Object.keys(TAG_COLORS);

const stored = reactive(new Map<string, string>());

/** Takes a read's `tag_colors` part: each named tag's colour, `""` for one without. */
export function seedTagColors(colors: unknown) {
	if (!colors || typeof colors !== "object" || Array.isArray(colors)) return;
	for (const [tag, color] of Object.entries(colors)) {
		if (typeof color !== "string") continue;
		if (color) stored.set(tag, color);
		else stored.delete(tag);
	}
}

/** The dot class of a tag; one with no stored colour draws gray. */
export function tagColorClass(tag: string): string {
	return colorClass(stored.get(tag));
}

/** The stored colour name of a tag, `""` for one without. */
export function tagColorName(tag: string): string {
	return stored.get(tag) ?? "";
}

export function colorClass(color: string | undefined): string {
	return TAG_COLORS[color ?? ""] ?? GRAY;
}

/** Saves a colour on the Tag itself and repaints every chip of it. */
export async function recolourTag(tag: string, color: string) {
	await runMethod(SET_TAG_COLOR, { tag, color });
	seedTagColors({ [tag]: color });
}

/** Saves one picker session on a record in one call; answers the record's tags and their colours. */
export async function updateRecordTags(
	dt: string,
	dn: string,
	{ added, removed }: { added: { tag: string; color?: string }[]; removed: string[] }
) {
	const { data } = await runMethod<{ tags: string[]; tag_colors: Record<string, string> }>(
		UPDATE_RECORD_TAGS,
		{ dt, dn, added, removed }
	);
	seedTagColors(data.tag_colors);
	return { tags: data.tags };
}
