// The index's notices, as boot lists them, and the cards this tab has tucked into the bell.
import { runMethod } from "@framework/ui/api";
import type { Boot } from "@/boot";
import { tabMemory } from "@/browserMemory";

export type IndexNoticeList = NonNullable<Boot["notices"]>;
export type WhatsNewEntry = NonNullable<IndexNoticeList["whats_new"]>[number];
export type NoticeKey = keyof IndexNoticeList;

/** The keys of the cards this person has closed in this tab. */
export function tuckedNotices(user: string) {
	return tabMemory<NoticeKey[]>("index-notices-tucked", user, isKeyList);
}

/** Records that this person has seen the release notes of every app's current version. */
export function markWhatsNewSeen() {
	return runMethod("frappe.utils.change_log.update_last_known_versions", {}, { nullable: true });
}

function isKeyList(value: unknown): value is NoticeKey[] {
	return Array.isArray(value) && value.every((key) => key === "setup" || key === "whats_new");
}
