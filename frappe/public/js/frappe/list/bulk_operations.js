export default class BulkOperations {
	constructor({ doctype }) {
		if (!doctype) frappe.throw(__('Doctype required'));
		this.doctype = doctype;
	}

	print(docs) {
		const print_settings = frappe.model.get_doc(':Print Settings', 'Print Settings');
		const allow_print_for_draft = cint(print_settings.allow_print_for_draft);
		const is_submittable = frappe.model.is_submittable(this.doctype);
		const allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled);

		const valid_docs = docs.filter(doc => {
			return !is_submittable || doc.docstatus === 1 ||
				(allow_print_for_cancelled && doc.docstatus == 2) ||
				(allow_print_for_draft && doc.docstatus == 0) ||
				frappe.user.has_role('Administrator');
		}).map(doc => doc.name);

		const invalid_docs = docs.filter(doc => !valid_docs.includes(doc.name));

		if (invalid_docs.length > 0) {
			frappe.msgprint(__('You selected Draft or Cancelled documents'));
			return;
		}

		if (valid_docs.length > 0) {
			const dialog = new frappe.ui.Dialog({
				title: __('Print Documents'),
				fields: [{
					'fieldtype': 'Check',
					'label': __('With Letterhead'),
					'fieldname': 'with_letterhead'
				},
				{
					'fieldtype': 'Select',
					'label': __('Print Format'),
					'fieldname': 'print_sel',
					options: frappe.meta.get_print_formats(this.doctype)
				}]
			});

			dialog.set_primary_action(__('Print'), args => {
				if (!args) return;
				const default_print_format = frappe.get_meta(this.doctype).default_print_format;
				const with_letterhead = args.with_letterhead ? 1 : 0;
				const print_format = args.print_sel ? args.print_sel : default_print_format;
				const json_string = JSON.stringify(valid_docs);

				const w = window.open('/api/method/frappe.utils.print_format.download_multi_pdf?' +
					'doctype=' + encodeURIComponent(this.doctype) +
					'&name=' + encodeURIComponent(json_string) +
					'&format=' + encodeURIComponent(print_format) +
					'&no_letterhead=' + (with_letterhead ? '0' : '1'));
				if (!w) {
					frappe.msgprint(__('Please enable pop-ups'));
					return;
				}
			});

			dialog.show();
		} else {
			frappe.msgprint(__('Select atleast 1 record for printing'));
		}
	}

	delete(docnames, done = null) {
		frappe
			.call({
				method: 'frappe.desk.reportview.delete_items',
				freeze: true,
				args: {
					items: docnames,
					doctype: this.doctype
				}
			})
			.then((r) => {
				let failed = r.message;
				if (!failed) failed = [];

				if (failed.length && !r._server_messages) {
					frappe.throw(__('Cannot delete {0}', [failed.map(f => f.bold()).join(', ')]));
				}
				if (failed.length < docnames.length) {
					frappe.utils.play_sound('delete');
					if (done) done();
				}
			});
	}

	assign(docnames, done) {
		if (docnames.length > 0) {
			const assign_to = new frappe.ui.form.AssignToDialog({
				obj: this,
				method: 'frappe.desk.form.assign_to.add_multiple',
				doctype: this.doctype,
				docname: docnames,
				bulk_assign: true,
				re_assign: true,
				callback: done
			});
			assign_to.dialog.clear();
			assign_to.dialog.show();
		} else {
			frappe.msgprint(__('Select records for assignment'));
		}
	}

	apply_assignment_rule(docnames, done) {
		if (docnames.length > 0) {
			frappe.call('frappe.automation.doctype.assignment_rule.assignment_rule.bulk_apply', {
				doctype: this.doctype,
				docnames: docnames
			}).then(() => done());
		}
	}

	submit_or_cancel(docnames, action='submit', done=null) {
		action = action.toLowerCase();
		frappe
			.call({
				method: 'frappe.desk.doctype.bulk_update.bulk_update.submit_cancel_or_update_docs',
				args: {
					doctype: this.doctype,
					action: action,
					docnames: docnames
				},
			})
			.then((r) => {
				let failed = r.message;
				if (!failed) failed = [];

				if (failed.length && !r._server_messages) {
					frappe.throw(__('Cannot {0} {1}', [action, failed.map(f => f.bold()).join(', ')]));
				}
				if (failed.length < docnames.length) {
					frappe.utils.play_sound(action);
					if (done) done();
				}
			});
	}

	edit(docnames, field_mappings, done) {
		let field_options = Object.keys(field_mappings).sort();
		const status_regex = /status/i;

		const default_field = field_options.find(value => status_regex.test(value));

		const dialog = new frappe.ui.Dialog({
			title: __('Edit'),
			fields: [
				{
					'fieldtype': 'Select',
					'options': field_options,
					'default': default_field,
					'label': __('Field'),
					'fieldname': 'field',
					'reqd': 1,
					'onchange': () => {
						set_value_field(dialog);
					}
				},
				{
					'fieldtype': 'Data',
					'label': __('Value'),
					'fieldname': 'value',
					'reqd': 1
				}
			],
			primary_action: ({ value }) => {
				const fieldname = field_mappings[dialog.get_value('field')].fieldname;
				dialog.disable_primary_action();
				frappe.call({
					method: 'frappe.desk.doctype.bulk_update.bulk_update.submit_cancel_or_update_docs',
					args: {
						doctype: this.doctype,
						freeze: true,
						docnames: docnames,
						action: 'update',
						data: {
							[fieldname]: value
						}
					}
				}).then(r => {
					let failed = r.message || [];

					if (failed.length && !r._server_messages) {
						dialog.enable_primary_action();
						frappe.throw(__('Cannot update {0}', [failed.map(f => f.bold ? f.bold() : f).join(', ')]));
					}
					done();
					dialog.hide();
					frappe.show_alert(__('Updated successfully'));
				});
			},
			primary_action_label: __('Update')
		});

		if (default_field) set_value_field(dialog); // to set `Value` df based on default `Field`

		function set_value_field(dialogObj) {
			const new_df = Object.assign({},
				field_mappings[dialogObj.get_value('field')]);
			/* if the field label has status in it and
			if it has select fieldtype with no default value then
			set a default value from the available option. */
			if(new_df.label.match(status_regex) &&
				new_df.fieldtype === 'Select' && !new_df.default) {
				let options = [];
				if(typeof new_df.options==="string") {
					options = new_df.options.split("\n");
				}
				//set second option as default if first option is an empty string
				new_df.default = options[0] || options[1];
			}
			new_df.label = __('Value');
			new_df.reqd = 1;
			delete new_df.depends_on;
			dialogObj.replace_field('value', new_df);
		}

		dialog.refresh();
		dialog.show();
	}


	add_tags(docnames, done) {
		const dialog = new frappe.ui.Dialog({
			title: __('Add Tags'),
			fields: [
				{
					fieldtype: 'MultiSelectPills',
					fieldname: 'tags',
					label: __("Tags"),
					reqd: true,
					get_data: function(txt) {
						return frappe.db.get_link_options("Tag", txt);
					}
				},
			],
			primary_action_label: __("Add"),
			primary_action: () => {
				let args = dialog.get_values();
				if (args && args.tags) {
					dialog.set_message("Adding Tags...");

					frappe.call({
						method: "frappe.desk.doctype.tag.tag.add_tags",
						args: {
							'tags': args.tags,
							'dt': this.doctype,
							'docs': docnames,
						},
						callback: () => {
							dialog.hide();
							done();
						}
					});
				}
			},
		});
		dialog.show();
	}
}
