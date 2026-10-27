// The index's Recent, as boot lists them: the person's last list and record addresses, newest first.
import type { Boot } from "@/boot";

export type IndexVisit = NonNullable<Boot["recent"]>[number];

/** The selection key of the visit at `position`; a route can hold any character, so it is not the key. */
export function recentKey(position: number): string {
	return `recent:${position}`;
}
