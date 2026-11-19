// Track Seen in a list: a row is unseen when the session user is not in its `_seen` list.
import type { ListMeta } from "./defaults";

/** An empty, missing or unreadable `_seen` is unseen. */
export function isUnseen(row: Record<string, unknown>, user: string | null): boolean {
	try {
		const users: unknown = JSON.parse(String(row._seen || "[]"));
		return !(Array.isArray(users) && user !== null && users.includes(user));
	} catch {
		return true;
	}
}

/** The column that carries the mark: the title, else the first column when the list does not show it. */
export function seenColumn(meta: ListMeta | null, fieldnames: string[]): string | null {
	if (!meta?.track_seen) return null;
	const title = meta.title_field || "name";
	return fieldnames.includes(title) ? title : (fieldnames[0] ?? null);
}

/** On a list cell's wrapper; cells draw their text in `text-ink-gray-8`, which this restyles. */
export function cellSeenClass(unseen: boolean): string {
	return unseen
		? "[&_.text-ink-gray-8]:font-medium [&_.text-ink-gray-8]:text-ink-gray-9"
		: "[&_.text-ink-gray-8]:text-ink-gray-7";
}

export function cardSeenClass(unseen: boolean): string {
	return unseen ? "font-medium text-ink-gray-9" : "text-ink-gray-7";
}
