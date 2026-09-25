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

		this.render_list();
		this.bind_events();
		this.dialog.show();
	}

	get_layouts() {
		return [...(this.list_filter.filters || [])].sort((a, b) =>
			(a.filter_name || "").localeCompare(b.filter_name || "")
		);
	}

	render_list() {
		const layouts = this.get_layouts();
		const $wrapper = this.dialog.get_field("layouts_html").$wrapper;

		if (!layouts.length) {
			$wrapper.html(
				`<p class="text-muted text-center mb-0">${__("No saved layouts yet.")}</p>`
			);
			return;
		}

		const rows = layouts.map((layout) => this.get_row_html(layout)).join("");
		$wrapper.html(`<div class="layout-manage-list">${rows}</div>`);
	}

	get_row_html(layout) {
		const can_edit = this.list_filter.can_edit_layout(layout);
		const is_global = !layout.for_user;
		const scope_label = is_global ? __("Global") : __("Personal");
		const edit_disabled = can_edit ? "" : "disabled";
		const delete_disabled = can_edit ? "" : "disabled";
		const esc = frappe.utils.escape_html;

		return `
			<div class="layout-manage-row d-flex justify-content-between align-items-center py-2 border-bottom"
				data-name="${esc(layout.name)}">
				<div class="layout-manage-row-label min-width-0 pr-2">
					<div class="ellipsis font-weight-bold text-sm" title="${esc(layout.filter_name)}">
						${esc(__(layout.filter_name))}
					</div>
					<div class="text-muted" style="font-size: var(--text-xs)">${esc(scope_label)}</div>
				</div>
				<div class="layout-manage-row-actions d-flex flex-shrink-0" style="gap: 4px;">
					<button type="button" class="btn btn-default btn-xs btn-icon layout-action-edit"
						${edit_disabled} title="${esc(__("Edit"))}" aria-label="${esc(__("Edit"))}">
						${frappe.utils.icon("pencil", "xs")}
					</button>
					<button type="button" class="btn btn-default btn-xs btn-icon layout-action-duplicate"
						title="${esc(__("Duplicate"))}" aria-label="${esc(__("Duplicate"))}">
						${frappe.utils.icon("copy", "xs")}
					</button>
					<button type="button" class="btn btn-default btn-xs btn-icon layout-action-delete"
						${delete_disabled} title="${esc(__("Delete"))}" aria-label="${esc(__("Delete"))}">
						${frappe.utils.icon("trash", "xs")}
					</button>
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
