// The Favourite column's state: which listed rows the person starred. Module state, kept apart
// so the column can go without touching the rest of the list. A cached record that holds its
// own `favourites` part answers first, so a star toggled on the record page shows here.
import { addFavourite, removeFavourite } from "@framework/ui/api";
import { readCachedDocument } from "@framework/ui/cache";
import { reactive } from "vue";

const stars = reactive(new Map<string, boolean>());

// A second click while the first is in flight is dropped, so it cannot flip the star back.
const toggling = new Set<string>();

const starKey = (doctype: string, name: string) => `${doctype}\0${name}`;

/** Marks every row of the page: starred when the read lists it, else not. */
export function seedFavourites(doctype: string, answer: Record<string, unknown>, names: string[]) {
	const starred = new Set((answer.favourites as string[] | undefined) ?? []);
	if (!Array.isArray(answer.favourites)) return;
	for (const name of names) stars.set(starKey(doctype, name), starred.has(String(name)));
}

export function isStarred(doctype: string, name: string, user: string): boolean {
	const docinfo = readCachedDocument(doctype, name)?.parts.favourites;
	if (docinfo) return (docinfo as { user: string }[]).some((row) => row.user === user);
	return stars.get(starKey(doctype, name)) ?? false;
}

/** Stars or unstars the row through the record's `favourites` sub-resource. */
export async function toggleStar(doctype: string, name: string, user: string) {
	const key = starKey(doctype, name);
	if (toggling.has(key)) return;
	toggling.add(key);
	try {
		const starred = !isStarred(doctype, name, user);
		await (starred ? addFavourite : removeFavourite)(doctype, name);
		stars.set(key, starred);
	} finally {
		toggling.delete(key);
	}
}
