// The index's Favourites, as boot lists them: the person's latest favourite records, newest first.
import type { Boot } from "@/boot";

export type IndexFavourite = NonNullable<Boot["favourites"]>[number];

/** The favourite's selection key, unique on the page. */
export function favouriteKey(favourite: IndexFavourite): string {
	return `favourite:${favourite.doctype}:${favourite.name}`;
}
