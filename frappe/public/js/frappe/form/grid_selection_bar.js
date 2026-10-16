export default class GridSelectionBar {
	constructor(grid) {
		this.grid = grid;
		this.custom_actions = new Map();
		this.hidden_actions = new Set();
		this.make();
		this.grid.wrapper.on("change", () => this.debounced_refresh());
		this.grid.wrapper.on("change", ".grid-row-check", () => this.refresh());
	}

	add_action({ label, icon, theme, action }) {
		this.custom_actions.set(label, {
			label,
			icon,
			theme,
			onclick: () => action(this.grid.get_selected_children(), this.grid),
		});
	}

	toggle_action(name, show) {
		if (show) {
			this.hidden_actions.delete(name);
		} else {
			this.hidden_actions.add(name);
		}
	}

	refresh() {
		const count = this.grid.get_selected_children().length;
		this.grid.wrapper.toggleClass("grid-has-selection", count > 0);
		this.$label.text(count === 1 ? __("1 row selected") : __("{0} rows selected", [count]));
		this.$select_all.prop("disabled", count === this.grid.data.length);
		this.refresh_pager();
	}

	debounced_refresh = frappe.utils.debounce(() => this.refresh(), 100);

	select_all(checked) {
		this.grid.data.forEach((doc) => (doc.__checked = checked ? 1 : 0));
		this.grid.refresh();
		this.grid.grid_pagination.update_select_all_checkbox();
	}

	go_to_page(step) {
		const pagination = this.grid.grid_pagination;
		pagination.go_to_page(pagination.page_index + step);
		this.refresh_pager();
	}

	delete_rows() {
		const count = this.grid.get_selected_children().length;
		frappe.confirm(__("Are you sure you want to delete {0} rows?", [count]), () =>
			this.grid.delete_rows()
		);
	}

	get_actions() {
		const { grid } = this;
		const can_add_rows = !(grid.cannot_add_rows || grid.df.cannot_add_rows);

		const built_in = {
			edit: grid.frm &&
				grid.meta?.allow_bulk_edit && {
					label: __("Edit"),
					icon: "pen",
					onclick: () => grid.bulk_edit_rows(),
				},
			duplicate: can_add_rows && {
				label: __("Duplicate"),
				icon: "copy",
				onclick: () => grid.duplicate_rows(),
			},
			delete: !grid.df.cannot_delete_rows && {
				label: __("Delete"),
				icon: "trash",
				theme: "red",
				onclick: () => this.delete_rows(),
			},
		};

		const visible = Object.entries(built_in)
			.filter(([name, item]) => item && !this.hidden_actions.has(name))
			.map(([, item]) => item);
		return [
			...visible,
			...this.custom_actions.values(),
			{
				label: __("Select All"),
				icon: "list-checks",
				condition: () =>
					frappe.is_mobile() && grid.get_selected_children().length < grid.data.length,
				onclick: () => this.select_all(true),
			},
		];
	}

	refresh_pager() {
		const { page_index, page_length } = this.grid.grid_pagination;
		const total_pages = Math.ceil(this.grid.data.length / page_length);

		this.$pager.toggle(total_pages > 1);
		this.$page.text(__("{0} of {1}", [page_index, total_pages]));
		this.$prev.prop("disabled", page_index <= 1);
		this.$next.prop("disabled", page_index >= total_pages);
	}

	make() {
		this.$label = $(`<span class="grid-selection-label" dir="auto"></span>`);
		this.$select_all = this.make_button({
			label: __("Select All"),
			css_class: "grid-selection-select-all",
			onclick: () => this.select_all(true),
		});

		this.$wrapper = $(`<div class="grid-selection-bar"></div>`)
			.append(
				$(`<div class="grid-selection-summary"></div>`).append(
					$(`<input type="checkbox" class="grid-selection-check" checked disabled>`),
					this.$label
				),
				this.make_pager(),
				$(`<div class="grid-selection-actions"></div>`).append(
					frappe.ui.dropdown({
						button: { icon: "ellipsis", variant: "ghost", tooltip: __("Actions") },
						options: () => this.get_actions(),
						side: "top",
						align: "start",
					}),
					frappe.ui.divider({
						orientation: "vertical",
						flex_item: true,
						css_class: "grid-selection-divider",
					}),
					this.$select_all,
					this.make_button({
						icon: "x",
						tooltip: __("Clear selection"),
						onclick: () => this.select_all(false),
					})
				)
			)
			.appendTo(this.grid.wrapper.find(".grid-selection-scope"));
	}

	make_pager() {
		const rtl = frappe.utils.is_rtl();
		this.$page = $(`<span class="grid-selection-page"></span>`);
		this.$prev = this.make_button({
			icon: rtl ? "chevron-right" : "chevron-left",
			tooltip: __("Previous page"),
			onclick: () => this.go_to_page(-1),
		});
		this.$next = this.make_button({
			icon: rtl ? "chevron-left" : "chevron-right",
			tooltip: __("Next page"),
			onclick: () => this.go_to_page(1),
		});

		this.$pager = $(`<div class="grid-selection-pager"></div>`).append(
			this.$prev,
			this.$page,
			this.$next
		);
		return this.$pager;
	}

	make_button(opts) {
		return frappe.ui.button({ variant: "ghost", ...opts });
	}
}
