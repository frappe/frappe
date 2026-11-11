// What `docinfo` says about the record's people and tags, and the list arithmetic the pickers need.
import { personOf, type DocInfo } from "./context";

export interface Person {
	id: string;
	name: string;
	image?: string;
}

export interface SharedPerson extends Person {
	everyone: boolean;
	canWrite: boolean;
}

export const EVERYONE = "everyone";

export function assigneesOf(docinfo: DocInfo | null): Person[] {
	return (docinfo?.assignments ?? []).map((row) => personOf(docinfo, row.user));
}

// A share with everyone has no person to draw; it is named as such.
export function sharedWith(docinfo: DocInfo | null): SharedPerson[] {
	return (docinfo?.shares ?? []).map((row) => {
		const everyone = row.user === EVERYONE;
		return {
			...(everyone ? { id: EVERYONE, name: "Everyone" } : personOf(docinfo, row.user)),
			everyone,
			canWrite: Boolean(row.write),
		};
	});
}

export function tagsOf(docinfo: DocInfo | null): string[] {
	return docinfo?.tags ?? [];
}

/** What a new selection adds and drops against the one it replaces. */
export function listDiff(picked: string[], current: string[]) {
	return {
		added: picked.filter((value) => !current.includes(value)),
		dropped: current.filter((value) => !picked.includes(value)),
	};
}

export function matchingTags(known: string[], query: string): string[] {
	const wanted = normalize(query);
	return known.filter((tag) => normalize(tag).includes(wanted));
}

// Desk v1 joins tags with commas on the document, so a name with one would read as two there.
export function canCreateTag(known: string[], query: string): boolean {
	const wanted = normalize(query);
	if (!wanted || wanted.includes(",")) return false;
	return !known.some((tag) => normalize(tag) === wanted);
}

function normalize(text: string) {
	return text.trim().toLowerCase();
}
