import { computed, ref, shallowRef, watch, type Ref } from "vue";
import { __ } from "@/i18n";
import type { Scope } from "./draft";
import { fetchViews, type ListedView, pickableViews } from "./viewPicker";

/** The views of the picked doctype, read once per pick, as the Select's options for `scope`. */
export function useViewOptions(doctype: Ref<string>, scope: Ref<Scope>, app: string) {
	const views = shallowRef<ListedView[]>([]);
	const loading = ref(false);
	const failure = ref<string | null>(null);
	let latest = 0;

	async function read(name: string) {
		const ticket = ++latest;
		views.value = [];
		failure.value = null;
		loading.value = !!name;
		if (!name) return;

		try {
			const found = await fetchViews(name, app);
			if (ticket === latest) views.value = found;
		} catch (error) {
			if (ticket !== latest) return;
			failure.value = __("Could not read the views: {0}", [(error as Error).message]);
		} finally {
			if (ticket === latest) loading.value = false;
		}
	}

	watch(doctype, read, { immediate: true });

	const options = computed(() =>
		pickableViews(views.value, scope.value).map((view) => ({
			label: view.label,
			value: view.key,
		}))
	);

	return { views: computed(() => pickableViews(views.value, scope.value)), options, loading, failure };
}
