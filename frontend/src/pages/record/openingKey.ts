// What makes an address a new opening of the new record page: its path and its query, not its hash.
import type { RouteLocationNormalizedLoaded } from "vue-router";

export function openingKey(route: Pick<RouteLocationNormalizedLoaded, "path" | "query">): string {
	return `${route.path}?${JSON.stringify(route.query)}`;
}
