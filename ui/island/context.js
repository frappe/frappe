// The ambient context a host injects into every island: what the page knows or
// can do that the island's shadow root cannot reach for itself.
//
// The key lives here, next to its reader. `mountVueIsland` provides under it.

import { inject } from "vue";

/**
 * @typedef {Object} IslandHost
 * @property {string} [locale]
 * @property {string|null} [timezone]
 * @property {string|null} [user]
 * @property {string} [base_url]
 * @property {(route: string) => void} [navigate]  route the host to one of its
 *           own pages
 * @property {string} [theme]  the host's live theme, added by `mountVueIsland`
 */

/**
 * Injection key for the host context. `Symbol.for`, so an island that carries
 * its own copy of this module still reads what the host provided.
 */
export const hostKey = Symbol.for("frappe:island-host");

/**
 * The host's context, inside an island component.
 *
 * An empty context is a working context. Every field is optional, so a component
 * still renders where nothing is provided, such as in a unit test or under a
 * host that predates the field it wants.
 *
 * @returns {IslandHost}
 */
export function useHost() {
	return inject(hostKey, {});
}
