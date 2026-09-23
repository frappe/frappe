// How the email writer opens: a new draft from the record or the email it answers, a stored one re-addressed.
import { activityTimelineRows, type EmailActivity } from "@framework/ui/ActivityTimeline";
import type { ActivityItem, RecordPageApi } from "@/recordPage";
import { composerDraft, openComposer, replaceComposerDraft } from "@/shell/composer";
import { EMAIL_TYPES } from "../feed/recordFeeds";
import {
	EMAIL_WRITER,
	emailFields,
	emptyEmailDraft,
	isFreshEmailDraft,
	readEmailDraft,
	type EmailDraft,
} from "./emailDraft";
import { prefillEmail, replyFill } from "./emailPrefill";

type EmailData = EmailActivity["data"];

/** What the seed reads from the page, which the host builds after the composer's host half. */
export interface EmailSeedContext {
	page: () => RecordPageApi | null | undefined;
	/** The session user's address, dropped from a Reply all. */
	userEmail: string;
}

/** A draft in memory wins, except that a `replyTo` re-addresses it; the body stays. */
export function openEmail(
	doctype: string,
	docname: string,
	context: EmailSeedContext | undefined,
	draft: Record<string, unknown> = {}
) {
	const page = context?.page();
	const reader = page?.doctype === doctype && page.docname === docname ? page : undefined;
	const reply = replyFor(reader, context?.userEmail ?? "", draft);
	if (!composerDraft(doctype, docname, EMAIL_WRITER)) seed(doctype, docname, reader, reply, draft);
	else if (reply) readdress(doctype, docname, reply, draft.replyAll === true);
	openComposer(doctype, docname, EMAIL_WRITER);
}

/** What a plain open of the email writer on this record starts with. */
export function freshEmail(page: RecordPageApi | undefined): EmailDraft {
	const prefill = page ? prefillEmail(page.meta, page.doc, titleOf(page)) : {};
	return { ...emptyEmailDraft(), ...prefill };
}

// A fresh draft is left out of the store, as the writer leaves it; an untouched writer may be open.
function seed(
	doctype: string,
	docname: string,
	page: RecordPageApi | undefined,
	reply: Partial<EmailDraft> | undefined,
	draft: Record<string, unknown>
) {
	const next = newDraft(page, reply, draft);
	if (next.from || !isFreshEmailDraft(next, freshEmail(page)))
		replaceComposerDraft(doctype, docname, EMAIL_WRITER, next);
}

function newDraft(
	page: RecordPageApi | undefined,
	reply: Partial<EmailDraft> | undefined,
	draft: Record<string, unknown>
): EmailDraft {
	return { ...freshEmail(page), ...reply, ...emailFields(draft) };
}

// Bcc changes only for a Reply all, the one reply that fills it.
function readdress(doctype: string, docname: string, reply: Partial<EmailDraft>, all: boolean) {
	const { bcc, ...headers } = reply;
	const stored = readEmailDraft(doctype, docname);
	const next = { ...stored, ...headers, ...(all && bcc ? { bcc } : {}) };
	replaceComposerDraft(doctype, docname, EMAIL_WRITER, next);
}

// The thread comes from the key, since a row the writer just sent has no name in its data.
// An email the reader has not loaded still threads the reply; the headers stay as they were.
function replyFor(
	page: RecordPageApi | undefined,
	userEmail: string,
	draft: Record<string, unknown>
): Partial<EmailDraft> | undefined {
	if (typeof draft.replyTo !== "string") return undefined;
	const inReplyTo = draft.replyTo.replace(/^email:/, "");
	const email = page && loadedEmail(page, draft.replyTo);
	if (!email) return { inReplyTo };
	return { ...replyFill(email, userEmail, draft.replyAll === true), inReplyTo };
}

function loadedEmail(page: RecordPageApi, key: string): EmailData | undefined {
	const item = page.activity.items.find(
		(one): one is ActivityItem => one.name === key && "type" in one && one.type === "email"
	);
	if (item) return item.data as EmailData;
	const row = activityTimelineRows(page.doctype, page.docname, EMAIL_TYPES).find(
		(one) => one.key === key && one.type === "email"
	);
	return row?.data as EmailData | undefined;
}

/** The record's title as the header shows it: the title field, else the name. */
export function titleOf(page: RecordPageApi) {
	const field = page.meta?.title_field;
	return String((field && page.doc[field]) || page.docname);
}
