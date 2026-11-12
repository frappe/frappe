// The list page's header row: its built-in items, and how the engine's list becomes the row.
import { hidingDenied, projectHeader } from "@/pageEngine";
import type { ResolvedItem } from "@/pageEngine/surface";
import type { HeaderItem } from "@/pageEngine/types";
import { __ } from "@/i18n";
import { favouriteWording } from "@/pages/favourite/favouriteWording";

// Create and every control a script adds; the rest go in `⋯`.
const HEADER_BUDGET = 3;
// Create keeps its slot whatever a script adds, as Save does on the record page.
const PINNED_CONTROLS = ["new"];

export interface ListHeaderHost {
	doctype: string;
	/** The doctype's module, once its meta is in. */
	module: () => { label: string; href?: string } | null;
	/** The saved view's name and the plain list's address; a plain list has no view crumb. */
	view: () => { label: string; href: string } | null;
	/** False until a list settings read says what is starred. */
	starsLoaded: () => boolean;
	favourited: () => boolean;
	toggleFavourite: () => unknown;
	create: () => unknown;
}

/** Module crumb, doctype crumb, the view and the star on the left; Create on the right, `⋯` empty. */
export function listHeaderItems(host: ListHeaderHost): HeaderItem[] {
	const module = host.module();
	const view = host.view();
	const items: HeaderItem[] = [];
	if (module) items.push({ name: "module", zone: "left", display: "crumb", ...module });
	items.push({
		name: "doctype",
		label: host.doctype,
		zone: "left",
		display: "crumb",
		href: view?.href,
	});
	if (view) items.push({ name: "view", label: view.label, zone: "left", display: "crumb" });
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
