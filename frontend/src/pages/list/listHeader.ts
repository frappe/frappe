// The list page's header row: its built-in items, and how the engine's list becomes the row.
import { hidingDenied, projectHeader } from "@/pageEngine";
import type { ResolvedItem } from "@/pageEngine/surface";
import type { HeaderItem } from "@/pageEngine/types";
import { __ } from "@/i18n";
import { favouriteWording } from "@/pages/favourite/favouriteWording";
import type { SwitcherHost } from "./viewSwitcher/switcherHost";
import ViewSwitcher from "./viewSwitcher/ViewSwitcher.vue";

// Create and every control a script adds; the rest go in `⋯`.
const HEADER_BUDGET = 3;
// Create keeps its slot whatever a script adds, as Save does on the record page.
const PINNED_CONTROLS = ["new"];

export interface ListHeaderHost {
	doctype: string;
	/** The doctype's module, once its meta is in. */
	module: () => { label: string; href?: string } | null;
	/** The view crumb's control, always drawn: the plain List has one too. */
	switcher: SwitcherHost;
	/** The doctype crumb's link to the list; null on the plain List, which is that address. */
	listHref: () => string | null;
	/** False until a list settings read says what is starred. */
	starsLoaded: () => boolean;
	favourited: () => boolean;
	toggleFavourite: () => unknown;
	create: () => unknown;
}

/** Crumbs, switcher and star on the left; Create on the right. */
export function listHeaderItems(host: ListHeaderHost): HeaderItem[] {
	const module = host.module();
	const items: HeaderItem[] = [];
	if (module) items.push({ name: "module", zone: "left", display: "crumb", ...module });
	items.push({
		name: "doctype",
		label: host.doctype,
		zone: "left",
		display: "crumb",
		href: host.listHref() ?? undefined,
	});
	items.push({
		name: "view",
		label: host.switcher.view().label,
		zone: "left",
		component: ViewSwitcher,
		props: { host: host.switcher },
	});
	if (host.starsLoaded()) {
		items.push({
			name: "favourite",
			...favouriteWording(host.favourited()),
			zone: "left",
			display: "button",
			palette: false,
			run: () => host.toggleFavourite(),
		});
	}
	items.push({
		name: "new",
		label: __("Create"),
		icon: "lucide-plus",
		display: "button",
		props: { variant: "solid" },
		right: "create",
		palette: false,
		asks: ["dialog"],
		run: () => host.create(),
	});
	return items;
}

export function projectListHeader(
	resolved: ResolvedItem<HeaderItem>[],
	allows: (item: HeaderItem) => boolean,
) {
	return projectHeader(hidingDenied(resolved, allows), HEADER_BUDGET, PINNED_CONTROLS);
}
