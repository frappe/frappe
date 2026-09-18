// What the frame hands its built-in sections, so each one is a component like a script's.
import type { InjectionKey, Ref } from "vue";
import type { QuickAction, RecordPageController } from "@/recordPage";

/** The parts the record read returns beside the document, as the panel reads them. */
export interface DocInfo {
	assignments?: { user: string; description?: string }[];
	/** `user` is the string "everyone" for the everyone share. */
	shares?: { user: string; read?: 0 | 1; write?: 0 | 1; submit?: 0 | 1; share?: 0 | 1 }[];
	tags?: string[];
	favourites?: { user: string; creation?: string }[];
	users?: Record<string, { full_name?: string; user_image?: string }>;
	permissions?: Record<string, any>;
}

export interface PanelContext {
	doctype: string;
	docname: string;
	doc: Ref<Record<string, any>>;
	meta: Ref<any>;
	docinfo: Ref<DocInfo | null>;
	controller: RecordPageController;
	run: (action: QuickAction) => void;
	/** Re-reads the sidecar alone, after an assign, share or tag. */
	reloadDocinfo: () => Promise<void>;
}

export const PanelContextKey: InjectionKey<PanelContext> = Symbol("record-panel");

/** A person as the `users` part describes them, or their id when it does not. */
export function personOf(docinfo: DocInfo | null, user: string) {
	const info = docinfo?.users?.[user];
	return { id: user, name: info?.full_name || user, image: info?.user_image || undefined };
}
