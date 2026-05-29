import { createApp } from "vue";
import AiPanelComponent from "./frappe/ai/AiPanel.vue";

class AiPanel {
	constructor() {
		this.visible = false;
		this._mount();
		this._register_shortcut();
	}

	_mount() {
		this.$wrapper = $(`
			<div id="ai-panel-wrapper" style="
				position: fixed;
				top: 0;
				right: 0;
				width: 400px;
				height: 100vh;
				z-index: 1040;
				box-shadow: var(--shadow-lg, -2px 0 8px rgba(0,0,0,0.1));
				transform: translateX(100%);
				transition: transform 0.2s ease;
				display: flex;
				flex-direction: column;
			"/>
		`).appendTo("body");

		const app = createApp(AiPanelComponent, {
			onClose: () => this.hide(),
		});
		SetVueGlobals(app);
		app.mount(this.$wrapper.get(0));
	}

	_register_shortcut() {
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+m",
			action: () => this.toggle(),
			description: __("Toggle AI panel"),
			ignore_inputs: false,
		});
	}

	show() {
		this.visible = true;
		this.$wrapper.css("transform", "translateX(0)");
	}

	hide() {
		this.visible = false;
		this.$wrapper.css("transform", "translateX(100%)");
	}

	toggle() {
		this.visible ? this.hide() : this.show();
	}
}

frappe.provide("frappe.ai");

$(document).on("app_ready", () => {
	frappe.ai.panel = new AiPanel();
});
