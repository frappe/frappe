// The index's apps, as boot lists them: one tile each, in the order boot gives.
import type { Boot } from "@/boot";

export type IndexApp = NonNullable<Boot["apps"]>[number];

/** The apps whose title holds the query, any case; with no query, the apps the person has not hidden. */
export function matching(apps: IndexApp[], query: string): IndexApp[] {
	const needle = query.trim().toLowerCase();
	return needle
		? apps.filter((app) => app.title.toLowerCase().includes(needle))
		: apps.filter((app) => !app.hidden);
}

/** How many tiles the unfiltered grid draws: the apps not hidden, and "Get more apps" when boot offers it. */
export function unfilteredTiles(apps: IndexApp[], moreApps?: string | null): number {
	return matching(apps, "").length + (moreApps ? 1 : 0);
}
