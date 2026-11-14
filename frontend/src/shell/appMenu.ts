// The app menu the rail's tile and the navigation header both open.

import { computed, h, inject, shallowRef } from "vue";
import type { DropdownOptions } from "frappe-ui";
import type { Boot } from "@/boot";
import AppLogo from "./AppLogo.vue";
import { menuApps } from "./appSwitchOrder";
import type { PlacesApp } from "./palettePlaces";
import { shellMenu } from "./shellActs";
import { loadDocument } from "./tabKeepAlive";

const APP_MENU = ["all_apps", "open_settings", "customize_sidebar", "copy_link", "about"];

export function useAppMenu() {
	const boot = inject<Boot>("boot")!;
	const appTitle = computed(() => boot.app_title ?? boot.app!);

	// The apps come from `places`, asked for when the trigger is reached, so a boot carries none and
	// the palette's chunk stays out of the shell's load.
	const places = shallowRef<PlacesApp[]>([]);
	const menu = computed<DropdownOptions>(() => {
		const apps = menuApps(places.value, boot.app).map((app) => ({
			label: app.title,
			icon: logoOf(app),
			onClick: () => loadDocument(app.route),
		}));
		const actions = { group: "", hideLabel: true, options: shellMenu(APP_MENU) };
		return apps.length ? [{ group: "", hideLabel: true, options: apps }, actions] : [actions];
	});

	function loadApps() {
		void import("./palettePlaces")
			.then((module) => module.loadApps())
			.then((apps) => (places.value = apps))
			.catch(() => {});
	}

	return { boot, appTitle, menu, loadApps };
}

// A functional component so the menu row draws the logo, not an icon name.
function logoOf(app: PlacesApp) {
	return () => h(AppLogo, { logo: app.logo, title: app.title, size: 16 });
}
