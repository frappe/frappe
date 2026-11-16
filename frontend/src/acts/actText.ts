import type { ActText } from "./text/types";

type Sidecar = Record<string, ActText>;

const SIDECARS: Record<string, () => Promise<{ default: Sidecar }>> = {
	shell: () => import("./text/shell"),
	header: () => import("./text/header"),
	quickActions: () => import("./text/quickActions"),
	tabs: () => import("./text/tabs"),
	record: () => import("./text/record"),
	list: () => import("./text/list"),
	cards: () => import("./text/cards"),
	editor: () => import("./text/editor"),
	canvas: () => import("./text/canvas"),
	fields: () => import("./text/fields"),
	settings: () => import("./text/settings"),
	customize: () => import("./text/customize"),
	danger: () => import("./text/danger"),
	layouts: () => import("./text/layouts"),
};

const loaded = new Map<string, Sidecar>();
const loading = new Map<string, Promise<Sidecar>>();

/** The surface's sidecar once it has loaded; no surface has one before its first `loadText`. */
export function loadedText(surface: string): Sidecar | undefined {
	return loaded.get(surface);
}

/** Loads the surface's sidecar on first use; a surface with none (a script's or an app's) gives an empty one. */
export function loadText(surface: string): Promise<Sidecar> {
	const held = loading.get(surface);
	if (held) return held;
	const load = SIDECARS[surface]?.();
	const pending = (load ? load.then((module) => module.default) : Promise.resolve({})).then((sidecar) => {
		loaded.set(surface, sidecar);
		return sidecar;
	});
	loading.set(surface, pending);
	pending.catch(() => loading.delete(surface));
	return pending;
}

/** Every surface that has a sidecar; CI reads them all. */
export const TEXT_SURFACES = Object.keys(SIDECARS);
