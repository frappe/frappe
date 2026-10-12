/** List saved layouts with edit, duplicate, and delete actions. */
export default class ManageLayoutsDialog {
	constructor({ list_filter }) {
		this.list_filter = list_filter;
		this.list_view = list_filter.list_view;
		this.make_dialog();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Manage Layouts"),
			size: "medium",
			fields: [{ fieldtype: "HTML", fieldname: "layouts_html" }],
		});

		// Add some min-width which actually works
		this.dialog.$wrapper.find(".modal-content").css({ "min-height": "32vh" });
		// the form's first-section padding adds a gap above the list; it outranks a utility class
		this.dialog.$wrapper.find(".form-section > .section-body").css({ "padding-top": 0 });

		this.render_list();
		this.bind_events();
		this.dialog.show();
	}

	get_layouts() {
		return this.list_filter.filters || [];
	}

	render_list() {
		const layouts = this.get_layouts();
		const $wrapper = this.dialog.get_field("layouts_html").$wrapper;

		if (!layouts.length) {
			$wrapper.html(
				frappe.ui.empty_state.html({
					icon: "layout-list",
					title: __("No saved layouts yet"),
					description: __("Layouts you create will show up here."),
				})
			);
			return;
		}

		const rows = layouts.map((layout) => this.get_row_html(layout)).join("");
		$wrapper.html(`<div class="layout-manage-list">${rows}</div>`);
	}

	get_row_html(layout) {
		const can_edit = this.list_filter.can_edit_layout(layout);
		const is_global = !layout.for_user;
		let scope_label = is_global ? __("Global") : __("Personal");
		if (layout.is_standard) scope_label = __("Standard");
		const esc = frappe.utils.escape_html;
		const action = (icon, title, css_class, disabled = false) =>
			frappe.ui.button.html({ icon, title, css_class, disabled, variant: "ghost" });

		return `
			<div class="layout-manage-row flex items-center justify-between py-2 border-b"
				data-name="${esc(layout.name)}">
				<div class="min-w-0 flex gap-1 items-center pe-2">
					<div class="truncate text-base-semibold text-ink-gray-8" title="${esc(layout.filter_name)}">
						${esc(this.list_filter.get_layout_label(layout))}
					</div>
					${frappe.ui.badge.html({ label: scope_label })}
				</div>
				<div class="flex shrink-0 gap-1">
					${action("pencil", __("Edit"), "layout-action-edit", !can_edit)}
					${action("copy", __("Duplicate"), "layout-action-duplicate")}
					${action("trash", __("Delete"), "layout-action-delete", !can_edit)}
				</div>
			</div>
		`;
	}

	bind_events() {
		const $wrapper = this.dialog.get_field("layouts_html").$wrapper;

		$wrapper.on("click", ".layout-action-edit", (e) => {
			e.preventDefault();
			const layout = this.get_layout_from_row(e.currentTarget);
			if (!layout || !this.list_filter.can_edit_layout(layout)) return;
			this.dialog.hide();
			this.list_filter.open_layout_dialog(layout);
		});

		$wrapper.on("click", ".layout-action-duplicate", (e) => {
			e.preventDefault();
			const layout = this.get_layout_from_row(e.currentTarget);
			if (!layout) return;
			this.dialog.hide();
			this.list_filter.open_layout_dialog(null, { duplicate_from: layout });
		});

		$wrapper.on("click", ".layout-action-delete", (e) => {
			e.preventDefault();
			const layout = this.get_layout_from_row(e.currentTarget);
			if (!layout || !this.list_filter.can_edit_layout(layout)) return;
			this.confirm_delete(layout);
		});
	}

	get_layout_from_row(button) {
		const name = $(button).closest(".layout-manage-row").data("name");
		return (this.list_filter.filters || []).find((row) => row.name === name);
	}

	confirm_delete(layout) {
		frappe.confirm(
			__("Delete layout <strong>{0}</strong>?", [
				frappe.utils.escape_html(layout.filter_name),
			]),
			() => {
				this.list_filter.delete_layout(layout).then(() => {
					frappe.show_alert({
						message: __("Layout <b>{0}</b> deleted", [
							frappe.utils.escape_html(layout.filter_name),
						]),
						indicator: "green",
					});
					this.render_list();
					this.list_filter.setup_layout_menu({ refetch: true });
				});
			}
		);
	}
}
