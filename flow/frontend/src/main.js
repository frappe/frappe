import { createApp } from "vue";
import App from "@/App.vue";
import "@/index.css";

const PANEL_WIDTH = 420;

// Slide-in overlay panel injected into the Frappe desk. The Vue app (with real
// frappe-ui components) mounts inside #flow-root; all bundle CSS is scoped to
// that id so nothing leaks onto the desk.
class FlowPanel {
	constructor() {
		this.visible = false;
		this._mount();
		this._syncTheme();
		this._registerShortcut();
	}

	_mount() {
		this.root = document.createElement("div");
		this.root.id = "flow-root";
		Object.assign(this.root.style, {
			position: "fixed",
			top: "0",
			right: "0",
			width: `${PANEL_WIDTH}px`,
			height: "100vh",
			zIndex: "1040",
			transform: "translateX(100%)",
			transition: "transform 0.22s ease",
			boxShadow: "-2px 0 16px rgba(0, 0, 0, 0.08)",
		});
		document.body.appendChild(this.root);

		this.app = createApp(App, { onClose: () => this.hide() });
		this.app.mount(this.root);
	}

	// Mirror the desk's light/dark theme onto the panel root so scoped tokens
	// resolve to the right palette.
	_syncTheme() {
		const apply = () => {
			const theme = document.documentElement.getAttribute("data-theme") || "light";
			this.root.setAttribute("data-theme", theme);
		};
		apply();
		new MutationObserver(apply).observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["data-theme"],
		});
	}

	_registerShortcut() {
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+m",
			action: () => this.toggle(),
			description: __("Toggle AI panel"),
			ignore_inputs: false,
		});
	}

	show() {
		this.visible = true;
		this.root.style.transform = "translateX(0)";
	}

	hide() {
		this.visible = false;
		this.root.style.transform = "translateX(100%)";
	}

	toggle() {
		this.visible ? this.hide() : this.show();
	}
}

frappe.provide("frappe.flow");
$(document).on("app_ready", () => {
	frappe.flow.panel = new FlowPanel();
});
