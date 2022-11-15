frappe.provide("frappe.views");

frappe.views.ListViewSelect = class ListViewSelect {
	constructor(opts) {
		$.extend(this, opts);
		this.set_current_view();
		this.setup_views();
	}

	add_view_to_menu(view, action) {
		if (this.doctype == "File" && view == "List") {
			view = "File";
		}
		let $el = this.page.add_custom_menu_item(
			this.parent,
			__(view),
			action,
			true,
			null,
			this.icon_map[view] || "list"
		);
		$el.parent().attr("data-view", view);
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

	set_route(view, calendar_name) {
		const route = [this.slug(), "view", view];
		if (calendar_name) route.push(calendar_name);
		frappe.set_route(route);
	}

	setup_views() {
		const views = {
			List: {
				condition: true,
				action: () => this.set_route("list")
			},
			Report: {
				condition: true,
				action: () => this.set_route("report"),
				current_view_handler: () => {
					const reports = this.get_reports();
					let default_action = {};
					// Only add action if current route is not report builder
					if (frappe.get_route().length > 3) {
						default_action = {
							label: __("Report Builder"),
							action: () => this.set_route("report")
						};
					}
					this.setup_dropdown_in_sidebar("Report", reports, default_action);
				}
			},
			Dashboard: {
				condition: true,
				action: () => this.set_route("dashboard")
			},
			Calendar: {
				condition: frappe.views.calendar[this.doctype],
				action: () => this.set_route("calendar", "default"),
				current_view_handler: () => {
					this.get_calendars().then(calendars => {
						this.setup_dropdown_in_sidebar("Calendar", calendars);
					});
				}
			},
			Gantt: {
				condition: frappe.views.calendar[this.doctype],
				action: () => this.set_route("gantt")
			},
			Inbox: {
				condition:
					this.doctype === "Communication" &&
					frappe.boot.email_accounts.length,
				action: () => this.set_route("inbox"),
				current_view_handler: () => {
					const accounts = this.get_email_accounts();
					let default_action;
					if (
						has_common(frappe.user_roles, [
							"System Manager",
							"Administrator"
						])
					) {
						default_action = {
							label: __("New Email Account"),
							action: () => frappe.new_doc("Email Account")
						};
					}
					this.setup_dropdown_in_sidebar(
						"Inbox",
						accounts,
						default_action
					);
				}
			},
			Image: {
				condition: this.list_view.meta.image_field,
				action: () => this.set_route("image")
			},
			Tree: {
				condition:
					frappe.treeview_settings[this.doctype] ||
					frappe.get_meta(this.doctype).is_tree,
				action: () => this.set_route("tree")
			},
			Kanban: {
				condition: this.doctype != "File",
				action: () => this.setup_kanban_boards(),
				current_view_handler: () => {
					frappe.views.KanbanView.get_kanbans(this.doctype).then(
						kanbans => this.setup_kanban_switcher(kanbans)
					);
				}
			},
			Map: {
				condition: this.list_view.settings.get_coords_method ||
					(this.list_view.meta.fields.find(i => i.fieldname === "latitude") &&
					this.list_view.meta.fields.find(i => i.fieldname === "longitude")) ||
					(this.list_view.meta.fields.find(i => i.fieldname === 'location' && i.fieldtype == 'Geolocation')),
				action: () => this.set_route("map")
			},
		};

		frappe.views.view_modes.forEach(view => {
			if (this.current_view !== view && views[view].condition) {
				this.add_view_to_menu(view, views[view].action);
			}

			if (this.current_view == view) {
				views[view].current_view_handler &&
					views[view].current_view_handler();
			}
		});
	}

	setup_dropdown_in_sidebar(view, items, default_action) {
		if (!this.sidebar) return;
		const views_wrapper = this.sidebar.sidebar.find(".views-section");
		views_wrapper.find(".sidebar-label").html(`${__(view)}`);
		const $dropdown = views_wrapper.find(".views-dropdown");

		let placeholder = `${__("Select {0}", [__(view)])}`;
		let html = ``;

		if (!items || !items.length) {
			html = `<div class="empty-state">
						${__("No {0} Found", [__(view)])}
				</div>`;
		} else {
			const page_name = this.get_page_name();
			items.map(item => {
				if (item.name.toLowerCase() == page_name.toLowerCase()) {
					placeholder = item.name;
				} else {
					html += `<li><a class="dropdown-item" href="${item.route}">${
						item.name
					}</a></li>`;
				}
			});
		}

		views_wrapper.find(".selected-view").html(placeholder);

		if (default_action) {
			views_wrapper.find(".sidebar-action a").html(default_action.label);
			views_wrapper
				.find(".sidebar-action a")
				.click(() => default_action.action());
		}

		$dropdown.html(html);

		views_wrapper.removeClass("hide");
	}

	setup_kanban_switcher(kanbans) {
		const kanban_switcher = this.page.add_custom_button_group(
			__("Select Kanban"),
			null,
			this.list_view.$filter_section
		);

		kanbans.map(k => {
			this.page.add_custom_menu_item(
				kanban_switcher,
				k.name,
				() => this.set_route("kanban", k.name),
				false
			);
		});

		this.page.add_custom_menu_item(
			kanban_switcher,
			__("Create New Kanban Board"),
			() => frappe.views.KanbanView.show_kanban_dialog(this.doctype),
			true
		);
	}

	get_page_name() {
		return frappe.utils.to_title_case(
			frappe.get_route().slice(-1)[0] || ""
		);
	}

	get_reports() {
		// add reports linked to this doctype to the dropdown
		let added = [];
		let reports_to_add = [];

		let add_reports = reports => {
			reports.map(r => {
				if (!r.ref_doctype || r.ref_doctype == this.doctype) {
					const report_type =
						r.report_type === "Report Builder"
							? `/app/list/${r.ref_doctype}/report`
							: "/app/query-report";

					const route =
						r.route || report_type + "/" + (r.title || r.name);

					if (added.indexOf(route) === -1) {
						// don't repeat
						added.push(route);
						reports_to_add.push({
							name: __(r.title || r.name),
							route: route
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
			Object.values(frappe.boot.user.all_reports).sort((a, b) =>
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
			frappe.model.user_settings[this.doctype]["Kanban"] &&
			frappe.model.user_settings[this.doctype]["Kanban"].last_kanban_board;
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
					reference_doctype: doctype
				}
			})
			.then(result => {
				if (!(result && Array.isArray(result) && result.length)) return;

				if (frappe.views.calendar[this.doctype]) {
					// has standard calendar view
					calendars.push({
						name: "Default",
						route: `/app/${this.slug()}/view/calendar/default`
					});
				}
				result.map(calendar => {
					calendars.push({
						name: calendar.name,
						route: `/app/${this.slug()}/view/calendar/${
							calendar.name
						}`
					});
				});

				return calendars;
			});
	}

	get_email_accounts() {
		let accounts_to_add = [];
		let accounts = frappe.boot.email_accounts;
		accounts.forEach(account => {
			let email_account =
				account.email_id == "All Accounts"
					? "All Accounts"
					: account.email_account;
			let route = `/app/communication/view/inbox/${email_account}`;
			let display_name = [
				"All Accounts",
				"Sent Mail",
				"Spam",
				"Trash"
			].includes(account.email_id)
				? __(account.email_id)
				: account.email_account;

			accounts_to_add.push({
				name: display_name,
				route: route
			});
		});

		return accounts_to_add;
	}

	slug() {
		return frappe.router.slug(frappe.router.doctype_layout || this.doctype);
	}
};
