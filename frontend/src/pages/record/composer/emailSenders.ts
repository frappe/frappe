// Who an email can go out as, read once per session, and the address book the To row searches.
import type { Recipient } from "@framework/ui/Composer";
import { runMethod } from "@framework/ui/api";

export type OutgoingSenders = { senders: string[]; default: string | null };

/** The From row's choices, the one picked, and whether nothing can send. */
export type SenderChoice = { senders: string[]; from: string; blocked: boolean };

type ContactOption = { value: string; label?: string; description?: string };

let senders: Promise<OutgoingSenders> | null = null;

/** Asked on the first open, never on load; a failure asks again next time. */
export function loadSenders(): Promise<OutgoingSenders> {
	senders ??= runMethod<OutgoingSenders>(
		"frappe.email.inbox.get_outgoing_senders",
		{},
		{ http: "GET" }
	)
		.then(({ data }) => data)
		.catch((error) => {
			senders = null;
			throw error;
		});
	return senders;
}

/** A From row only with two or more; one is used as is; none leaves the server's default. */
export function chooseSender(
	answer: OutgoingSenders,
	user: string,
	current: string
): SenderChoice {
	const list = answer.senders;
	if (list.length > 1) {
		const from = [current, user].find((one) => list.includes(one)) ?? list[0];
		return { senders: list, from, blocked: false };
	}
	if (list.length === 1) return { senders: list, from: list[0], blocked: false };
	return { senders: [], from: "", blocked: !answer.default };
}

export async function searchRecipients(query: string): Promise<Recipient[]> {
	const { data } = await runMethod<ContactOption[]>(
		"frappe.email.get_contact_list",
		{ txt: query },
		{ http: "GET" }
	);
	return data.map((option) => ({
		email: option.value,
		label: option.description || undefined,
	}));
}

/** Forgets the session's answer; for tests. */
export function resetSenders() {
	senders = null;
}
