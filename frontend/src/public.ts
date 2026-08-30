// `@shell` -- the framework's public surface for CONTRIBUTED source.
//
// A contributed file lives in another app's repo but is compiled into this bundle by
// the vite plugin, so it is in the same module graph and can import from here. What
// it must not do is reach in through `@/…`, which is this app's private alias.
//
// It exists for one reason: after #42210 and #42211 a doctype URL has a shape a
// contributed script cannot know -- it depends on the prefix the reader is standing
// in, and whether that app declares `app_modular`. A script that spells one by hand
// gets a 404 on ERPNext and a working link on CRM, which is the worst possible way to
// find out. So the builder is published rather than the shape being documented.
//
// Deliberately small. This is not the record-page `page` surface (maps 1-4) and not a
// second door into the shell: everything here is address arithmetic.

export {
	routeFor,
	routeForModule,
	urlFor,
	type RouteOptions,
} from "@/router/routeFor";
export type { NavigationEntry } from "@/navigation";
