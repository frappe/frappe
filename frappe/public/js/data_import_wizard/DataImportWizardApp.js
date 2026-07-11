import { createApp } from "vue";
import DataImportWizard from "./DataImportWizard.vue";

/** Mount / remount the Data Import wizard on the form view (replaces std layout UI). */
export default class DataImportWizardApp {
	constructor({ wrapper, frm }) {
		this.wrapper = wrapper;
		this.frm = frm;
		this.mount();
	}

	mount() {
		this.unmount();
		const app = createApp(DataImportWizard, { frm: this.frm });
		SetVueGlobals(app);
		this._instance = app.mount(this.wrapper);
		this._app = app;
	}

	unmount() {
		if (this._app) {
			this._app.unmount();
			this._app = null;
			this._instance = null;
		}
	}

	set_step(step) {
		this._instance?.set_step?.(step);
	}

	refresh_from_frm() {
		this._instance?.sync_from_frm?.();
	}

	bump_ui() {
		this._instance?.bump_ui?.();
	}

	refresh_fix_issues() {
		this._instance?.refresh_fix_issues?.();
	}

	set_preview_tab(tab) {
		this._instance?.set_preview_tab?.(tab);
	}

	set_preview_loading(loading) {
		this._instance?.set_preview_loading?.(loading);
	}
}
