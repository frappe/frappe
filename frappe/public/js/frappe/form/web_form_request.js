const METHOD = "frappe.website.doctype.web_form_request.web_form_request";
const STATUS_THEME = { Used: "green", Expired: "red", "Not Used": "gray" };

export class WebFormRequestDialog {
	constructor({ frm }) {
		this.frm = frm;
	}

	show() {
		const web_forms = frappe.boot.web_form_request_forms[this.frm.doctype];
		this.titles = Object.fromEntries(web_forms.map((f) => [f.value, f.label]));
		this.dialog = new frappe.ui.Dialog({
			title: __("Request via Web Form"),
			fields: [
				{
					fieldtype: "Select",
					fieldname: "web_form",
					label: __("Web Form"),
					options: web_forms.map((f) => ({
						value: f.value,
						label: frappe.utils.escape_html(f.label),
					})),
					default: web_forms[0].value,
					reqd: 1,
				},
				{
					fieldtype: "Datetime",
					fieldname: "expires_on",
					label: __("Expires On"),
					default: frappe.datetime.add_days(frappe.datetime.now_datetime(), 7),
				},
				{
					fieldtype: "Section Break",
					fieldname: "requests_section",
					label: __("Earlier Requests"),
					hidden: 1,
				},
				{ fieldtype: "HTML", fieldname: "requests_html" },
			],
			primary_action_label: __("Copy Link"),
			primary_action: (values) =>
				this.create(values).then((url) => {
					frappe.utils.copy_to_clipboard(url, __("Web Form Request link copied"));
					this.dialog.hide();
				}),
		});
		this.dialog.footer.addClass("border-0 pt-0");
		this.dialog.add_custom_action(__("Email Link"), () => {
			const values = this.dialog.get_values();
			if (!values) return;
			this.create(values).then((url) => {
				this.dialog.hide();
				this.email(url, values.web_form);
			});
		});
		this.dialog.show();
		this.load_requests();
	}

	create({ web_form, expires_on }) {
		return frappe.xcall(`${METHOD}.create_for_document`, {
			web_form,
			docname: this.frm.docname,
			expires_on,
		});
	}

	email(url, web_form) {
		new frappe.views.CommunicationComposer({
			doc: this.frm.doc,
			frm: this.frm,
			subject: __("Please fill in {0}", [this.titles[web_form]]),
			message: `<p><a href="${encodeURI(url)}">${frappe.utils.escape_html(url)}</a></p>`,
		});
	}

	load_requests() {
		Promise.all([
			frappe.xcall(
				`${METHOD}.get_requests_for_document`,
				{ doctype: this.frm.doctype, docname: this.frm.docname },
				"GET"
			),
			frappe.require("embedded_list.bundle.js"),
		]).then(([requests]) => {
			if (!requests.length) return;
			this.dialog.set_df_property("requests_section", "hidden", 0);
			const $wrapper = this.dialog.get_field("requests_html").$wrapper;
			new frappe.ui.EmbeddedList({
				wrapper: $('<div class="web-form-request-list"></div>').appendTo($wrapper.empty()),
				show_search: false,
				get_data: () => Promise.resolve(requests),
				columns: this.get_columns(),
			}).refresh();
			$wrapper.on("click", "[data-url]", (e) => {
				frappe.utils.copy_to_clipboard(
					$(e.currentTarget).attr("data-url"),
					__("Web Form Request link copied")
				);
			});
		});
	}

	get_columns() {
		return [
			{
				label: __("ID"),
				fieldname: "name",
				type: "link",
				route: (row) => ["Form", "Web Form Request", row.name],
			},
			{
				label: __("Status"),
				render: (row) =>
					frappe.ui.badge.html({
						label: __(row.status),
						theme: STATUS_THEME[row.status],
					}),
			},
			{
				label: __("Web Form"),
				render: (row) =>
					frappe.utils.escape_html(this.titles[row.web_form] || row.web_form),
			},
			{
				label: __("Expires On"),
				render: (row) =>
					row.expires_on
						? frappe.datetime.str_to_user(
								frappe.datetime.convert_to_user_tz(row.expires_on),
								false,
								true
						  )
						: "",
			},
			{
				render: (row) =>
					row.url
						? frappe.ui.button.html({
								icon: "copy",
								size: "xs",
								variant: "ghost",
								title: __("Copy Link"),
								attrs: { "data-url": row.url },
						  })
						: "",
			},
		];
	}
}
