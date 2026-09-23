// What a new email starts with: the record's subject and address, or the headers of the email it answers.
import type { EmailActivity } from "@framework/ui/ActivityTimeline";
import { __ } from "@/i18n";
import { addressList, type EmailDraft } from "./emailDraft";

type ReplyFields = Pick<EmailDraft, "to" | "cc" | "bcc" | "subject">;

/** `Re: <title>`, and To from the record's first email field when it holds a value. */
export function prefillEmail(
	meta: Record<string, any> | null,
	doc: Record<string, any>,
	title: string
): Partial<EmailDraft> {
	const field = (meta?.fields ?? []).find(
		(one: Record<string, any>) => one.fieldtype === "Data" && one.options === "Email"
	);
	const address = field ? doc[field.fieldname] : undefined;
	return {
		subject: replySubject(title),
		to: typeof address === "string" ? addressList(address) : [],
	};
}

/** Desk v1's reply: to the sender, or to the recipients of the user's own email; `all` adds Cc. */
export function replyFill(email: EmailActivity["data"], user: string, all: boolean): ReplyFields {
	const sender = addressList(email.sender);
	const mine = same(sender[0], user);
	const recipients = addressList(email.to);
	const to = mine ? recipients : sender;
	const others = [...(mine ? [] : recipients), ...addressList(email.cc)];
	return {
		to,
		cc: all ? others.filter((one) => !same(one, user) && !to.some((t) => same(t, one))) : [],
		bcc: all ? addressList(email.bcc) : [],
		subject: replySubject(email.subject ?? ""),
	};
}

// Desk v1 adds "Re:" only when the subject does not already start with it.
function replySubject(subject: string) {
	if (subject.split(":")[0].trim().toLowerCase() === "re") return subject;
	return __("Re: {0}", [subject]);
}

function same(one: string | undefined, other: string) {
	return Boolean(one) && one!.trim().toLowerCase() === other.trim().toLowerCase();
}
