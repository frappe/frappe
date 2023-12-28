// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import ListFilter from "./list_filter";
frappe.provide("frappe.views");

// opts:
// stats = list of fields
// doctype
// parent

frappe.views.ListSidebar = class ListSidebar {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		var sidebar_content = frappe.render_template("list_sidebar", { doctype: this.doctype });

		this.sidebar = $('<div class="list-sidebar"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.setup_list_filter();
		this.setup_list_group_by();

		// do not remove
		// used to trigger custom scripts
		$(document).trigger("list_sidebar_setup");

		this.add_insights_banner();
	}

	setup_views() {
		var show_list_link = false;

		if (frappe.views.calendar[this.doctype]) {
			this.sidebar.find('.list-link[data-view="Calendar"]').removeClass("hide");
			this.sidebar.find('.list-link[data-view="Gantt"]').removeClass("hide");
			show_list_link = true;
		}
		//show link for kanban view
		this.sidebar.find('.list-link[data-view="Kanban"]').removeClass("hide");
		if (this.doctype === "Communication" && frappe.boot.email_accounts.length) {
			this.sidebar.find('.list-link[data-view="Inbox"]').removeClass("hide");
			show_list_link = true;
		}

		if (frappe.treeview_settings[this.doctype] || frappe.get_meta(this.doctype).is_tree) {
			this.sidebar.find(".tree-link").removeClass("hide");
		}

		this.current_view = "List";
		var route = frappe.get_route();
		if (route.length > 2 && frappe.views.view_modes.includes(route[2])) {
			this.current_view = route[2];

			if (this.current_view === "Kanban") {
				this.kanban_board = route[3];
			} else if (this.current_view === "Inbox") {
				this.email_account = route[3];
			}
		}

		// disable link for current view
		this.sidebar
			.find('.list-link[data-view="' + this.current_view + '"] a')
			.attr("disabled", "disabled")
			.addClass("disabled");

		//enable link for Kanban view
		this.sidebar
			.find('.list-link[data-view="Kanban"] a, .list-link[data-view="Inbox"] a')
			.attr("disabled", null)
			.removeClass("disabled");

		// show image link if image_view
		if (this.list_view.meta.image_field) {
			this.sidebar.find('.list-link[data-view="Image"]').removeClass("hide");
			show_list_link = true;
		}

		if (
			this.list_view.settings.get_coords_method ||
			(this.list_view.meta.fields.find((i) => i.fieldname === "latitude") &&
				this.list_view.meta.fields.find((i) => i.fieldname === "longitude")) ||
			this.list_view.meta.fields.find(
				(i) => i.fieldname === "location" && i.fieldtype == "Geolocation"
			)
		) {
			this.sidebar.find('.list-link[data-view="Map"]').removeClass("hide");
			show_list_link = true;
		}

		if (show_list_link) {
			this.sidebar.find('.list-link[data-view="List"]').removeClass("hide");
		}
	}

	setup_reports() {
		// add reports linked to this doctype to the dropdown
		var me = this;
		var added = [];
		var dropdown = this.page.sidebar.find(".reports-dropdown");
		var divider = false;

		var add_reports = function (reports) {
			$.each(reports, function (name, r) {
				if (!r.ref_doctype || r.ref_doctype == me.doctype) {
					var report_type =
						r.report_type === "Report Builder"
							? `List/${r.ref_doctype}/Report`
							: "query-report";

					var route = r.route || report_type + "/" + (r.title || r.name);

					if (added.indexOf(route) === -1) {
						// don't repeat
						added.push(route);

						if (!divider) {
							me.get_divider().appendTo(dropdown);
							divider = true;
						}

						$(
							'<li><a href="#' + route + '">' + __(r.title || r.name) + "</a></li>"
						).appendTo(dropdown);
					}
				}
			});
		};

		// from reference doctype
		if (this.list_view.settings.reports) {
			add_reports(this.list_view.settings.reports);
		}

		// Sort reports alphabetically
		var reports =
			Object.values(frappe.boot.user.all_reports).sort((a, b) =>
				a.title.localeCompare(b.title)
			) || [];

		// from specially tagged reports
		add_reports(reports);
	}

	setup_list_filter() {
		this.list_filter = new ListFilter({
			wrapper: this.page.sidebar.find(".list-filters"),
			doctype: this.doctype,
			list_view: this.list_view,
		});
	}

	setup_kanban_boards() {
		const $dropdown = this.page.sidebar.find(".kanban-dropdown");
		frappe.views.KanbanView.setup_dropdown_in_sidebar(this.doctype, $dropdown);
	}

	setup_keyboard_shortcuts() {
		this.sidebar.find(".list-link > a, .list-link > .btn-group > a").each((i, el) => {
			frappe.ui.keys.get_shortcut_group(this.page).add($(el));
		});
	}

	setup_list_group_by() {
		this.list_group_by = new frappe.views.ListGroupBy({
			doctype: this.doctype,
			sidebar: this,
			list_view: this.list_view,
			page: this.page,
		});
	}

	add_insights_banner() {
		try {
			if (this.list_view.view != "Report") {
				return;
			}

			if (localStorage.getItem("show_insights_banner") == "false") {
				return;
			}

			if (this.insights_banner) {
				this.insights_banner.remove();
			}

			const message = "Get more insights with";
			const link = "https://frappe.io/s/insights";
			const cta = "Frappe Insights";

			this.insights_banner = $(`
				<div style="position: relative;">
					<div class="pr-3">
						${message} <a href="${link}" target="_blank" style="color: var(--text-color)">${cta} &rarr; </a>
					</div>
					<div style="position: absolute; top: -1px; right: -4px; cursor: pointer;" title="Dismiss"
						onclick="localStorage.setItem('show_insights_banner', 'false') || this.parentElement.remove()">
						<svg class="icon  icon-sm" style="">
							<use class="" href="#icon-close"></use>
						</svg>
					</div>
				</div>
			`).appendTo(this.sidebar);
		} catch (error) {
			console.error(error);
		}
	}
};
