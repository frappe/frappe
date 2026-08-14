frappe.provide("frappe.contacts");
frappe.provide("frappe.ui.form");

frappe.ui.form.AddressQuickEntryForm = class AddressQuickEntryForm extends (
	frappe.ui.form.QuickEntryForm
) {
	insert() {
		if (this.source_frm) {
			this.dialog.doc.links = [
				{ link_doctype: this.source_frm.doctype, link_name: this.source_frm.docname },
			];
		}
		return super.insert();
	}

	open_form_if_not_list() {
		if (!this.source_frm) return super.open_form_if_not_list();
		this.source_frm.reload_doc();
	}
};

frappe.ui.form.ContactQuickEntryForm = class ContactQuickEntryForm extends (
	frappe.ui.form.AddressQuickEntryForm
) {
	render_dialog() {
		const fields = this.get_detail_fields().map(
			({ table, value_field, primary_flag, ...field }) => field
		);
		this.docfields = this.docfields.concat({ fieldtype: "Column Break" }, ...fields);
		super.render_dialog();
	}

	update_doc() {
		const doc = super.update_doc();

		for (const { fieldname, table, value_field, primary_flag } of this.get_detail_fields()) {
			const value = doc[fieldname];
			delete doc[fieldname];
			if (!value) continue;

			doc[table] = doc[table] || [];
			doc[table].push({ [value_field]: value, [primary_flag]: 1 });
		}

		return doc;
	}

	get_detail_fields() {
		return [
			{
				fieldname: "contact_phone",
				label: __("Phone"),
				fieldtype: "Data",
				options: "Phone",
				table: "phone_nos",
				value_field: "phone",
				primary_flag: "is_primary_phone",
			},
			{
				fieldname: "contact_mobile_no",
				label: __("Mobile No"),
				fieldtype: "Data",
				options: "Phone",
				table: "phone_nos",
				value_field: "phone",
				primary_flag: "is_primary_mobile_no",
			},
			{
				fieldname: "contact_email",
				label: __("Email"),
				fieldtype: "Data",
				options: "Email",
				table: "email_ids",
				value_field: "email_id",
				primary_flag: "is_primary",
			},
		];
	}
};

const PARTY_LINK_SECTIONS = [
	{
		doctype: "Address",
		wrapper_field: "address_html",
		onload_key: "addr_list",
		template: "address_list",
		button_selector: ".btn-address",
		primary_flag: "is_primary_address",
	},
	{
		doctype: "Contact",
		wrapper_field: "contact_html",
		onload_key: "contact_list",
		template: "contact_list",
		button_selector: ".btn-contact",
		primary_flag: "is_primary_contact",
	},
];

class PartyLinkSection {
	constructor(
		frm,
		{ doctype, wrapper_field, onload_key, template, button_selector, primary_flag }
	) {
		this.frm = frm;
		this.doctype = doctype;
		this.wrapper_field = wrapper_field;
		this.onload_key = onload_key;
		this.template = template;
		this.button_selector = button_selector;
		this.primary_flag = primary_flag;
	}

	get is_loaded() {
		const has_wrapper = Boolean(this.frm.fields_dict[this.wrapper_field]);
		return has_wrapper && this.onload_key in (this.frm.doc.__onload || {});
	}

	get records() {
		return this.frm.doc.__onload[this.onload_key] || [];
	}

	get primary_field() {
		return (this.frm.meta.fields || []).find(
			(df) =>
				df.fieldtype === "Link" &&
				df.options === this.doctype &&
				/primary/i.test(df.fieldname)
		)?.fieldname;
	}

	get primary_name() {
		if (this.primary_field) return this.frm.doc[this.primary_field];
		return this.records.find((record) => record[this.primary_flag])?.name;
	}

	render() {
		const primary_name = this.primary_name;
		const records = [...this.records].sort(
			(first, second) => (second.name === primary_name) - (first.name === primary_name)
		);

		const $wrapper = $(this.frm.fields_dict[this.wrapper_field].wrapper).html(
			frappe.render_template(this.template, {
				...this.frm.doc.__onload,
				[this.onload_key]: records,
				primary_name,
			})
		);

		$wrapper.find(this.button_selector).on("click", () => this.create_record());
		this.bind_card_menus($wrapper);
	}

	bind_card_menus($wrapper) {
		const by_name = Object.fromEntries(this.records.map((record) => [record.name, record]));

		$wrapper.find(".card-menu-btn").each((index, trigger) => {
			const record = by_name[trigger.closest("[data-name]")?.dataset.name];
			if (!record) return;
			new frappe.ui.Dropdown({
				trigger,
				options: this.get_menu_options(record),
				align: "end",
			});
		});
	}

	get_menu_options(record) {
		const is_primary = record.name === this.primary_name;
		return [
			{
				label: __("Edit"),
				icon: "pen",
				onclick: () => frappe.set_route("Form", this.doctype, record.name),
			},
			{
				label: __("Set as Primary"),
				icon: "star",
				condition: () => !is_primary,
				onclick: () => this.set_primary(record),
			},
			{
				label: __("Unset as Primary"),
				icon: "star-off",
				condition: () => is_primary,
				onclick: () => this.unset_primary(record),
			},
			{
				label: __("Unlink {0}", [__(this.doctype)]),
				icon: "unlink",
				onclick: () => this.unlink(record),
			},
		];
	}

	create_record() {
		const { frm, doctype } = this;
		frappe.dynamic_link = { doctype: frm.doc.doctype, doc: frm.doc, fieldname: "name" };

		if (frappe.boot.enable_address_autocompletion === 1 && doctype === "Address") {
			new frappe.ui.AddressAutocompleteDialog({
				title: __("New Address"),
				link_doctype: frm.doc.doctype,
				link_name: frm.doc.name,
				after_insert: () => frm.reload_doc(),
			}).show();
		} else {
			frappe.new_doc(doctype, null, (quick_entry) => (quick_entry.source_frm = frm));
		}
	}

	async set_primary(record) {
		if (this.primary_field) {
			await frappe.db.set_value(
				this.frm.doctype,
				this.frm.docname,
				this.primary_field,
				record.name
			);
		} else {
			const previously_primary = this.records.filter(
				(other) => other[this.primary_flag] && other.name !== record.name
			);
			for (const previous of previously_primary) {
				await frappe.db.set_value(this.doctype, previous.name, this.primary_flag, 0);
			}
			await frappe.db.set_value(this.doctype, record.name, this.primary_flag, 1);
		}

		this.frm.reload_doc();
	}

	async unset_primary(record) {
		const primary_field = this.primary_field;

		if (primary_field) {
			const updates = { [primary_field]: null };
			for (const fieldname of this.get_dependent_fields(primary_field)) {
				updates[fieldname] = null;
			}
			await frappe.db.set_value(this.frm.doctype, this.frm.docname, updates);
		} else {
			await frappe.db.set_value(this.doctype, record.name, this.primary_flag, 0);
		}

		this.frm.reload_doc();
	}

	get_dependent_fields(primary_field) {
		return (this.frm.meta.fields || [])
			.filter((df) => df.fetch_from?.split(".")[0] === primary_field)
			.map((df) => df.fieldname);
	}

	unlink(record) {
		const record_label = frappe.utils.bold(record.name);
		const party_label = frappe.utils.bold(this.frm.docname);
		const message = __("Unlink {0} {1} from {2}?", [
			__(this.doctype),
			record_label,
			party_label,
		]);

		frappe.confirm(message, () => this.delink_party(record));
	}

	delink_party(record) {
		return frappe
			.xcall("frappe.contacts.address_and_contact.delink_party", {
				doctype: this.doctype,
				name: record.name,
				link_doctype: this.frm.doctype,
				link_name: this.frm.docname,
			})
			.then(() => {
				frappe.show_alert({
					message: __("{0} unlinked", [__(this.doctype)]),
					indicator: "green",
				});
				this.frm.reload_doc();
			});
	}
}

$.extend(frappe.contacts, {
	clear_address_and_contact: function (frm) {
		for (const wrapper_field of ["address_html", "contact_html"]) {
			$(frm.fields_dict[wrapper_field]?.wrapper)?.html("");
		}
	},

	render_address_and_contact: function (frm) {
		for (const options of PARTY_LINK_SECTIONS) {
			const section = new PartyLinkSection(frm, options);
			if (section.is_loaded) section.render();
		}
	},

	get_last_doc: function (frm) {
		const reverse_routes = frappe.route_history.slice().reverse();
		let last_route = null;
		for (const route of reverse_routes) {
			if (route[0] === "Form" && route[1] === frm.doctype) continue;
			if (route[0] !== "Form") break; // stop at List or other non-Form routes
			last_route = route;
			break;
		}
		let doctype = last_route && last_route[1];
		let docname = last_route && last_route[2];

		if (last_route && last_route.length > 3) docname = last_route.slice(2).join("/");

		return {
			doctype,
			docname,
		};
	},

	get_address_display: function (frm, address_field, display_field) {
		if (frm.updating_party_details) {
			return;
		}

		let _address_field = address_field || "address";
		let _display_field = display_field || "address_display";

		if (!frm.doc[_address_field]) {
			frm.set_value(_display_field, "");
			return;
		}

		frappe
			.xcall("frappe.contacts.doctype.address.address.get_address_display", {
				address_dict: frm.doc[_address_field],
			})
			.then((address_display) => frm.set_value(_display_field, address_display));
	},
});
