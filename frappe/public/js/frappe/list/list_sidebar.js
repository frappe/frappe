// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import ListFilter from './list_filter';
frappe.provide('frappe.views');

// opts:
// stats = list of fields
// doctype
// parent
// set_filter = function called on click

frappe.views.ListSidebar = class ListSidebar {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
		this.cat_tags = [];
	}

	make() {
		var sidebar_content = frappe.render_template("list_sidebar", { doctype: this.doctype });

		this.sidebar = $('<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.group_by_fields = [];
		this.user_settings = frappe.get_user_settings(this.doctype);
		if(this.user_settings.group_by_fields) {
			this.group_by_fields = this.user_settings.group_by_fields;
			this.add_group_by_dropdown_fields(this.group_by_fields);
		}
		this.setup_reports();
		this.setup_list_filter();
		this.setup_views();
		this.setup_kanban_boards();
		this.setup_calendar_view();
		this.setup_email_inbox();
		this.setup_keyboard_shortcuts();
		this.setup_list_group_by();

		let limits = frappe.boot.limits;

		if (limits.upgrade_url && limits.expiry && !frappe.flags.upgrade_dismissed) {
			this.setup_upgrade_box();
		}

		if (this.list_view.list_view_settings && this.list_view.list_view_settings.disable_sidebar_stats) {
			this.sidebar.find('.sidebar-stat').remove();
		} else {
			this.sidebar.find('.list-stats').on('click', (e) => {
				$(e.currentTarget).find('.stat-link').remove();
				this.get_stats();
			});
		}

	}

	setup_views() {
		var show_list_link = false;

		if (frappe.views.calendar[this.doctype]) {
			this.sidebar.find('.list-link[data-view="Calendar"]').removeClass("hide");
			this.sidebar.find('.list-link[data-view="Gantt"]').removeClass('hide');
			show_list_link = true;
		}
		//show link for kanban view
		this.sidebar.find('.list-link[data-view="Kanban"]').removeClass('hide');
		if (this.doctype === "Communication" && frappe.boot.email_accounts.length) {
			this.sidebar.find('.list-link[data-view="Inbox"]').removeClass('hide');
			show_list_link = true;
		}

		if (frappe.treeview_settings[this.doctype]) {
			this.sidebar.find(".tree-link").removeClass("hide");
		}

		this.current_view = 'List';
		var route = frappe.get_route();
		if (route.length > 2 && frappe.views.view_modes.includes(route[2])) {
			this.current_view = route[2];

			if (this.current_view === 'Kanban') {
				this.kanban_board = route[3];
			} else if (this.current_view === 'Inbox') {
				this.email_account = route[3];
			}
		}

		// disable link for current view
		this.sidebar.find('.list-link[data-view="' + this.current_view + '"] a')
			.attr('disabled', 'disabled').addClass('disabled');

		//enable link for Kanban view
		this.sidebar.find('.list-link[data-view="Kanban"] a, .list-link[data-view="Inbox"] a')
			.attr('disabled', null).removeClass('disabled');

		// show image link if image_view
		if (this.list_view.meta.image_field) {
			this.sidebar.find('.list-link[data-view="Image"]').removeClass('hide');
			show_list_link = true;
		}

		if (show_list_link) {
			this.sidebar.find('.list-link[data-view="List"]').removeClass('hide');
		}
	}

	setup_reports() {
		// add reports linked to this doctype to the dropdown
		var me = this;
		var added = [];
		var dropdown = this.page.sidebar.find('.reports-dropdown');
		var divider = false;

		var add_reports = function(reports) {
			$.each(reports, function(name, r) {
				if (!r.ref_doctype || r.ref_doctype == me.doctype) {
					var report_type = r.report_type === 'Report Builder' ?
						`List/${r.ref_doctype}/Report` : 'query-report';

					var route = r.route || report_type + '/' + (r.title || r.name);

					if (added.indexOf(route) === -1) {
						// don't repeat
						added.push(route);

						if (!divider) {
							me.get_divider().appendTo(dropdown);
							divider = true;
						}

						$('<li><a href="#' + route + '">' +
							__(r.title || r.name) + '</a></li>').appendTo(dropdown);
					}
				}
			});
		};

		// from reference doctype
		if (this.list_view.settings.reports) {
			add_reports(this.list_view.settings.reports);
		}

		// Sort reports alphabetically
		var reports = Object.values(frappe.boot.user.all_reports).sort((a,b) => a.title.localeCompare(b.title)) || [];

		// from specially tagged reports
		add_reports(reports);
	}

	setup_list_filter() {
		this.list_filter = new ListFilter({
			wrapper: this.page.sidebar.find('.list-filters'),
			doctype: this.doctype,
			list_view: this.list_view
		});
	}

	setup_kanban_boards() {
		const $dropdown = this.page.sidebar.find('.kanban-dropdown');
		frappe.views.KanbanView.setup_dropdown_in_sidebar(this.doctype, $dropdown);
	}

	setup_calendar_view() {
		const doctype = this.doctype;

		frappe.db.get_list('Calendar View', {
			filters: {
				reference_doctype: doctype
			}
		}).then(result => {
			if (!result) return;
			const calendar_views = result;
			const $link_calendar = this.sidebar.find('.list-link[data-view="Calendar"]');

			let default_link = '';
			if (frappe.views.calendar[this.doctype]) {
				// has standard calendar view
				default_link = `<li><a href="#List/${doctype}/Calendar/Default">
					${ __("Default") }</a></li>`;
			}
			const other_links = calendar_views.map(
				calendar_view => `<li><a href="#List/${doctype}/Calendar/${calendar_view.name}">
					${ __(calendar_view.name) }</a>
				</li>`
			).join('');

			const dropdown_html = `
				<div class="btn-group">
					<a class="dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
						${ __("Calendar") } <span class="caret"></span>
					</a>
					<ul class="dropdown-menu calendar-dropdown" style="max-height: 300px; overflow-y: auto;">
						${default_link}
						${other_links}
					</ul>
				</div>
			`;
			$link_calendar.removeClass('hide');
			$link_calendar.html(dropdown_html);
		});
	}

	setup_email_inbox() {
		// get active email account for the user and add in dropdown
		if (this.doctype != "Communication")
			return;

		let $dropdown = this.page.sidebar.find('.email-account-dropdown');
		let divider = false;

		if (has_common(frappe.user_roles, ["System Manager", "Administrator"])) {
			$(`<li class="new-email-account"><a>${__("New Email Account")}</a></li>`)
				.appendTo($dropdown);
		}

		let accounts = frappe.boot.email_accounts;
		accounts.forEach((account) => {
			let email_account = (account.email_id == "All Accounts") ? "All Accounts" : account.email_account;
			let route = ["List", "Communication", "Inbox", email_account].join('/');
			if (!divider) {
				this.get_divider().appendTo($dropdown);
				divider = true;
			}
			$(`<li><a href="#${route}">${account.email_id}</a></li>`).appendTo($dropdown);
			if (account.email_id === "Sent Mail")
				divider = false;
		});

		$dropdown.find('.new-email-account').click(function() {
			frappe.new_doc("Email Account");
		});
	}

	setup_keyboard_shortcuts() {
		this.sidebar.find('.list-link > a, .list-link > .btn-group > a').each((i, el) => {
			frappe.ui.keys
				.get_shortcut_group(this.page)
				.add($(el));
		});
	}

	setup_list_group_by() {
		this.add_group_by_dropdown_fields(['assigned_to']);
		let d = new frappe.ui.Dialog ({
			title: __("Add Filter By"),
			fields: this.get_group_by_dropdown_fields()
		});
		d.set_primary_action("Add", (values) => {
			this.page.sidebar.find('.group-by-field a').not("[data-fieldname='assigned_to']").remove();
			let fields = values[this.doctype];
			delete values[this.doctype];
			if(!fields) {
				frappe.model.user_settings.save(this.doctype,'group_by_fields',null);
			} else {
				this.add_group_by_dropdown_fields(fields);
				frappe.model.user_settings.save(this.doctype,'group_by_fields',fields);
			}
			d.hide();
		});

		this.page.sidebar.find(".add-list-group-by a ").on("click", () => {
			d.show();
		});
	}

	get_group_by_count(field, dropdown) {
		let current_filters = this.list_view.get_filters_for_args(), field_list;
		frappe.call('frappe.desk.listview.get_group_by_count',
			{doctype: this.doctype, current_filters: current_filters, field: field}).then((data) => {
			dropdown.find('.group-by-loading').hide();
			if(field === 'assigned_to') {
				let current_user  = data.message.find(user => user.name === frappe.session.user);
				if(current_user) {
					let current_user_count = current_user.count;
					this.get_html_for_group_by('Me', current_user_count).appendTo(dropdown);
				}
				field_list = data.message.filter(user => !['Guest', frappe.session.user, 'Administrator'].includes(user.name) && user.count!==0 );
			} else {
				field_list = data.message.filter(field => field.count!==0 );
			}
			field_list.forEach((f) => {
				if(f.name === null) {
					f.name = 'Not Specified';
				}
				this.get_html_for_group_by(f.name, f.count).appendTo(dropdown);
			});
			if(field_list.length) {
				this.setup_dropdown_search(dropdown, '.group-by-value');
			} else {
				dropdown.find('.dropdown-search').hide();
			}
			this.setup_group_by_filter(dropdown, field);
		});
	}

	setup_group_by_filter(dropdown, field) {
		dropdown.find("li a").on("click", (e) => {
			let value = $(e.currentTarget).find($('.group-by-value')).text().trim();
			let fieldname = field === 'assigned_to'? '_assign': field;
			this.list_view.filter_area.remove(field);
			if(value === 'Not Specified') {
				this.list_view.filter_area.add(this.doctype, fieldname, "like", '');
			} else {
				if(value === 'Me') value = frappe.session.user;
				this.list_view.filter_area.add(this.doctype, fieldname, "like", `%${value}%`);
			}
		});
	}

	setup_dropdown_search(dropdown, text_class) {
		let $dropdown_search = dropdown.find('.dropdown-search').show();
		let $search_input = $dropdown_search.find('.dropdown-search-input');
		$search_input.focus();
		$dropdown_search.on('click',(e)=>{
			e.stopPropagation();
		});
		let $elements = dropdown.find('li');
		$dropdown_search.on('keyup',()=> {
			let text_filter = $search_input.find('.dropdown-search-input').val().toLowerCase();
			let text;
			for (var i = 0; i < $elements.length; i++) {
				text = $elements.eq(i).find(text_class).text();
				if (text.toLowerCase().indexOf(text_filter) > -1) {
					$elements.eq(i).css('display','');
				} else {
					$elements.eq(i).css('display','none');
				}
			}
		});
		dropdown.parent().on('hide.bs.dropdown',()=> {
			$dropdown_search.val('');
		});
	}

	add_group_by_dropdown_fields(fields) {
		if(fields) {
			fields.forEach((field)=> {
				let field_label = field === 'assigned_to'? 'Assigned To': frappe.meta.get_label(this.doctype, field);
				this.list_group_by_dropdown = $(frappe.render_template("list_sidebar_group_by", {
					field_label: field_label,
					group_by_field: field,
				}));

				this.list_group_by_dropdown.on('click', (e)=> {
					let dropdown = $(e.currentTarget).find('.group-by-dropdown');
					dropdown.find('.group-by-loading').show();
					dropdown.find('.group-by-item').remove();
					this.get_group_by_count(field, dropdown);
				});
				this.list_group_by_dropdown.insertAfter(this.page.sidebar.find('.list-group-by-label'));
			});
		}
	}

	get_html_for_group_by(name, count) {
		if (count > 99) count='99+';
		let html = $('<li class="group-by-item"><a class="badge-hover" href="#" onclick="return false;"><span class="group-by-value">'
					+ name + '</span><span class="badge pull-right" style="position:relative">' + count + '</span></a></li>');
		return html;
	}

	get_group_by_dropdown_fields() {
		let group_by_fields = [];
		let fields = this.list_view.meta.fields.filter((f)=> ["Select", "Link"].includes(f.fieldtype));
		group_by_fields.push({
			label: __(this.doctype),
			fieldname: this.doctype,
			fieldtype: 'MultiCheck',
			columns: 2,
			options: fields
				.map(df => ({
					label: __(df.label),
					value: df.fieldname,
					checked: this.group_by_fields.includes(df.fieldname)
				}))
		});
		return group_by_fields;
	}

	setup_upgrade_box() {
		let upgrade_list = $(`<ul class="list-unstyled sidebar-menu"></ul>`).appendTo(this.sidebar);

		// Show Renew/Upgrade button,
		// if account is holding one user free plan or
		// if account's expiry date within range of 30 days from today's date

		let upgrade_date = frappe.datetime.add_days(frappe.datetime.get_today(), 30);
		if (frappe.boot.limits.users === 1 || upgrade_date >= frappe.boot.limits.expiry) {
			let upgrade_box = $(`<div class="border" style="
					padding: 0px 10px;
					border-radius: 3px;
				">
				<a><i class="octicon octicon-x pull-right close" style="margin-top: 10px;"></i></a>
				<h5>Go Premium</h5>
				<p>Upgrade to a premium plan with more users, storage and priority support.</p>
				<button class="btn btn-xs btn-default btn-upgrade" style="margin-bottom: 10px;"> Renew / Upgrade </button>
				</div>`).appendTo(upgrade_list);

			upgrade_box.find('.btn-upgrade').on('click', () => {
				frappe.set_route('usage-info');
			});

			upgrade_box.find('.close').on('click', () => {
				upgrade_list.remove();
				frappe.flags.upgrade_dismissed = 1;
			});
		}
	}

	get_cat_tags() {
		return this.cat_tags;
	}

	get_stats() {
		var me = this;
		frappe.call({
			method: 'frappe.desk.reportview.get_sidebar_stats',
			type: 'GET',
			args: {
				stats: me.stats,
				doctype: me.doctype,
				filters: me.default_filters || []
			},
			callback: function(r) {
				me.defined_category = r.message;
				if (r.message.defined_cat) {
					me.defined_category = r.message.defined_cat;
					me.cats = {};
					//structure the tag categories
					for (var i in me.defined_category) {
						if (me.cats[me.defined_category[i].category] === undefined) {
							me.cats[me.defined_category[i].category] = [me.defined_category[i].tag];
						} else {
							me.cats[me.defined_category[i].category].push(me.defined_category[i].tag);
						}
						me.cat_tags[i] = me.defined_category[i].tag;
					}
					me.tempstats = r.message.stats;

					$.each(me.cats, function(i, v) {
						me.render_stat(i, (me.tempstats || {})["_user_tags"], v);
					});
					me.render_stat("_user_tags", (me.tempstats || {})["_user_tags"]);
				} else {
					//render normal stats
					me.render_stat("_user_tags", (r.message.stats || {})["_user_tags"]);
				}
				let stats_dropdown = me.sidebar.find('.list-stats-dropdown');
				me.setup_dropdown_search(stats_dropdown,'.stat-label');
			}
		});
	}

	render_stat(field, stat, tags) {
		var me = this;
		var sum = 0;
		var stats = [];
		var label = frappe.meta.docfield_map[this.doctype][field] ?
			frappe.meta.docfield_map[this.doctype][field].label : field;

		stat = (stat || []).sort(function(a, b) {
			return b[1] - a[1];
		});
		$.each(stat, function(i, v) {
			sum = sum + v[1];
		});

		if (tags) {
			for (var t in tags) {
				var nfound = -1;
				for (var i in stat) {
					if (tags[t] === stat[i][0]) {
						stats.push(stat[i]);
						nfound = i;
						break;
					}
				}
				if (nfound < 0) {
					stats.push([tags[t], 0]);
				} else {
					me.tempstats["_user_tags"].splice(nfound, 1);
				}
			}
			field = "_user_tags";
		} else {
			stats = stat;
		}
		var context = {
			field: field,
			stat: stats,
			sum: sum,
			label: field === '_user_tags' ? (tags ? __(label) : __("Tags")) : __(label),
		};
		$(frappe.render_template("list_sidebar_stat", context))
			.on("click", ".stat-link", function() {
				var fieldname = $(this).attr('data-field');
				var label = $(this).attr('data-label');
				var condition = "like";
				var existing = me.list_view.filter_area.filter_list.get_filter(fieldname);
				if(existing) {
					existing.remove();
				}
				if (label == "No Tags") {
					label = "%,%";
					condition = "not like";
				}
				me.list_view.filter_area.filter_list.add_filter(me.list_view.doctype, fieldname, condition, label)
					.then(function() {
						me.list_view.refresh();
					});
			})
			.appendTo(this.sidebar.find(".list-stats-dropdown"));
	}

	set_fieldtype(df) {

		// scrub
		if (df.fieldname == "docstatus") {
			df.fieldtype = "Select",
			df.options = [
				{ value: 0, label: "Draft" },
				{ value: 1, label: "Submitted" },
				{ value: 2, label: "Cancelled" },
			];
		} else if (df.fieldtype == 'Check') {
			df.fieldtype = 'Select';
			df.options = [{ value: 0, label: 'No' },
				{ value: 1, label: 'Yes' }
			];
		} else if (['Text', 'Small Text', 'Text Editor', 'Code', 'Tag', 'Comments',
			'Dynamic Link', 'Read Only', 'Assign'
		].indexOf(df.fieldtype) != -1) {
			df.fieldtype = 'Data';
		} else if (df.fieldtype == 'Link' && this.$w.find('.condition').val() != "=") {
			df.fieldtype = 'Data';
		}
		if (df.fieldtype === "Data" && (df.options || "").toLowerCase() === "email") {
			df.options = null;
		}
	}

	reload_stats() {
		this.sidebar.find(".sidebar-stat").remove();
		this.get_stats();
	}

	get_divider() {
		return $('<li role="separator" class="divider"></li>');
	}
};
