// Which apps the switcher and the rail menu list, and in what order.
import type { PlacesApp } from "./palettePlaces";

/** The apps the person has not hidden: the current one first, then the last opened, then the rest as `/apps` has them. */
export function switchOrder(apps: PlacesApp[], current: string | null, used: string[]): PlacesApp[] {
	const rank = (app: PlacesApp) => (app.app === current ? -1 : used.includes(app.app) ? used.indexOf(app.app) : used.length);
	return apps.filter((app) => !app.hidden).sort((a, b) => rank(a) - rank(b));
}

/** The rail menu's apps: those the person has not hidden, as `/apps` has them, less the current one. */
export function menuApps(apps: PlacesApp[], current: string | null): PlacesApp[] {
	return apps.filter((app) => !app.hidden && app.app !== current);
}
