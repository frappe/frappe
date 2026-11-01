// The Flow launcher's round button. It is not shell code: a custom element in `document.body` whose
// shadow root holds the button, which a drag moves by its `style`.
import { onBeforeUnmount, onMounted, shallowRef, type Ref } from "vue";
import { useEventListener } from "@vueuse/core";

export interface LauncherBox {
	left: number;
	right: number;
	top: number;
	bottom: number;
}

/** The button's box, or null while there is no launcher or its button is hidden. */
export function useFlowLauncherBox(): Readonly<Ref<LauncherBox | null>> {
	const box = shallowRef<LauncherBox | null>(null);
	let icon: HTMLElement | null = null;
	const watchers: MutationObserver[] = [];

	function measure() {
		const rect = icon?.getBoundingClientRect();
		const { left = 0, right = 0, top = 0, bottom = 0, width = 0 } = rect ?? {};
		box.value = width ? { left, right, top, bottom } : null;
	}

	function follow(found: HTMLElement) {
		icon = found;
		const watcher = new MutationObserver(measure);
		watcher.observe(icon, { attributes: true, attributeFilter: ["style", "hidden"] });
		watchers.push(watcher);
		measure();
	}

	onMounted(() => {
		const found = findIcon();
		if (found) return follow(found);
		// The launcher's bundle may load after the shell.
		const arrival = new MutationObserver(() => {
			const late = findIcon();
			if (!late) return;
			arrival.disconnect();
			follow(late);
		});
		arrival.observe(document.body, { childList: true });
		watchers.push(arrival);
	});
	onBeforeUnmount(() => watchers.forEach((watcher) => watcher.disconnect()));
	useEventListener(window, "resize", measure);

	return box;
}

function findIcon(): HTMLElement | null {
	return document.querySelector("flow-launcher")?.shadowRoot?.querySelector<HTMLElement>(".icon") ?? null;
}
