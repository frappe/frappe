const PAGE_LENGTH = 20;
const MAX_COLUMNS = 3;

const BADGE_THEMES = {
	orange: "amber",
	yellow: "amber",
	purple: "violet",
	pink: "red",
	cyan: "blue",
	"light-blue": "blue",
	grey: "gray",
	darkgrey: "gray",
};

frappe.ui.form.ConnectionsDialog = class ConnectionsDialog {
	constructor({ frm, doctype }) {
		this.frm = frm;
		this.dashboard = frm.dashboard;
		Promise.all([
			this.dashboard.load_counts(),
			frappe.require("embedded_list.bundle.js"),
		]).then(() => this.make(doctype));
	}

	make(doctype) {
		const connections = this.dashboard.get_connections();
		const linked = connections.filter((c) => c.count);
		const total = linked.reduce((sum, c) => sum + cint(c.count), 0);
		// a type at the server's cap of 100 may have more
		const total_label = linked.some((c) => cint(c.count) > 99) ? `${total}+` : total;

		const groups = [];
		for (const c of connections) {
			let group = groups.find((g) => g.group === c.group);
			if (!group) groups.push((group = { group: c.group && __(c.group), items: [] }));
			group.items.push(this.get_tab(c));
		}

		this.dialog = new frappe.ui.SettingsDialog({
			title: __("Connections"),
			sidebar_title: __("Connections"),
			sidebar_footer: linked.length
				? __("{0} records across {1} types", [total_label, linked.length])
				: "",
			default_tab: doctype || (linked[0] || connections[0])?.doctype,
			tabs: groups,
			compact: true,
		});
		this.dialog.onhide = () => this.dialog.$wrapper.remove();
		this.dialog.show();
	}

	get_tab(connection) {
		const { doctype, count } = connection;
		const icon = frappe.ui.form.connection_icon_name(connection.icon);
		const can_create =
			this.frm.can_create(doctype) && !this.dashboard.data.internal_links?.[doctype];
		const is_empty = count === 0;

		return {
			id: doctype,
			label: __(doctype),
			icon,
			count: count ? frappe.ui.form.connection_count(count) : "",
			muted: is_empty,
			title: __(doctype),
			meta: count ? frappe.ui.form.connection_count(count) : "",
			actions: is_empty
				? []
				: [
						{
							label: __("Open in list view"),
							icon_right: "arrow-up-right",
							variant: "ghost",
							click: () => this.open_list_view(doctype),
						},
						can_create && {
							label: __("New"),
							icon: "plus",
							click: () => this.make_new(doctype),
						},
				  ].filter(Boolean),
			render: (panel) => {
				panel.body.addClass("connections-panel");
				if (is_empty) {
					this.render_empty(doctype, can_create, icon, panel);
					return;
				}
				this.make_list({ doctype, panel });
			},
		};
	}

	render_empty(doctype, can_create, icon, panel) {
		const title = this.frm.get_title();
		panel.body.append(
			frappe.ui.empty_state({
				icon,
				title: __("No {0} for {1} yet", [__(doctype), title]),
				description: can_create
					? __("A new one is linked here automatically.")
					: __("Documents that link to {0} show up here.", [title]),
				actions: can_create
					? [
							{
								label: __("New {0}", [__(doctype)]),
								icon: "plus",
								variant: "solid",
								css_class: "connections-new",
								onclick: () => this.make_new(doctype),
							},
					  ]
					: [],
				css_class: "connections-empty",
			})
		);
	}

	get_filters(doctype) {
		// a dashboard's dynamic link can name a field that only some of its doctypes have
		// (e.g. Customer's "quotation_to" applies to Quotation, not Opportunity); the link
		// field itself can be in a child table
		const filters = this.dashboard.get_link_filters(doctype);
		if (!filters) return null;
		const link_fieldname = this.dashboard.get_link_fieldname(doctype);
		const out = {};
		for (const [fieldname, value] of Object.entries(filters)) {
			if (this.get_field_doctype(doctype, fieldname)) {
				out[fieldname] = value;
			} else if (fieldname === link_fieldname) {
				return null;
			}
		}
		return out;
	}

	get_field_doctype(doctype, fieldname) {
		if (
			frappe.model.std_fields_list.includes(fieldname) ||
			frappe.meta.has_field(doctype, fieldname)
		) {
			return doctype;
		}
		return frappe.meta
			.get_table_fields(doctype)
			.map((df) => df.options)
			.find((child) => frappe.meta.has_field(child, fieldname));
	}

	get_list_filters(doctype, filters) {
		return Object.entries(filters).map(([fieldname, value]) => {
			const field_doctype = this.get_field_doctype(doctype, fieldname);
			return Array.isArray(value)
				? [field_doctype, fieldname, ...value]
				: [field_doctype, fieldname, "=", value];
		});
	}

	async make_list(view) {
		const { doctype } = view;
		view.$root = $('<div class="connections-records"></div>').appendTo(view.panel.body);
		await frappe.model.with_doctype(doctype);
		const filters = this.get_filters(doctype);
		const list_filters = filters && this.get_list_filters(doctype, filters);
		const child_filter = list_filters?.some(([field_doctype]) => field_doctype !== doctype);
		const fields = this.get_fields(doctype, filters);
		const meta = frappe.get_meta(doctype);
		const me = this;

		view.list = new frappe.ui.EmbeddedList({
			wrapper: view.$root,
			page_size: PAGE_LENGTH,
			search_position: "start",
			empty_icon: "inbox",
			empty_message: __("No {0} yet", [__(doctype)]),
			no_match_message: __("No matching {0}", [__(doctype)]),
			get_page: ({ start, page_length, txt }) => {
				if (!filters) return Promise.resolve([]);
				return frappe
					.call({
						method: "frappe.client.get_list",
						args: {
							doctype,
							fields: fields.fields,
							filters: list_filters,
							// a link in a child table matches once per row
							group_by: child_filter ? "name" : undefined,
							or_filters: txt
								? [
										["name", "like", `%${txt}%`],
										meta.title_field && [meta.title_field, "like", `%${txt}%`],
								  ].filter(Boolean)
								: undefined,
							order_by: "modified desc",
							limit_start: start,
							limit_page_length: page_length,
						},
					})
					.then((r) => r.message || []);
			},
			before_render() {
				this.columns = me.get_list_columns(view, fields, this.data);
			},
			on_row_click: (row) => this.open_record(doctype, row.name),
		});
		view.list.refresh();
	}

	get_fields(doctype, filters) {
		const meta = frappe.get_meta(doctype);
		const settings = frappe.listview_settings[doctype] || {};
		const skip = [
			"status",
			"workflow_state",
			"naming_series",
			meta.title_field,
			...Object.keys(filters || {}),
		];
		const candidates = meta.fields.filter(
			(df) =>
				df.in_list_view &&
				!skip.includes(df.fieldname) &&
				!frappe.model.no_value_type.includes(df.fieldtype) &&
				!df.hidden &&
				frappe.perm.has_perm(doctype, df.permlevel, "read")
		);
		const dates = candidates.filter((df) => ["Date", "Datetime"].includes(df.fieldtype));
		const columns = candidates
			.filter((df) => !dates.includes(df) || df === dates.at(-1))
			.slice(0, MAX_COLUMNS);

		const has_field = (fieldname) => frappe.meta.has_field(doctype, fieldname);
		const currency_fields = columns
			.filter((df) => df.fieldtype === "Currency" && df.options && has_field(df.options))
			.map((df) => df.options);

		return {
			title: meta.title_field && meta.title_field !== "name" ? meta.title_field : null,
			columns,
			fields: [
				...new Set(
					[
						"name",
						"docstatus",
						"modified",
						meta.title_field,
						...columns.map((df) => df.fieldname),
						...currency_fields,
						has_field("status") ? "status" : null,
						has_field("workflow_state") ? "workflow_state" : null,
						...(settings.add_fields || []).filter(has_field),
					].filter(Boolean)
				),
			],
		};
	}

	get_title(doc, title_field) {
		const title = title_field && doc[title_field];
		return title && ![doc.name, this.frm.docname, this.frm.get_title()].includes(title)
			? title
			: "";
	}

	get_list_columns(view, fields, rows) {
		const escape = frappe.utils.escape_html;
		return [
			{ label: __("ID"), fieldname: "name" },
			rows.some((row) => this.get_title(row, fields.title)) && {
				label: __("Title"),
				render: (row) => escape(this.get_title(row, fields.title)),
			},
			...fields.columns.map((df) => this.value_column(df)),
			{ label: __("Status"), render: (row) => this.status_badge(row, view.doctype) },
		].filter(Boolean);
	}

	value_column(df) {
		return {
			label: __(df.label, null, df.parent),
			align: frappe.model.is_numeric_field(df) ? "right" : null,
			render: (row) => this.format_value(df, row),
		};
	}

	status_badge(doc, doctype) {
		const indicator = frappe.get_indicator(doc, doctype);
		return indicator
			? frappe.ui.badge.html({
					label: indicator[0],
					theme: BADGE_THEMES[indicator[1]] || indicator[1],
			  })
			: "";
	}

	format_value(df, doc) {
		const value = doc[df.fieldname];
		if (value == null || value === "") return "";
		if (["Date", "Datetime"].includes(df.fieldtype)) {
			return frappe.utils.escape_html(
				frappe.datetime
					.str_to_obj(value)
					.toLocaleDateString(frappe.boot.lang || undefined, {
						day: "numeric",
						month: "short",
						year: "numeric",
					})
			);
		}
		return frappe.format(value, df, { inline: true, only_value: true }, doc);
	}

	open_record(doctype, name) {
		this.dialog.hide();
		frappe.set_route("Form", doctype, name);
	}

	make_new(doctype) {
		this.dialog.hide();
		this.frm.make_new(doctype, this.dashboard.get_link_fieldname(doctype));
	}

	async open_list_view(doctype) {
		await frappe.model.with_doctype(doctype);
		const filters = this.get_filters(doctype);
		this.dialog.hide();
		if (filters) frappe.route_options = filters;
		frappe.set_route("List", doctype, "List");
	}
};
