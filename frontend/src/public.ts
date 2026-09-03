// `@shell`: what a contributed file may import from; `@/` is this app's private alias.
// A doctype URL's shape depends on the prefix, so the builders are published, not the shape.

export {
	isModular,
	routeFor,
	routeForModule,
	urlFor,
	type RouteOptions,
} from "@/router/routeFor";
export type { ContentEntry } from "@/contents";
