// A background re-read of the record, merged into the draft the reader may be editing.

export interface Draft {
	doc: Record<string, any>;
	saved: Record<string, any>;
}

/** `saved` takes the server's values and `doc` keeps the fields the reader touched; a touched field the server also changed keeps the old `modified`. */
export function mergeRefetch({ doc, saved }: Draft, fresh: Record<string, any>): Draft {
	// A save that landed while the read was out holds the newer document.
	if (fresh.modified < saved.modified || same(fresh, saved)) return { doc, saved };
	const merged: Draft = { saved: { ...fresh }, doc: JSON.parse(JSON.stringify(fresh)) };
	let overlap = false;
	for (const field of new Set([...Object.keys(saved), ...Object.keys(doc)])) {
		if (sameContent(doc[field], saved[field])) continue;
		merged.doc[field] = doc[field];
		if (!sameContent(fresh[field], saved[field])) overlap = true;
	}
	if (overlap) merged.saved.modified = merged.doc.modified = saved.modified;
	return merged;
}

/** Equal by content, row stamps included. */
export function same(one: unknown, other: unknown) {
	return JSON.stringify(one) === JSON.stringify(other);
}

/** Equal by content; a child row's stamps are not content. */
export function sameContent(one: unknown, other: unknown) {
	return JSON.stringify(one, withoutRowStamps) === JSON.stringify(other, withoutRowStamps);
}

// Bookkeeping that any save of the parent restamps on every row; never a reader's edit.
const ROW_STAMPS = new Set(["modified", "modified_by", "creation", "owner"]);

function withoutRowStamps(_key: string, value: unknown) {
	if (!value || typeof value !== "object" || !("parentfield" in value)) return value;
	return Object.fromEntries(Object.entries(value).filter(([key]) => !ROW_STAMPS.has(key)));
}
