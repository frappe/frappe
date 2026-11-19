// Which listed rows the person starred, kept apart so the Favourite column can go alone.
// A cached record's `favourites` part answers first: each write here keeps it in step, or it outvotes a newer star.
import { addFavourite, removeFavourite } from "@framework/ui/api";
import { feedPartWrite, readCachedDocument, settleTicket, takeTicket } from "@framework/ui/cache";
import { reactive } from "vue";

const stars = reactive(new Map<string, boolean>());

// A second click while the first is in flight is dropped, so it cannot flip the star back.
const toggling = new Set<string>();

// Counts the stars written here, and when each row's last one landed: a list read sent before it may not overwrite it.
let written = 0;
const writtenAt = new Map<string, number>();
export const starsWritten = () => written;

const starKey = (doctype: string, name: string) => `${doctype}\0${name}`;

type Favourites = { user: string }[];

/** Rewrites the person's row in a cached record's `favourites` part; a record without it stays out. */
function syncCachedPart(doctype: string, name: string, user: string, starred: boolean) {
	const cached = readCachedDocument(doctype, name)?.parts.favourites as Favourites | undefined;
	if (!cached || cached.some((row) => row.user === user) === starred) return;
	const others = cached.filter((row) => row.user !== user);
	const ticket = takeTicket();
	feedPartWrite(ticket, doctype, name, "favourites", starred ? [...others, { user }] : others);
	settleTicket(ticket);
}

/** Marks every row of the page: starred when the read lists it, else not. */
export function seedFavourites(
	doctype: string,
	answer: Record<string, unknown>,
	names: string[],
	user?: string,
	sentAt = written
) {
	const starred = new Set((answer.favourites as string[] | undefined) ?? []);
	if (!Array.isArray(answer.favourites)) return;
	for (const name of names) {
		if ((writtenAt.get(starKey(doctype, String(name))) ?? 0) > sentAt) continue;
		const isStar = starred.has(String(name));
		stars.set(starKey(doctype, name), isStar);
		if (user) syncCachedPart(doctype, String(name), user, isStar);
	}
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
		writtenAt.set(key, ++written);
		syncCachedPart(doctype, name, user, starred);
	} finally {
		toggling.delete(key);
	}
}
