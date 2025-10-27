// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// library to mange assets (js, css, models, html) etc in the app.
// will try and get from localStorage if latest are available
// depends on frappe.versions to manage versioning

frappe.require = function (items, callback) {
	if (typeof items === "string") {
		items = [items];
	}
	items = items.map((item) => frappe.assets.bundled_asset(item));

	return new Promise((resolve) => {
		frappe.assets.execute(items, () => {
			resolve();
			callback && callback();
		});
	});
};

class AssetManager {
	constructor() {
		this._executed = [];
		this._handlers = {
			js: function (txt) {
				frappe.dom.eval(txt);
			},
			css: function (txt) {
				frappe.dom.set_style(txt);
			},
		};
	}
	check() {
		// if version is different then clear localstorage
		if (window._version_number != localStorage.getItem("_version_number")) {
			this.clear_local_storage();
			console.log("Cleared App Cache.");
		}

		if (localStorage._last_load) {
			let not_updated_since = new Date() - new Date(localStorage._last_load);
			// Evict cache every 2 days
			// Evict cache if page is reloaded within 10 seconds. Which could be user trying to
			// refresh if things feel broken.
			if ((not_updated_since < 5000 && is_reload()) || not_updated_since > 2 * 86400000) {
				this.clear_local_storage();
			}
		} else {
			this.clear_local_storage();
		}

		this.init_local_storage();
	}

	init_local_storage() {
		localStorage._last_load = new Date();
		localStorage._version_number = window._version_number;
		if (frappe.boot) localStorage.metadata_version = frappe.boot.metadata_version;
	}

	clear_local_storage() {
		["_last_load", "_version_number", "metadata_version", "page_info", "last_visited"].forEach(
			(key) => localStorage.removeItem(key)
		);

		// clear assets
		for (let key in localStorage) {
			if (
				key.startsWith("_page:") ||
				key.startsWith("_doctype:") ||
				key.startsWith("preferred_breadcrumbs:")
			) {
				localStorage.removeItem(key);
			}
		}
		console.log("localStorage cleared");
	}

	eval_assets(path, content) {
		if (!this._executed.includes(path)) {
			this._handlers[this.extn(path)](content);
			this._executed.push(path);
		}
	}

	execute(items, callback) {
		// this is virtual page load, only get the the source
		let me = this;

		const version_string =
			frappe.boot.developer_mode || window.dev_server ? Date.now() : window._version_number;

		let fetched_assets = {};
		async function fetch_item(path) {
			let url = new URL(path, window.location.origin);

			// Add the version to the URL to bust the cache for non-bundled assets
			if (
				url.hostname === window.location.hostname &&
				!path.includes(".bundle.") &&
				!url.searchParams.get("v")
			) {
				url.searchParams.append("v", version_string);
			}
			const response = await fetch(url.toString());
			fetched_assets[path] = await response.text();
		}

		frappe.dom.freeze();
		const fetch_promises = items.map(fetch_item);
		Promise.all(fetch_promises).then(() => {
			items.forEach((path) => {
				let body = fetched_assets[path];
				me.eval_assets(path, body);
			});
			frappe.dom.unfreeze();
			callback?.();
		});
	}

	extn(src) {
		if (src.indexOf("?") != -1) {
			src = src.split("?").slice(-1)[0];
		}
		return src.split(".").slice(-1)[0];
	}

	bundled_asset(path, is_rtl = null) {
		if (!path.startsWith("/assets") && path.includes(".bundle.")) {
			if (path.endsWith(".css") && is_rtl) {
				path = `rtl_${path}`;
			}
			path = frappe.boot.assets_json[path] || path;
			return path;
		}
		return path;
	}
}

function is_reload() {
	try {
		return window.performance
			?.getEntriesByType("navigation")
			.map((nav) => nav.type)
			.includes("reload");
	} catch (e) {
		// Safari probably
		return true;
	}
}

frappe.assets = new AssetManager();
