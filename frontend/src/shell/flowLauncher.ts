// The Flow launcher's button and docked panel: a custom element in `document.body` whose shadow root holds both.
import { onBeforeUnmount, onMounted, shallowRef, type Ref } from "vue";
import { useEventListener } from "@vueuse/core";

export interface LauncherBox {
	left: number;
	right: number;
	top: number;
	bottom: number;
}

export interface FlowLauncher {
	/** The button's box, or null while there is no launcher or its button is hidden. */
	box: Readonly<Ref<LauncherBox | null>>;
	/** The left edge of the panel while it is open and docked on the right, else null. */
	dockedLeft: Readonly<Ref<number | null>>;
}

export function useFlowLauncher(): FlowLauncher {
	const box = shallowRef<LauncherBox | null>(null);
	const dockedLeft = shallowRef<number | null>(null);
	let parts: LauncherParts | null = null;
	const watchers: MutationObserver[] = [];

	function measure() {
		const rect = parts?.icon.getBoundingClientRect();
		const { left = 0, right = 0, top = 0, bottom = 0, width = 0 } = rect ?? {};
		box.value = width ? { left, right, top, bottom } : null;
		const panel = parts?.panel;
		const docked = panel && panel.dataset.mode === "right" && !panel.hasAttribute("inert");
		dockedLeft.value = docked ? panel.getBoundingClientRect().left : null;
	}

	function follow(found: LauncherParts) {
		parts = found;
		const watcher = new MutationObserver(measure);
		watcher.observe(found.icon, { attributes: true, attributeFilter: ["style", "hidden"] });
		watcher.observe(found.panel, { attributes: true, attributeFilter: ["style", "data-mode", "inert"] });
		watchers.push(watcher);
		measure();
	}

	onMounted(() => {
		const found = findParts();
		if (found) return follow(found);
		// The launcher's bundle may load after the shell.
		const arrival = new MutationObserver(() => {
			const late = findParts();
			if (!late) return;
			arrival.disconnect();
			follow(late);
		});
		arrival.observe(document.body, { childList: true });
		watchers.push(arrival);
	});
	onBeforeUnmount(() => watchers.forEach((watcher) => watcher.disconnect()));
	useEventListener(window, "resize", measure);

	return { box, dockedLeft };
}

interface LauncherParts {
	icon: HTMLElement;
	panel: HTMLElement;
}

function findParts(): LauncherParts | null {
	const root = document.querySelector("flow-launcher")?.shadowRoot;
	const icon = root?.querySelector<HTMLElement>(".icon");
	const panel = root?.querySelector<HTMLElement>(".panel");
	return icon && panel ? { icon, panel } : null;
}
