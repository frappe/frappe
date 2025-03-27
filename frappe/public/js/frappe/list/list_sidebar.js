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

		this.sidebar = $('<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.setup_list_filter();
		this.setup_list_group_by();
		this.setup_collapsible();

		// do not remove
		// used to trigger custom scripts
		$(document).trigger("list_sidebar_setup");

		if (
			this.list_view.list_view_settings &&
			this.list_view.list_view_settings.disable_sidebar_stats
		) {
			this.sidebar.find(".list-tags").remove();
		} else {
			this.sidebar.find(".list-stats").on("show.bs.dropdown", (e) => {
				this.reload_stats();
			});
		}

		if (frappe.user.has_role("System Manager")) {
			this.add_insights_banner();
			this.add_crm_banner();
			this.add_helpdesk_banner();
		}
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
			section_title: this.page.sidebar.find(".save-filter-section .sidebar-label"),
		});
	}

	setup_collapsible() {
		// tags and save filter sections should be collapsible
		let sections = [
			["tags-section", "list-tags"],
			["save-filter-section", "list-filters"],
			["filter-section", "list-group-by"],
		];

		for (let s of sections) {
			this.page.sidebar.find(`.${s[0]} .sidebar-label`).on("click", () => {
				let list_tags = this.page.sidebar.find("." + s[1]);
				let icon = "#es-line-down";
				list_tags.toggleClass("hide");
				if (list_tags.hasClass("hide")) {
					icon = "#es-line-right-chevron";
				}
				this.page.sidebar.find(`.${s[0]} .es-line use`).attr("href", icon);
			});
		}
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

	get_stats() {
		var me = this;

		let dropdown_options = me.sidebar.find(".list-stats-dropdown .stat-result");
		this.set_loading_state(dropdown_options);

		frappe.call({
			method: "frappe.desk.reportview.get_sidebar_stats",
			type: "GET",
			args: {
				stats: me.stats,
				doctype: me.doctype,
				// wait for list filter area to be generated before getting filters, or fallback to default filters
				filters:
					(me.list_view.filter_area
						? me.list_view.get_filters_for_args()
						: me.default_filters) || [],
			},
			callback: function (r) {
				let stats = (r.message.stats || {})["_user_tags"] || [];
				me.render_stat(stats);
				let stats_dropdown = me.sidebar.find(".list-stats-dropdown");
				frappe.utils.setup_search(stats_dropdown, ".stat-link", ".stat-label");
			},
		});
	}

	set_loading_state(dropdown) {
		dropdown.html(`<div>
			<div class="empty-state">
				${__("Loading...")}
			</div>
		</div>`);
	}

	render_stat(stats) {
		let args = {
			stats: stats,
			label: __("Tags"),
		};

		let tag_list = $(frappe.render_template("list_sidebar_stat", args)).on(
			"click",
			".stat-link",
			(e) => {
				let fieldname = $(e.currentTarget).attr("data-field");
				let label = $(e.currentTarget).attr("data-label");
				let condition = "like";
				let existing = this.list_view.filter_area.filter_list.get_filter(fieldname);
				if (existing) {
					existing.remove();
				}
				if (label == "No Tags") {
					label = "%,%";
					condition = "not like";
				}
				this.list_view.filter_area.add(this.doctype, fieldname, condition, label);
			}
		);

		this.sidebar.find(".list-stats-dropdown .stat-result").html(tag_list);
	}

	reload_stats() {
		this.sidebar.find(".stat-link").remove();
		this.sidebar.find(".stat-no-records").remove();
		this.get_stats();
	}

	add_banner(message, link, cta) {
		try {
			this.banner = $(`
				<div class="sidebar-section">
					${message} <a href="${link}" target="_blank" style="color: var(--text-color)">${cta} &rarr; </a>
				</div>
			`).appendTo(this.sidebar);
		} catch (error) {
			console.error(error);
		}
	}

	add_insights_banner() {
		if (this.list_view.view != "Report") {
			return;
		}

		if (localStorage.getItem("show_insights_banner") == "false") {
			return;
		}

		const message = __("Get more insights with");
		const link = "https://frappe.io/s/insights";
		const cta = "Frappe Insights";
		this.add_banner(message, link, cta);
	}

	add_crm_banner() {
		if (this.list_view.meta.module != "CRM" || this.list_view.view != "List") {
			return;
		}

		const message = "";
		const link =
			"https://frappe.io/crm?utm_source=crm-sidebar&utm_medium=sidebar&utm_campaign=frappe-ad";
		const cta = __("Switch to Frappe CRM for smarter sales");
		this.add_banner(message, link, cta);
	}

	add_helpdesk_banner() {
		if (this.list_view.meta.module != "Support" || this.list_view.view != "List") {
			return;
		}

		const message = "";
		const link =
			"https://frappe.io/helpdesk?utm_source=support-sidebar&utm_medium=sidebar&utm_campaign=frappe-ad";
		const cta = __("Upgrade your support experience with Frappe Helpdesk");
		this.add_banner(message, link, cta);
	}
};
