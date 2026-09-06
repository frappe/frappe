frappe.provide("frappe.views");

/**
 * The view switcher — one es-dropdown on the page header that lists every
 * view the doctype supports. Rows with variants carry them as a submenu AT
 * ALL TIMES (kanban boards, saved layouts, saved reports, calendars, inbox
 * accounts), so you jump straight to a board or layout from any view instead
 * of switching first and picking after. Variant lists that need a fetch load
 * lazily at hover (menu.js async support). The current view's row is marked
 * selected and shows its active variant as the description line.
 *
 * This replaced three separate header dropdowns: the old switcher, the
 * "Select Kanban" group and the Saved Layouts button.
 */
frappe.views.ListViewSelect = class ListViewSelect {
	constructor(opts) {
		$.extend(this, opts);
		this.set_current_view();
		this.make_switcher();
	}

	set_current_view() {
		this.current_view = "List";
		const route = frappe.get_route();
		const view_name = frappe.utils.to_title_case(route[2] || "");
		if (route.length > 2 && frappe.views.view_modes.includes(view_name)) {
			this.current_view = view_name;

			if (this.current_view === "Kanban") {
				this.kanban_board = route[3];
			} else if (this.current_view === "Inbox") {
				this.email_account = route[3];
			}
		}
	}

	make_switcher() {
		this.$wrapper = $('<div class="custom-btn-group view-switcher"></div>');
		this.$trigger = frappe.ui.button({ css_class: "ellipsis" });
		this.set_trigger_content(this.get_trigger_label());
		this.$wrapper.append(this.$trigger);

		this.dropdown = new frappe.ui.Dropdown({
			trigger: this.$trigger,
			options: () => this.get_view_options(),
		});

		const parent = frappe.is_mobile()
			? this.page.custom_mobile_actions
			: this.page.custom_actions;
		parent.removeClass("hide").append(this.$wrapper);
	}

	// the trigger shows WHERE YOU ARE: the view's icon plus the active
	// variant when one is picked ("Overdue" with the list icon), else the
	// plain view name ("List View")
	get_trigger_label() {
		const route = frappe.get_route();
		switch (this.current_view) {
			case "List": {
				const filter = this.list_view.list_filter;
				const label = filter?.active_layout_label;
				return label && label !== filter?.default_layout_label
					? label
					: this.label_map["List"];
			}
			case "Kanban":
				return this.kanban_board || this.label_map["Kanban"];
			case "Calendar":
				return route[3] && route[3] !== "default" ? route[3] : this.label_map["Calendar"];
			case "Inbox":
				return this.email_account || this.label_map["Inbox"];
			case "Report":
				return route.length > 3 ? this.get_page_name() : this.label_map["Report"];
			default:
				return this.label_map[this.current_view] || this.label_map["List"];
		}
	}

	set_trigger_content(label) {
		frappe.ui.button.dress(this.$trigger, {
			label,
			icon: this.icon_map[this.current_view] || "list",
			icon_right: "chevrons-up-down",
		});
		// mobile collapses the trigger to the view icon alone (label and
		// chevron hide below md; page.scss squares the button)
		this.$trigger.find(".es-button__label").addClass("hidden-xs custom-btn-group-label");
		this.$trigger.children("svg").last().addClass("hidden-xs");
	}

	// called when the active variant changes at runtime (a layout is
	// selected or restored) so the trigger keeps showing the truth
	refresh_trigger() {
		this.set_trigger_content(this.get_trigger_label());
	}

	get_view_options() {
		const views = this.get_views();
		const options = [];

		frappe.views.view_modes.forEach((view) => {
			const config = views[view];
			if (!config || !config.condition) return;

			const label =
				view === "List" && this.doctype === "File"
					? __("File")
					: this.label_map[view] || __(view);
			const item = { label, icon: this.icon_map[view] || "list" };

			// a submenu row doesn't act on click (it opens its panel), so a
			// view with variants always leads with an entry row inside the
			// submenu; a view without variants switches on click
			const submenu = this.get_view_submenu(view, config);
			if (submenu) item.submenu = submenu;
			else if (this.current_view !== view) item.onclick = config.action;

			if (this.current_view === view) {
				item.selected = true;
			}
			options.push(item);
		});

		return options;
	}

	get_views() {
		return {
			List: {
				condition: true,
				action: () => this.set_route("list"),
			},
			Report: {
				condition: true,
				action: () => this.set_route("report"),
			},
			Dashboard: {
				condition: true,
				action: () => this.set_route("dashboard"),
			},
			Calendar: {
				condition:
					frappe.views.calendar[this.doctype] ||
					frappe.get_meta(this.doctype).is_calendar_and_gantt,
				action: () => this.set_route("calendar", "default"),
			},
			Gantt: {
				condition:
					frappe.views.calendar[this.doctype] ||
					frappe.get_meta(this.doctype).is_calendar_and_gantt,
				action: () => this.set_route("gantt"),
			},
			Inbox: {
				condition: this.doctype === "Communication" && frappe.boot.email_accounts.length,
				action: () => this.set_route("inbox"),
			},
			Image: {
				condition: this.list_view.meta.image_field,
				action: () => this.set_route("image"),
			},
			Tree: {
				condition:
					frappe.treeview_settings[this.doctype] ||
					frappe.get_meta(this.doctype).is_tree,
				action: () => this.set_route("tree"),
			},
			Kanban: {
				condition: this.doctype != "File",
				action: () => this.setup_kanban_boards(),
			},
			Map: {
				condition:
					this.list_view.settings.get_coords_method ||
					(this.list_view.meta.fields.find((i) => i.fieldname === "latitude") &&
						this.list_view.meta.fields.find((i) => i.fieldname === "longitude")) ||
					this.list_view.meta.fields.find(
						(i) => i.fieldname === "location" && i.fieldtype == "Geolocation"
					),
				action: () => this.set_route("map"),
			},
		};
	}

	// a view's variants, as a submenu source (array, or a function for the
	// lazy ones — menu.js resolves it at hover with a loading state). Present
	// for every view that HAS variants, whichever view is current.
	get_view_submenu(view, config) {
		switch (view) {
			case "List":
				return this.get_layout_submenu(config);
			case "Report":
				return this.get_report_items();
			case "Calendar":
				return () => this.get_calendars().then((c) => this.get_calendar_items(c || []));
			case "Inbox":
				return this.get_inbox_items();
			case "Kanban":
				return () =>
					frappe.views.KanbanView.get_kanbans(this.doctype).then((kanbans) =>
						this.get_kanban_items(kanbans || [])
					);
			default:
				return null;
		}
	}

	// Saved layouts under the List row. On the list view itself the rows
	// apply in place (via the lazily-loaded list_filter bundle). From any
	// other view, clicking a layout switches to the list view WITH that
	// layout: the choice is saved as the active-layout preference and the
	// route is set clean, so the list view's restore logic applies it on
	// arrival.
	get_layout_submenu(config) {
		const lv = this.list_view;
		if (this.current_view === "List") {
			if (!lv.show_saved_layout_menu) return null;
			return () => {
				const ready = lv.list_filter
					? Promise.resolve(lv.list_filter.setup_promise)
					: lv.setup_list_filter_by();
				return ready.then(() => lv.list_filter.get_layout_menu_items());
			};
		}

		if (frappe.session.user === "Guest") return null;
		return () =>
			frappe.db
				.get_list("List Filter", {
					fields: ["name", "filter_name", "for_user"],
					filters: { reference_doctype: this.doctype },
					or_filters: [
						["for_user", "=", frappe.session.user],
						["for_user", "=", ""],
					],
					order_by: "filter_name asc",
					limit: 200,
				})
				.then((layouts) => this.get_cross_view_layout_items(layouts || []));
	}

	get_cross_view_layout_items(layouts) {
		const open_with_layout = (name) => {
			// remember the choice, then route WITHOUT carrying the current
			// view's filters — a layout defines its own, and URL filters
			// would override the restore. The route waits for the save:
			// user_settings.save only updates the local cache in its server
			// callback, so routing immediately would let the arriving list
			// view restore from the stale value.
			const go = () => frappe.set_route([this.slug(), "view", "list"]);
			frappe.model.user_settings
				.save(this.doctype, "List", {
					active_layout_name: name === "default_layout" ? "" : name,
				})
				// a failed save must not make the click inert — the list
				// opens either way, just without the chosen layout applied
				.then(go, go);
		};

		const layout_row = (layout) => ({
			label: __(layout.filter_name),
			onclick: () => open_with_layout(layout.name),
		});
		const global_layouts = layouts.filter((f) => !f.for_user).map(layout_row);
		const user_layouts = layouts
			.filter((f) => f.for_user === frappe.session.user)
			.map(layout_row);

		const items = [
			{
				label: __("Default Layout"),
				onclick: () => open_with_layout("default_layout"),
			},
		];
		if (global_layouts.length) {
			items.push({ group: __("Global Layouts"), options: global_layouts });
		}
		if (user_layouts.length) {
			items.push({ group: __("Your Layouts"), options: user_layouts });
		}
		return items;
	}

	get_report_items() {
		const route = frappe.get_route();
		const on_report = this.current_view === "Report";
		const items = [
			{
				label: __("Standard Report"),
				selected: on_report && route.length <= 3,
				onclick: () => this.set_route("report"),
			},
		];

		const report_row = (report) => ({
			label: report.name,
			selected: on_report && route.length > 3 && route[3] === report.title,
			href: report.route,
		});
		const reports = this.get_reports();
		// reports saved from the report builder vs the query/script reports
		// that developers ship for the doctype
		const saved = reports.filter((r) => r.report_type === "Report Builder");
		const related = reports.filter((r) => r.report_type !== "Report Builder");

		if (saved.length) {
			items.push({ group: __("Saved Reports"), options: saved.map(report_row) });
		}
		if (related.length) {
			items.push({ group: __("Related Reports"), options: related.map(report_row) });
		}
		return items;
	}

	get_calendar_items(calendars) {
		const current = this.current_view === "Calendar" ? frappe.get_route()[3] : null;
		const items = [
			{
				label: __("Default"),
				selected: current === "default",
				onclick: () => this.set_route("calendar", "default"),
			},
		];
		calendars
			.filter((calendar) => calendar.name !== "Default")
			.forEach((calendar) => {
				items.push({
					label: __(calendar.name),
					selected: current === calendar.name,
					href: calendar.route,
				});
			});
		return items;
	}

	get_inbox_items() {
		const items = this.get_email_accounts().map((account) => ({
			label: account.name,
			selected:
				this.current_view === "Inbox" &&
				this.email_account === account.route.split("/").pop(),
			href: account.route,
		}));
		if (has_common(frappe.user_roles, ["System Manager", "Administrator"])) {
			items.push({
				label: __("New Email Account"),
				icon: "plus",
				onclick: () => frappe.new_doc("Email Account"),
			});
		}
		return items;
	}

	get_kanban_items(kanbans) {
		const items = kanbans.map((board) => ({
			label: board.name,
			selected: board.name === this.kanban_board,
			onclick: () => this.set_route("kanban", board.name),
		}));
		const perms = this.list_view.board_perms;
		if (perms ? perms.create : true) {
			// its own group, like the layouts submenu's Create/Manage rows
			items.push({
				group: "",
				hide_label: true,
				options: [
					{
						label: __("Create Board"),
						icon: "plus",
						onclick: () => frappe.views.KanbanView.show_kanban_dialog(this.doctype),
					},
				],
			});
		}
		return items;
	}

	set_route(view, calendar_name) {
		const route = [this.slug(), "view", view];
		if (calendar_name) route.push(calendar_name);

		let search_params = cur_list?.get_search_params();
		if (search_params) {
			frappe.route_options = Object.fromEntries(search_params);
		}
		frappe.set_route(route);
	}

	get_page_name() {
		return frappe.utils.to_title_case(frappe.get_route().slice(-1)[0] || "");
	}

	get_reports() {
		// add reports linked to this doctype to the dropdown
		let added = [];
		let reports_to_add = [];

		let add_reports = (reports) => {
			reports.map((r) => {
				if (!r.ref_doctype || r.ref_doctype == this.doctype) {
					const report_type =
						r.report_type === "Report Builder"
							? `/desk/list/${r.ref_doctype}/report`
							: "/desk/query-report";

					const route = r.route || report_type + "/" + (r.title || r.name);

					if (added.indexOf(route) === -1) {
						// don't repeat
						added.push(route);
						reports_to_add.push({
							name: __(r.title || r.name),
							// raw title (route segment) and type, so the menu
							// can mark the open report and group by kind
							title: r.title || r.name,
							report_type: r.report_type,
							route: route,
						});
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
			Object.values(frappe.boot.allowed_reports).sort((a, b) =>
				a.title.localeCompare(b.title)
			) || [];

		// from specially tagged reports
		add_reports(reports);

		return reports_to_add;
	}

	setup_kanban_boards() {
		function fetch_kanban_board(doctype) {
			frappe.db.get_value(
				"Kanban Board",
				{ reference_doctype: doctype },
				"name",
				(board) => {
					if (!$.isEmptyObject(board)) {
						frappe.set_route("list", doctype, "kanban", board.name);
					} else {
						frappe.views.KanbanView.show_kanban_dialog(doctype);
					}
				}
			);
		}

		const last_opened_kanban =
			frappe.model.user_settings[this.doctype]["Kanban"]?.last_kanban_board;
		if (!last_opened_kanban) {
			fetch_kanban_board(this.doctype);
		} else {
			frappe.db.exists("Kanban Board", last_opened_kanban).then((exists) => {
				if (exists) {
					frappe.set_route("list", this.doctype, "kanban", last_opened_kanban);
				} else {
					fetch_kanban_board(this.doctype);
				}
			});
		}
	}

	get_calendars() {
		const doctype = this.doctype;
		let calendars = [];

		return frappe.db
			.get_list("Calendar View", {
				filters: {
					reference_doctype: doctype,
				},
			})
			.then((result) => {
				if (!(result && Array.isArray(result) && result.length)) return;

				if (frappe.views.calendar[this.doctype]) {
					// has standard calendar view
					calendars.push({
						name: "Default",
						route: `/desk/${this.slug()}/view/calendar/default`,
					});
				}
				result.map((calendar) => {
					calendars.push({
						name: calendar.name,
						route: `/desk/${this.slug()}/view/calendar/${calendar.name}`,
					});
				});

				return calendars;
			});
	}

	get_email_accounts() {
		let accounts_to_add = [];
		let accounts = frappe.boot.email_accounts;
		accounts.forEach((account) => {
			let email_account =
				account.email_id == "All Accounts" ? "All Accounts" : account.email_account;
			let route = `/desk/communication/view/inbox/${email_account}`;
			let display_name = ["All Accounts", "Sent Mail", "Spam", "Trash"].includes(
				account.email_id
			)
				? __(account.email_id)
				: account.email_account;

			accounts_to_add.push({
				name: display_name,
				route: route,
			});
		});

		return accounts_to_add;
	}

	slug() {
		return frappe.router.slug(frappe.router.doctype_layout || this.doctype);
	}

	// ─── legacy API (kept for compatibility — the espresso switcher above
	//     doesn't use these, but apps may call them) ────────────────────────

	add_view_to_menu(view, action) {
		if (this.doctype == "File" && view == "List") {
			view = "File";
		}
		let $el = this.page.add_custom_menu_item(
			this.parent,
			this.label_map[view] || __(view),
			action,
			true,
			null,
			this.icon_map[view] || "list"
		);
		$el.parent().attr("data-view", view);
	}

	setup_dropdown_in_navbar(view, items, default_action) {
		let placeholder = __("Select {0}", [__(view)]);

		if (items && items.length) {
			items.map((item) => {
				this.page.add_inner_button(
					item.name,
					() => location.replace(item.route),
					placeholder
				);
			});
		}

		if (default_action && Object.keys(default_action).length) {
			this.page.add_inner_button(default_action.label, default_action.action, placeholder);
		}
	}

	setup_kanban_switcher(kanbans) {
		const kanban_switcher = this.page.add_custom_button_group(
			__("Select Kanban"),
			null,
			this.list_view.$filter_section
		);

		kanbans.map((k) => {
			this.page.add_custom_menu_item(
				kanban_switcher,
				k.name,
				() => this.set_route("kanban", k.name),
				false
			);
		});

		let perms = this.list_view.board_perms;
		let can_create = perms ? perms.create : true;
		if (can_create) {
			this.page.add_custom_menu_item(
				kanban_switcher,
				__("Create New Kanban Board"),
				() => frappe.views.KanbanView.show_kanban_dialog(this.doctype),
				true
			);
		}
	}
};
