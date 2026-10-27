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
export { askReload, registerAfterSave, type AfterSave, type SavedBinding } from "@/afterSave";
export { createPageEngine, FIRST_PAINT_LIMIT_MS, Surface } from "@/pageEngine";
export type {
	BodyItem,
	FrameItem,
	HeaderItem,
	PageApi,
	PageEngine,
	PageEngineSpec,
	Registration,
	SurfaceItem,
	SurfaceVerbs,
} from "@/pageEngine";
