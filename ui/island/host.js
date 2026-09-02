/**
 * The host loop: what every host of an island does, once.
 *
 *     import { mountIsland } from "@framework/ui/island/host";
 *
 *     const island = await mountIsland("insights.dashboard", el, {
 *         resolve: (name) => ({ js: "/assets/…island.js", css: "/assets/…island.css" }),
 *         desk: { locale, user, navigate },
 *         props: { dashboard: "sales" },
 *         on: { navigate: (intent) => router.push(intent.route) },
 *     });
 *     island.update({ filters });
 *     island.unmount();
 *
 * Import the module a name resolves to, check it exports `mount`, hand the target
 * over to it, and return a handle that survives a re-mount.
 *
 * This module imports nothing — not vue, not frappe-ui, not frappe. Resolution is
 * injected, so desk resolves against `frappe.boot` and a frappe-ui app resolves
 * against an API call, and both run this same loop. See
 * decisions/0008-one-host-loop-two-hosts.md.
 */

/**
 * @typedef {Object} IslandAssets
 * @property {string} js            Module URL to import.
 * @property {string|null} [css]    Stylesheet URL to adopt.
 */

/**
 * @typedef {(name: string) => IslandAssets|Promise<IslandAssets>} IslandResolver
 */

/**
 * @typedef {Object} IslandHandle
 * @property {(props: Object) => void} update
 * @property {() => void} unmount
 */

// target element -> entry. A Map, not a WeakMap, because `reloadChangedIslands`
// must walk what is live on the page.
const islands = new Map();

/**
 * @param {string} name       Island name, as the host's resolver knows it.
 * @param {HTMLElement|JQuery} el
 * @param {{ resolve: IslandResolver, desk?: Object, props?: Object, on?: Object }} options
 * @returns {Promise<IslandHandle>}
 */
export async function mountIsland(name, el, options = {}) {
	const target = resolveElement(el);
	if (typeof options.resolve !== "function") {
		throw new Error("mountIsland: no resolve(name) given");
	}

	const entry = {
		name,
		resolve: options.resolve,
		desk: options.desk || {},
		props: { ...(options.props || {}) },
		on: options.on || {},
		url: null,
		handle: null,
	};

	await loadInto(target, entry);

	return {
		// Both read `entry`, never the handle this call mounted. A re-mount
		// replaces that handle, and the caller keeps this object across it.
		update: (props) => {
			// Kept on the entry too, so a re-mount starts from what the island
			// last showed rather than from the props it first mounted with.
			entry.props = { ...entry.props, ...props };
			entry.handle?.update(props);
		},
		// Tears down this island and only this one. A second call, or a call
		// after something else has taken the target, does nothing.
		unmount: () => {
			if (islands.get(target) === entry) unmountIsland(target);
		},
	};
}

/** Tears down the island in `target`, if any. Safe to call at any time. */
export function unmountIsland(el) {
	const target = el && el.jquery ? el[0] : el;
	const entry = islands.get(target);
	if (!entry) return;
	islands.delete(target);
	entry.handle?.unmount();
}

/**
 * Re-mounts the live islands whose module URL has moved — what a host calls after
 * a rebuild. Teardown is idempotent, so a re-mount in place is safe.
 *
 * @param {IslandResolver} [resolve]  Overrides each entry's own resolver, for a
 *                                    host whose resolution changed with the build.
 * @returns {Promise<void>}
 */
export async function reloadChangedIslands(resolve) {
	for (const [target, entry] of [...islands]) {
		if (!document.body.contains(target)) {
			unmountIsland(target);
			continue;
		}

		if (resolve) entry.resolve = resolve;

		try {
			if ((await entry.resolve(entry.name)).js === entry.url) continue;
		} catch (e) {
			console.error(e);
			continue;
		}

		await loadInto(target, entry).catch((e) =>
			console.error(`island: could not re-mount "${entry.name}"`, e)
		);
	}
}

/**
 * Loads the island `entry.name` names into `target`, and records what it mounted
 * on the entry. A re-mount keeps the entry, so the handle held by whoever mounted
 * the island still reaches the island that is on the page.
 *
 * The target gives up what it holds only once the new module is in hand, so a
 * module that fails to load leaves the island already on screen alone.
 */
async function loadInto(target, entry) {
	const assets = await entry.resolve(entry.name);

	const module = await import(/* @vite-ignore */ assets.js);
	if (typeof module.mount !== "function") {
		throw new Error(`Island "${entry.name}" (${assets.js}) does not export mount()`);
	}

	// Whatever holds the target now goes, this entry included on a re-mount. The
	// handle clears with it, so a mount that fails below leaves nothing dead to
	// call through.
	unmountIsland(target);
	entry.handle = null;

	entry.handle = await module.mount(target, {
		// `desk` is the context key the mount contract reads. See `IslandDesk` in
		// mount.js: the name is the seam, whichever host fills it.
		desk: entry.desk,
		props: entry.props,
		on: entry.on,
		styles: assets.css ? [assets.css] : [],
	});
	entry.url = assets.js;
	islands.set(target, entry);
}

function resolveElement(el) {
	const target = el && el.jquery ? el[0] : el;
	if (!target || !target.appendChild) {
		throw new Error("island: mount target is not an element");
	}
	return target;
}
