frappe.provide("frappe.ui");

const SKELETON_DELAY = 250;
const SKELETON_MIN_DURATION = 300;
const CACHE_SIZE = 50;

/**
 * @typedef {Object} DetailLoaderOpts
 * @property {(name:string, opts:{silent:boolean})=>Promise} fetch Loads one record; `silent` asks for no error message.
 * @property {(name:string)=>string[]} [get_neighbours] The records beside `name` in the list, loaded early.
 */

/**
 * @typedef {Object} DetailLoaderHandlers
 * @property {()=>void} empty The record is not loaded yet: clear what the last one left below the header.
 * @property {()=>void} skeleton The load is slow: show placeholders.
 * @property {(data:any, opts:{is_refresh:boolean, is_quiet:boolean})=>void} render Draws the record. `is_refresh`: it is on screen already and changed; `is_quiet`: nobody asked for it, so it may wait while the user types.
 * @property {(error:any)=>void} error The first load failed.
 */

/**
 * Loads what the detail pane of a master-detail page shows, so stepping through the list does not
 * flash: a load under 250ms shows no skeleton, a slower one shows it for at least 300ms. The last
 * 50 records stay in memory and show at once when picked again, then load again quietly and draw
 * again only when they changed. The rows beside the shown one load early. Only the latest `show`
 * draws; a late answer for a record left behind only fills the memory. Not in the desk bundle:
 * load it first with `await frappe.require("split_view.bundle.js")`.
 *
 * @example
 * const loader = new frappe.ui.DetailLoader({
 *   fetch: (name, { silent }) => frappe.xcall("app.api.get_record", { name }, "GET", { silent }),
 *   get_neighbours: (name) => pane.get_neighbour_ids(name),
 * });
 * loader.show(name, { empty, skeleton, render, error });
 * // a record changed: loader.forget(name), then loader.refresh() if it is the one shown
 */
frappe.ui.DetailLoader = class DetailLoader {
	/** @param {DetailLoaderOpts} opts */
	constructor(opts) {
		this.opts = opts;
		this.cache = new Map();
		this.pending = new Map();
		this.token = 0;
		this.name = null;
		this.handlers = null;
		this.shown = null;
	}

	/** @param {DetailLoaderHandlers} handlers */
	show(name, handlers) {
		this.cancel();
		this.name = name;
		this.handlers = handlers;
		const cached = this.cache.get(name);
		if (cached) {
			this.draw(cached);
			return this.load(this.fetch(name, { silent: true }));
		}
		handlers.empty();
		this.skeleton_timer = setTimeout(() => this.show_skeleton(), SKELETON_DELAY);
		return this.load(this.pending.get(name) || this.fetch(name));
	}

	/** Loads the shown record again and draws it only if it changed. */
	refresh({ is_quiet = true } = {}) {
		if (!this.name) return Promise.resolve();
		return this.load(this.fetch(this.name, { silent: Boolean(this.shown) }), { is_quiet });
	}

	load(promise, { is_quiet = true } = {}) {
		const token = ++this.token;
		const name = this.name;
		return promise.then(
			(data) => {
				if (token !== this.token) return;
				this.after_skeleton(() => this.draw(data, { is_quiet }));
				this.load_neighbours(name);
			},
			(error) => {
				// a copy on screen stays as it is
				if (token !== this.token || this.shown) return;
				this.after_skeleton(() => this.handlers.error(error));
			}
		);
	}

	draw(data, { is_quiet = true } = {}) {
		const is_refresh = Boolean(this.shown);
		if (is_refresh && JSON.stringify(data) === JSON.stringify(this.shown)) return;
		this.shown = data;
		this.handlers.render(data, { is_refresh, is_quiet });
	}

	show_skeleton() {
		this.skeleton_shown_at = Date.now();
		this.handlers.skeleton();
	}

	after_skeleton(callback) {
		clearTimeout(this.skeleton_timer);
		clearTimeout(this.render_timer);
		const run = () => {
			this.skeleton_shown_at = null;
			callback();
		};
		const wait = this.skeleton_shown_at
			? this.skeleton_shown_at + SKELETON_MIN_DURATION - Date.now()
			: 0;
		if (wait > 0) this.render_timer = setTimeout(run, wait);
		else run();
	}

	fetch(name, { silent = false } = {}) {
		const is_latest = () => this.pending.get(name) === promise;
		const promise = Promise.resolve(this.opts.fetch(name, { silent })).then(
			(data) => {
				// a forgotten or superseded answer is not kept
				if (!is_latest()) return data;
				this.pending.delete(name);
				this.store(name, data);
				return data;
			},
			(error) => {
				if (is_latest()) this.pending.delete(name);
				throw error;
			}
		);
		this.pending.set(name, promise);
		return promise;
	}

	store(name, data) {
		this.cache.delete(name);
		this.cache.set(name, data);
		if (this.cache.size > CACHE_SIZE) this.cache.delete(this.cache.keys().next().value);
	}

	load_neighbours(name) {
		for (const neighbour of this.opts.get_neighbours?.(name) || []) {
			if (!neighbour || this.cache.has(neighbour) || this.pending.has(neighbour)) continue;
			this.fetch(neighbour, { silent: true }).catch(() => {});
		}
	}

	/** The record changed: the next `show` loads it fresh. */
	forget(name) {
		this.cache.delete(name);
		this.pending.delete(name);
	}

	forget_all() {
		this.cache.clear();
		this.pending.clear();
	}

	/** Stops drawing: no answer, skeleton or timer reaches the screen after this. */
	cancel() {
		this.token++;
		clearTimeout(this.skeleton_timer);
		clearTimeout(this.render_timer);
		this.skeleton_shown_at = null;
		this.name = null;
		this.handlers = null;
		this.shown = null;
	}

	destroy() {
		this.cancel();
		this.forget_all();
	}
};
