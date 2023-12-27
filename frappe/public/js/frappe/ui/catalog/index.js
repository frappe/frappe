import { createApp } from "vue";
import LinkCatalogVue from "./LinkCatalog.vue";
import { getLayoutAdapter } from "./LinkCatalogAdapter";
import { Bus, CatalogOptions } from "./link_catalog_common";

// Use this class with:
// import { LinkCatalog } from "frappe/public/js/frappe/ui/catalog";

export class LinkCatalog {
	constructor({ layout = null, frm = null, dialog = null, options = null, wrapper = null }) {
		if (!options) {
			throw new Error("Missing argument: options");
		}
		this.options = new CatalogOptions();
		Object.assign(this.options, options);

		this.layout = frm || dialog || layout || window.cur_frm;
		if (!this.layout) {
			throw new Error("Missing argument: Must provide one of: layout, frm, dialog");
		}

		this.wrapper = wrapper;
		if (!this.wrapper) {
			throw new Error("Missing argument: wrapper");
		}
		if (window.jQuery && this.wrapper instanceof window.jQuery) {
			this.wrapper = this.wrapper[0];
		}

		this.bus = new Bus();
		this.layoutAdapter = getLayoutAdapter(this.layout, this.options);

		this.make();
	}

	make() {
		const app = createApp(LinkCatalogVue);
		SetVueGlobals(app);
		app.provide("bus", this.bus);
		app.provide("frm", this.layout);
		app.provide("layoutAdapter", this.layoutAdapter);
		app.provide("options", this.options);
		app.mount(this.wrapper);
	}

	refresh() {
		this.bus?.emit("refresh");
	}
}
