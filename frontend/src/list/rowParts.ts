// What a list read says beside its rows for the collaboration columns: the people named in
// `_assign`/`_liked_by` and each row's comment count. Module state, so a cell reads it by id.
import { reactive } from "vue";

export interface RowPerson {
	full_name?: string;
	user_image?: string | null;
}

const people = reactive(new Map<string, RowPerson>());
const commentCounts = reactive(new Map<string, number>());

const rowKey = (doctype: string, name: string) => `${doctype}\0${name}`;

/** The `include` parts the shown columns need. */
export function partsFor(fieldnames: string[]): string[] {
	const shown = new Set(fieldnames);
	const parts: string[] = [];
	if (shown.has("_favourite")) parts.push("favourites");
	if (shown.has("_assign") || shown.has("_liked_by")) parts.push("users");
	if (shown.has("_comments")) parts.push("comment_counts");
	return parts;
}

export function seedRowParts(doctype: string, answer: Record<string, unknown>, names: string[]) {
	const users = answer.users as Record<string, RowPerson> | undefined;
	for (const [id, person] of Object.entries(users ?? {})) people.set(id, person);
	const counts = answer.comment_counts as Record<string, number> | undefined;
	if (counts) for (const name of names) commentCounts.set(rowKey(doctype, name), counts[name] ?? 0);
}

export function personOf(id: string): { id: string; name: string; image?: string } {
	const person = people.get(id);
	return { id, name: person?.full_name || id, image: person?.user_image || undefined };
}

export function commentCountOf(doctype: string, name: string): number | undefined {
	return commentCounts.get(rowKey(doctype, name));
}
