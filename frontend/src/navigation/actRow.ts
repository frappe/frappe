// What an Act row does, for the sidebar's row and the rail's cell alike: whether it draws, what a
// click runs, and the spinner. It runs the same two things the palette's act row does.

import { computed, onScopeDispose, ref } from "vue";
import { acts } from "@/acts/dispatcher";
import { openArgumentStep } from "@/shell/palette";

/** A run shows its spinner only after this long, so a quick act does not flash it. */
export const SPINNER_DELAY_MS = 300;

type ActRendering = { act: string; value?: unknown };

export function useActRow(rendering: () => ActRendering) {
	const running = ref(false);
	const spinning = ref(false);
	let timer: ReturnType<typeof setTimeout> | undefined;

	const available = computed(() => isActAvailable(rendering().act));

	async function run() {
		if (running.value) return;

		const { act, value } = rendering();
		running.value = true;
		timer = setTimeout(() => (spinning.value = true), SPINNER_DELAY_MS);

		try {
			const argument = acts.find(act)?.argument;
			if ("value" in rendering() || !argument) await acts.perform(act, value);
			else openArgumentStep(act);
		} finally {
			clearTimeout(timer);
			running.value = spinning.value = false;
		}
	}

	onScopeDispose(() => clearTimeout(timer));

	return { available, spinning, run };
}

/** Whether a row for the act `name` draws: the act is present, or it is an app's and its acts are still loading. */
export function isActAvailable(name: string): boolean {
	return !!acts.find(name) || acts.loads(name);
}
