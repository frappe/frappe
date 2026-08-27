// The ambient context desk injects into every island: what the page knows or
// can do that the island's shadow root cannot reach for itself.
//
// Desk captures it when the island mounts, which is what "where the reader came
// from" means. The island unmounts whenever the reader leaves the page, so a new
// visit brings a new trail.

import { inject } from "vue";

import { deskKey } from "./mount.js";

/**
 * The host's context, inside an island component.
 *
 * An empty context is a working context: every field is optional, so a component
 * still renders where nothing is provided — a unit test, or a host that predates
 * the field it wants.
 *
 * @returns {import('./mount.js').IslandDesk}
 */
export function useDesk() {
	return inject(deskKey, {});
}
