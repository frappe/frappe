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

export function assigneesOf(docinfo: DocInfo | null): Person[] {
	return (docinfo?.assignments ?? []).map((row) => personOf(docinfo, row.owner));
}

// A share with everyone has no person to draw; it is named as such.
export function sharedWith(docinfo: DocInfo | null): SharedPerson[] {
	return (docinfo?.shared ?? []).map((row) => ({
		...(row.everyone ? { id: "everyone", name: "Everyone" } : personOf(docinfo, row.user)),
		everyone: Boolean(row.everyone),
		canWrite: Boolean(row.write),
	}));
}

/** `getdoc` joins the tags with commas. */
export function tagsOf(docinfo: DocInfo | null): string[] {
	return (docinfo?.tags ?? "")
		.split(",")
		.map((tag) => tag.trim())
		.filter(Boolean);
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

// The server joins tags with commas, so a name with one would come back as two.
export function canCreateTag(known: string[], query: string): boolean {
	const wanted = normalize(query);
	if (!wanted || wanted.includes(",")) return false;
	return !known.some((tag) => normalize(tag) === wanted);
}

const PALETTE = [
	"bg-blue-500",
	"bg-green-500",
	"bg-amber-500",
	"bg-violet-500",
	"bg-pink-500",
	"bg-red-500",
];

/** Colour follows the tag's name, so the same tag looks the same on every record. */
export function tagColor(tag: string): string {
	let hash = 0;
	for (const character of tag) hash = (hash * 31 + character.charCodeAt(0)) % 997;
	return PALETTE[hash % PALETTE.length];
}

function normalize(text: string) {
	return text.trim().toLowerCase();
}
