// The settings of one saved view, read when its page opens, from the layer the person sees it at.
import { runMethod } from "@framework/ui/api";
import { getCurrentScope, onScopeDispose, ref, shallowRef, type Ref, type ShallowRef } from "vue";
import type { ListSettings } from "./storedSettings";

const READ = "frappe.desk.doctype.doctype_view.api.view_settings";

export interface ViewSettingsHandle {
	loaded: Ref<boolean>;
	/** The view's own settings, no other layer's: the base the URL query is a layer on. */
	stored: ShallowRef<ListSettings>;
	/** Whether this person can save the view: their own, or a shared one as a site administrator. */
	saveable: Ref<boolean>;
	failure: ShallowRef<unknown>;
	retry: () => Promise<void>;
}

export function useViewSettings(doctype: string, key: string): ViewSettingsHandle {
	const loaded = ref(false);
	const stored = shallowRef<ListSettings>({});
	const saveable = ref(false);
	const failure = shallowRef<unknown>(null);
	const asking = new AbortController();
	if (getCurrentScope()) onScopeDispose(() => asking.abort());

	async function load() {
		failure.value = null;
		try {
			const { data } = await runMethod<{ settings: ListSettings; saveable: boolean }>(
				READ,
				{ doctype, key },
				{ http: "GET", signal: asking.signal }
			);
			if (asking.signal.aborted) return;
			stored.value = data.settings ?? {};
			saveable.value = data.saveable;
			loaded.value = true;
		} catch (error) {
			if (!asking.signal.aborted) failure.value = error;
		}
	}

	void load();
	return { loaded, stored, saveable, failure, retry: load };
}
