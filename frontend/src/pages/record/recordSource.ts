// The record page's three server calls: the load, the re-read of the parts, and the save.
import { getDocument, updateDocument } from "@framework/ui/api";
import type { DocInfo } from "./panel/context";

/** The parts the page reads beside the document; `seen` is added on the load alone. */
export const RECORD_PARTS = [
	"permissions",
	"assignments",
	"shares",
	"tags",
	"favourites",
	"follows",
	"users",
	"link_titles",
] as const;

export interface LoadedRecord {
	document: Record<string, any>;
	docinfo: DocInfo;
	linkTitles: Record<string, string>;
}

/** The document, its parts and the link titles in one round trip; the read marks the record seen. */
export function loadRecord(doctype: string, name: string): Promise<LoadedRecord> {
	return read(doctype, name, [...RECORD_PARTS, "seen"]);
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
	return {
		document: envelope.data,
		docinfo: {
			permissions: envelope.permissions as DocInfo["permissions"],
			assignments: envelope.assignments as DocInfo["assignments"],
			shares: envelope.shares as DocInfo["shares"],
			tags: envelope.tags as DocInfo["tags"],
			favourites: envelope.favourites as DocInfo["favourites"],
			follows: envelope.follows as DocInfo["follows"],
			users: envelope.users as DocInfo["users"],
		},
		linkTitles: (envelope.link_titles ?? {}) as Record<string, string>,
	};
}
