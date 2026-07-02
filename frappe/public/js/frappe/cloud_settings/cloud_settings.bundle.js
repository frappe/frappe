import { createApp } from "vue";
import { createStore } from "./store";
import BillingTab from "./components/BillingTab.vue";
import MarketplaceTab from "./components/MarketplaceTab.vue";
import DomainsTab from "./components/DomainsTab.vue";
import AdvancedTab from "./components/AdvancedTab.vue";

frappe.provide("frappe.ui");

const TABS = [
	{ id: "billing", label: __("Billing"), icon: "wallet", component: BillingTab },
	{
		id: "marketplace",
		label: __("Marketplace"),
		icon: "layout-grid",
		component: MarketplaceTab,
	},
	{ id: "domains", label: __("Domains"), icon: "globe", component: DomainsTab },
	{ id: "advanced", label: __("Advanced"), icon: "sliders-horizontal", component: AdvancedTab },
];

// Reuse the framework's SettingsDialog for the shell (sidebar, header, panels)
// and mount one Vue component into each panel body, sharing a single store.
frappe.ui.CloudSettings = {
	show() {
		if (this.dialog) {
			this.dialog.show();
			return;
		}

		const store = createStore();
		const apps = [];

		this.dialog = new frappe.ui.SettingsDialog({
			title: __("Cloud settings"),
			default_tab: "billing",
			tabs: [
				{
					group: __("Cloud settings"),
					items: TABS.map((tab) => ({
						id: tab.id,
						label: tab.label,
						icon: tab.icon,
						render: (panel) => {
							const app = createApp(tab.component);
							app.provide("store", store);
							app.provide("panel", panel);
							SetVueGlobals(app);
							app.mount(panel.body.get(0));
							apps.push(app);
						},
					})),
				},
			],
		});

		this.dialog.$wrapper.on("hidden.bs.modal", () => {
			apps.forEach((app) => app.unmount());
			this.dialog = null;
		});

		this.dialog.show();
	},
};
