// Alt+` opens the app switcher on every page and Shift+Alt+` opens it from the other end; while it
// is open, the arrows and Enter move and choose, Esc cancels, and letting go of Alt opens the app.
import { defineAsyncComponent, defineComponent, h, inject, onBeforeUnmount } from "vue";
import { useKeyboardShortcut } from "frappe-ui";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { appSwitcher } from "./appSwitcher";
import { recordAppUse } from "./appUse";

// Drawn from the first press, so its code stays out of the shell's load.
const AppSwitcherOverlay = defineAsyncComponent(() => import("./AppSwitcher.vue"));

// The switch key: its frappe-ui combo name and its `event.code`. Another key is a one-line edit here.
const KEY = { combo: "Backtick", code: "Backquote" } as const;

const STEPS: Record<string, 1 | -1> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };

export const AppSwitcherKey = defineComponent({
	name: "AppSwitcherKey",
	setup() {
		const boot = inject<Boot>("boot")!;
		recordAppUse(boot);

		// `event.code` is matched, so Option+` on a Mac, a dead key, types no accent: the press is cancelled.
		for (const [combo, by] of [
			[`Alt+${KEY.combo}`, 1],
			[`Alt+Shift+${KEY.combo}`, -1],
		] as const)
			useKeyboardShortcut({
				combo,
				description: __("Switch app"),
				allowInInput: true,
				preventDefault: false,
				handler: (event) => {
					event.preventDefault();
					if (!event.repeat && !event.isComposing) void appSwitcher.press(boot, by);
				},
			});

		document.addEventListener("keydown", whileOpen, true);
		document.addEventListener("keyup", onKeyUp, true);
		window.addEventListener("blur", cancel);
		onBeforeUnmount(() => {
			document.removeEventListener("keydown", whileOpen, true);
			document.removeEventListener("keyup", onKeyUp, true);
			window.removeEventListener("blur", cancel);
		});
		return () => (appSwitcher.open.value ? h(AppSwitcherOverlay) : null);
	},
});

function whileOpen(event: KeyboardEvent) {
	if (!appSwitcher.open.value || event.code === KEY.code) return;
	// The release was missed, such as an Alt let go in another window.
	if (!event.altKey) return appSwitcher.release();
	const by = STEPS[event.key];
	if (!by && event.key !== "Enter" && event.key !== "Escape") return;
	event.preventDefault();
	event.stopPropagation();
	if (by) appSwitcher.move(by);
	else if (event.key === "Enter") appSwitcher.release();
	else appSwitcher.cancel();
}

function onKeyUp(event: KeyboardEvent) {
	if (event.key !== "Alt" || !appSwitcher.engaged) return;
	// Alt alone would move focus to the browser's menu bar.
	event.preventDefault();
	appSwitcher.release();
}

function cancel() {
	appSwitcher.cancel();
}
