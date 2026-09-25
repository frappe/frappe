// The record page's three server calls (the load, the re-read of the parts, the save) and its cached read.
import { readCachedDocument, RECORD_PARTS } from "@framework/ui/cache";
import { getDocument, updateDocument } from "@framework/ui/api";
import type { DocInfo } from "./panel/context";

export { RECORD_PARTS };

export interface LoadedRecord {
	document: Record<string, any>;
	docinfo: DocInfo;
	linkTitles: Record<string, string>;
}

/** The document, its parts and the link titles in one round trip; the read marks the record seen. */
export function loadRecord(doctype: string, name: string): Promise<LoadedRecord> {
	return read(doctype, name, [...RECORD_PARTS, "seen"]);
}

/** A copy of the last full read the shared cache holds; null when it holds none. */
export function readCachedRecord(doctype: string, name: string): LoadedRecord | null {
	const entry = readCachedDocument(doctype, name);
	if (!entry?.complete) return null;
	return JSON.parse(JSON.stringify(loaded(entry.doc, entry.parts)));
}

/** The parts alone, on a realtime delta; the draft is untouched and nothing is marked seen. */
export async function loadParts(doctype: string, name: string): Promise<DocInfo> {
	const { docinfo } = await read(doctype, name, RECORD_PARTS);
	return docinfo;
}

/** The whole document, as the draft holds it; `modified` is what lets the server refuse a stale save. */
export async function saveRecord(
	doctype: string,
	doc: Record<string, any>
): Promise<Record<string, any>> {
	const { data } = await updateDocument(doctype, doc.name, { ...doc, doctype, name: doc.name });
	return data;
}

async function read(doctype: string, name: string, include: readonly string[]): Promise<LoadedRecord> {
	const envelope = await getDocument(doctype, name, { include });
	return loaded(envelope.data, envelope);
}

function loaded(document: Record<string, any>, parts: Readonly<Record<string, unknown>>): LoadedRecord {
	return {
		document,
		docinfo: {
			permissions: parts.permissions as DocInfo["permissions"],
			assignments: parts.assignments as DocInfo["assignments"],
			shares: parts.shares as DocInfo["shares"],
			tags: parts.tags as DocInfo["tags"],
			favourites: parts.favourites as DocInfo["favourites"],
			follows: parts.follows as DocInfo["follows"],
			users: parts.users as DocInfo["users"],
			attachments: parts.attachments as DocInfo["attachments"],
		},
		linkTitles: (parts.link_titles ?? {}) as Record<string, string>,
	};
}
