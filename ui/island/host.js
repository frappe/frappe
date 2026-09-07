/**
 * The host loop: what every host of an island does, once.
 *
 *     import { mountIsland } from "@framework/ui/island/host";
 *
 *     const island = mountIsland("insights.dashboard", el, {
 *         resolve: (name) => ({ js: "/assets/…island.js", css: "/assets/…island.css" }),
 *         host: { locale, user, navigate },
 *         props: {
 *             dashboard: "sales",
 *             onNavigate: (route) => router.push(route),
 *             onTitle: (title) => (document.title = title),
 *         },
 *     });
 *     island.update({ filters });
 *     await island.ready;
 *     island.unmount();
 *
 * The loop imports the module a name resolves to, checks that it exports
 * `mount`, hands the target to it, and returns a handle that survives a
 * re-mount.
 *
 * The handle returns at once, before the module loads, so a caller holds what
 * it must later release from the first line. `update` merges into the props the
 * mount starts from. `unmount` cancels a pending load. `ready` reports the load.
 * It resolves with the handle when the island is on the page, and it rejects
 * with what the load threw. A cancelled load resolves, because nothing failed.
 *
 * `props` is Vue's props object: data keys and `on*` listener keys in one flat
 * object, exactly as `h(Component, props)` takes them. A hyphen or a colon in an
 * event name stays quoted. Write `"onUpdate:modelValue"`, not
 * `onUpdateModelValue`, which Vue never resolves.
 *
 * This module imports nothing: not Vue, not frappe-ui, not frappe. Each host
 * injects its resolver. The desk loader resolves against `frappe.boot`, and
 * `<Island>` resolves over an API call. See
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
 * @property {Promise<IslandHandle>} ready
 */

// target element -> entry. One entry per target. A mount into a target replaces
// what holds it. A Map, not a WeakMap, because `reloadChangedIslands` must walk
// what is live on the page.
const islands = new Map();

/**
 * @param {string} name       Island name, as the host's resolver knows it.
 * @param {HTMLElement|JQuery} el
 * @param {{ resolve: IslandResolver, host?: Object, props?: Object }} options
 * @returns {IslandHandle}
 */
export function mountIsland(name, el, options = {}) {
	const target = resolveElement(el);
	if (typeof options.resolve !== "function") {
		throw new Error("mountIsland: no resolve(name) given");
	}

	// The target holds one island. This releases whatever holds it, a pending
	// load included. That load mounts nothing when it lands.
	unmountIsland(target);

	const entry = {
		name,
		resolve: options.resolve,
		host: options.host || {},
		props: { ...(options.props || {}) },
		url: null,
		handle: null,
		loading: false,
		cancelled: false,
	};
	islands.set(target, entry);

	const handle = {
		// Both read `entry`, never the handle a load mounted. A re-mount
		// replaces that handle, and the caller keeps this object across it.
		update: (props) => {
			// The entry keeps the props too, so a pending mount starts from the
			// latest props, and a re-mount starts from what the island last showed.
			entry.props = { ...entry.props, ...props };
			entry.handle?.update(props);
		},
		// Unmounts this island and only this one. A second call does nothing. A
		// call after another mount took the target does nothing.
		unmount: () => {
			if (islands.get(target) === entry) unmountIsland(target);
		},
		ready: null,
	};

	handle.ready = loadInto(target, entry).then(
		() => handle,
		(e) => {
			// The caller cancelled this load and moved on.
			if (entry.cancelled) return handle;
			throw e;
		}
	);

	return handle;
}

/** Unmounts the island in `target`, if any. Safe to call at any time. */
export function unmountIsland(el) {
	const target = el && el.jquery ? el[0] : el;
	const entry = islands.get(target);
	if (!entry) return;
	islands.delete(target);
	entry.cancelled = true;
	entry.handle?.unmount();
	entry.handle = null;
}

/**
 * Re-mounts the live islands whose module URL moved. A host calls this after a
 * rebuild. Unmount is idempotent, so a re-mount in place is safe.
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

		// An entry still loading is about to mount what it resolved. A second
		// load into it would race that one.
		if (entry.loading) continue;

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
 * Loads the island `entry.name` names into `target`, and records the mounted
 * handle on the entry. A re-mount keeps the entry, so the handle the caller
 * holds still reaches the island on the page.
 *
 * The entry releases what it holds only after the new module loads. A module
 * that fails to load leaves the island already on screen alone.
 *
 * A cancelled entry mounts nothing, and drops what it already mounted. The
 * cancel can land at any await, the one inside `mount` included.
 */
async function loadInto(target, entry) {
	entry.loading = true;
	try {
		const assets = await entry.resolve(entry.name);
		if (entry.cancelled) return;

		const module = await import(/* @vite-ignore */ assets.js);
		if (entry.cancelled) return;

		if (typeof module.mount !== "function") {
			throw new Error(`Island "${entry.name}" (${assets.js}) does not export mount()`);
		}

		// The handle clears with the island it names. A mount that fails below
		// then leaves no dead handle to call through.
		entry.handle?.unmount();
		entry.handle = null;

		const handle = await module.mount(target, {
			// `host` is the context key the mount contract reads. See
			// `IslandHost` in context.js. The key is the same whichever host
			// fills it.
			host: entry.host,
			props: entry.props,
			styles: assets.css ? [assets.css] : [],
		});

		if (entry.cancelled) return handle.unmount();
		entry.handle = handle;
		entry.url = assets.js;
	} finally {
		entry.loading = false;
	}
}

function resolveElement(el) {
	const target = el && el.jquery ? el[0] : el;
	if (!target || !target.appendChild) {
		throw new Error("island: mount target is not an element");
	}
	return target;
}
