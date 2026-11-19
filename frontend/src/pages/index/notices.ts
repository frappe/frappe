// The index's notices, as boot lists them, and the cards this tab has tucked into the bell.
import { runMethod } from "@framework/ui/api";
import type { Boot } from "@/boot";
import { tabMemory } from "@/browserMemory";

export type IndexNoticeList = NonNullable<Boot["notices"]>;
export type WhatsNewEntry = NonNullable<IndexNoticeList["whats_new"]>[number] & {
	notes: { version: string; html: string }[];
};
export type NoticeKey = keyof IndexNoticeList;

/** The keys of the cards this person has closed in this tab. */
export function tuckedNotices(user: string) {
	return tabMemory<NoticeKey[]>("index-notices-tucked", user, isKeyList);
}

/** The release notes of each app updated since this person last looked, which the server then records as seen. */
export async function readWhatsNew(): Promise<WhatsNewEntry[]> {
	const response = await runMethod<WhatsNewEntry[]>("frappe.shell.index_notices.read_whats_new");
	return response.data;
}

function isKeyList(value: unknown): value is NoticeKey[] {
	return Array.isArray(value) && value.every((key) => key === "setup" || key === "whats_new");
}
