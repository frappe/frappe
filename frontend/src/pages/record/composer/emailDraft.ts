// The email writer's draft as the store keeps it: read back, tested for content, and merged.
import type { UploadedFile } from "@framework/ui/Composer";
import { composerDraft } from "@/shell/composer";
import { isBlankDraft } from "./commentDraft";

export const EMAIL_WRITER = "email";

export type EmailDraft = {
	/** `""` lets the server pick the sender. */
	from: string;
	to: string[];
	cc: string[];
	bcc: string[];
	subject: string;
	content: string;
	attachments: UploadedFile[];
	/** The Communication this answers, `""` if none. */
	inReplyTo: string;
};

export function readEmailDraft(doctype: string, docname: string): EmailDraft {
	return asEmailDraft(composerDraft(doctype, docname, EMAIL_WRITER) ?? {});
}

/** Any stored or script-given value as a full draft; addresses may come comma separated. */
export function asEmailDraft(raw: Record<string, unknown>): EmailDraft {
	return { ...emptyEmailDraft(), ...emailFields(raw) };
}

/** Only the keys `raw` carries, each normalised; the rest of a draft is left alone. */
export function emailFields(raw: Record<string, unknown>): Partial<EmailDraft> {
	const fields: Partial<EmailDraft> = {};
	for (const key of ["from", "subject", "content", "inReplyTo"] as const)
		if (typeof raw[key] === "string") fields[key] = raw[key] as string;
	for (const key of ["to", "cc", "bcc"] as const)
		if (raw[key] !== undefined) fields[key] = addressList(raw[key]);
	if (Array.isArray(raw.attachments)) fields.attachments = raw.attachments as UploadedFile[];
	return fields;
}

export function emptyEmailDraft(): EmailDraft {
	return {
		from: "",
		to: [],
		cc: [],
		bcc: [],
		subject: "",
		content: "",
		attachments: [],
		inReplyTo: "",
	};
}

/** Only the body counts: a draft seeded with To and a subject is still blank. */
export function isBlankEmailDraft({ content, attachments }: EmailDraft) {
	return isBlankDraft({ content, attachments });
}

/** The failed post's body first, then the newer draft's; the newer draft keeps its own headers. */
export function mergeEmailDrafts(failed: EmailDraft, current: EmailDraft): EmailDraft {
	const names = new Set(failed.attachments.map((file) => file.name));
	return {
		from: current.from || failed.from,
		to: distinct([...failed.to, ...current.to]),
		cc: distinct([...failed.cc, ...current.cc]),
		bcc: distinct([...failed.bcc, ...current.bcc]),
		subject: current.subject || failed.subject,
		content: [failed.content, current.content]
			.filter((html) => !isBlankDraft({ content: html, attachments: [] }))
			.join(""),
		attachments: [
			...failed.attachments,
			...current.attachments.filter((file) => !names.has(file.name)),
		],
		inReplyTo: current.inReplyTo || failed.inReplyTo,
	};
}

/** Bare addresses from a comma-separated string or a list; `Name <address>` reads as the address. */
export function addressList(value: unknown): string[] {
	const parts = Array.isArray(value) ? value : typeof value === "string" ? splitAddresses(value) : [];
	return distinct(parts.filter((part) => typeof part === "string").map(bareAddress));
}

// A comma inside a quoted name or angle brackets does not end the address.
function splitAddresses(text: string) {
	return text.match(/(?:"[^"]*"|<[^>]*>|[^,])+/g) ?? [];
}

function bareAddress(address: string) {
	const angled = /<([^>]*)>\s*$/.exec(address);
	return (angled ? angled[1] : address).trim();
}

function distinct(addresses: string[]) {
	const seen = new Set<string>();
	return addresses.filter((address) => {
		const key = address.toLowerCase();
		if (!address || seen.has(key)) return false;
		seen.add(key);
		return true;
	});
}
