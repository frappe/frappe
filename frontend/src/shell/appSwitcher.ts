// The quick app switcher's state: the apps in switching order and the selected one. Keys drive it
// (`appSwitcherKey.ts`); the overlay (`AppSwitcher.vue`) draws it.
import { ref, shallowRef } from "vue";
import type { Boot } from "@/boot";
import { appsUsed } from "./appUse";
import { switchOrder } from "./appSwitchOrder";
import type { PlacesApp } from "./palettePlaces";
import { loadDocument } from "./tabKeepAlive";

class AppSwitcher {
	readonly open = ref(false);
	readonly apps = shallowRef<PlacesApp[]>([]);
	readonly selected = ref(0);
	/** The key that opens it is down, while the apps are still being asked for. */
	private starting = false;
	/** How the press ended before the apps came, if it did. */
	private ended: "release" | "cancel" | null = null;
	private boot: Boot | null = null;

	/** The first press opens it with the previous app selected; each later one steps `by`. */
	async press(boot: Boot, by: 1 | -1) {
		if (this.open.value) return this.move(by);
		if (this.starting) return;
		this.starting = true;
		this.ended = null;
		this.boot = boot;
		// Imported here so the palette's chunk is not fetched with the key's, on every load.
		const apps = await import("./palettePlaces").then((module) => module.loadApps()).catch(() => null);
		this.starting = false;
		if (!apps || this.ended === "cancel") return;

		const ordered = switchOrder(apps, boot.app, appsUsed(boot));
		const current = ordered[0]?.app === boot.app;
		if (ordered.length < (current ? 2 : 1)) return;

		this.apps.value = ordered;
		// With no app current, as on `/apps`, the first step lands on the most recent one, or the last.
		this.selected.value = current ? wrap(by, ordered.length) : by > 0 ? 0 : ordered.length - 1;
		this.open.value = true;
		if (this.ended === "release") this.release();
	}

	/** Whether a press is under way, so its release is the switcher's. */
	get engaged() {
		return this.open.value || this.starting;
	}

	move(by: 1 | -1) {
		this.selected.value = wrap(this.selected.value + by, this.apps.value.length);
	}

	/** The key that holds it open went up: opens the selected app. */
	release() {
		this.ended = "release";
		if (this.open.value) this.choose(this.selected.value);
	}

	cancel() {
		this.ended = "cancel";
		this.open.value = false;
	}

	choose(index: number) {
		const app = this.apps.value[index];
		this.open.value = false;
		// The current app is first, and choosing it leaves the page as it is.
		if (app && app.app !== this.boot?.app) loadDocument(app.route);
	}
}

function wrap(index: number, length: number) {
	return ((index % length) + length) % length;
}

export const appSwitcher = new AppSwitcher();
