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
