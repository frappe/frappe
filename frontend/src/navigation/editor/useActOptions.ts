// The option picker of an Act row's Preset: the act's own `argument.options(query)`, as the palette's
// argument step asks it, with each option marked when it cannot be saved as a preset.

import { computed, ref, shallowRef, watch, type Ref } from "vue";
import { refDebounced } from "@vueuse/core";
import { acts, type ActOption } from "@/acts/dispatcher";
import { optionRefusal } from "./actPicker";

const PAUSE_MS = 200;

export type PresetOption = { option: ActOption; refusal: string | null };

export function useActOptions(act: Ref<string>, query: Ref<string>) {
	const settled = refDebounced(query, PAUSE_MS);
	const found = shallowRef<ActOption[]>([]);
	const loading = ref(false);
	let latest = 0;

	// An older reply that lands after a newer ask is dropped.
	async function ask(name: string, text: string) {
		const argument = acts.find(name)?.argument;
		const ticket = ++latest;
		if (!argument) return void (found.value = []);

		loading.value = true;
		try {
			const options = await argument.options(text);
			if (ticket === latest) found.value = options;
		} catch (error) {
			console.error("[frappe] the editor could not read an act's options", error);
			if (ticket === latest) found.value = [];
		} finally {
			if (ticket === latest) loading.value = false;
		}
	}

	watch([act, settled], ([name, text]) => ask(name, text), { immediate: true });

	const options = computed<PresetOption[]>(() =>
		found.value.map((option) => ({ option, refusal: optionRefusal(act.value, option) }))
	);

	return { options, loading };
}
