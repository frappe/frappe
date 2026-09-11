// What the frame hands its built-in sections, so each one is a component like a script's.
import type { InjectionKey, Ref } from "vue";
import type { QuickAction, RecordPageController } from "@/recordPage";

/** `getdoc`'s sidecar, the parts the panel reads; the rest is not typed here. */
export interface DocInfo {
	assignments?: { owner: string; description?: string }[];
	shared?: { user: string; everyone?: 0 | 1; write?: 0 | 1 }[];
	tags?: string;
	user_info?: Record<string, { fullname?: string; image?: string }>;
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

/** A person as `docinfo.user_info` describes them, or their id when it does not. */
export function personOf(docinfo: DocInfo | null, user: string) {
	const info = docinfo?.user_info?.[user];
	return { id: user, name: info?.fullname || user, image: info?.image };
}
