frappe.provide("frappe.ui");

frappe.ui.Sidebar = class Sidebar {
	constructor() {
		this.make_app_switcher();
	}

	make_app_switcher() {
		$(`<div class="app-switcher"
			style="display: flex; justify-content: space-between; margin-top: -5px;">
			<div style="display: flex; align-items: center;">
				<img src="/assets/erpnext/images/erpnext-logo.svg" class="body-sidebar-app-image"
					style="width: 28px;">
				<div class="app-name" style="margin-left: var(--margin-sm);">ERPNext</div>
			</div>
			<div style="display: flex; align-items: center;">
				<svg class="es-icon icon-xs"><use href="#es-line-down"></use></svg>
			</div>
		</div>`).prependTo($(".body-sidebar"));
	}
};
