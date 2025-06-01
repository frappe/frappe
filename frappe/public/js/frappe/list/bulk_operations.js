export default class BulkOperations {
	constructor({ doctype }) {
		if (!doctype) nts.throw(__("Doctype required"));
		this.doctype = doctype;
	}

	print(docs) {
		const print_settings = nts.model.get_doc(":Print Settings", "Print Settings");
		const allow_print_for_draft = cint(print_settings.allow_print_for_draft);
		const is_submittable = nts.model.is_submittable(this.doctype);
		const allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled);
		const letterheads = this.get_letterhead_options();
		const MAX_PRINT_LIMIT = 500;
		const BACKGROUND_PRINT_THRESHOLD = 25;

		const valid_docs = docs
			.filter((doc) => {
				return (
					!is_submittable ||
					doc.docstatus === 1 ||
					(allow_print_for_cancelled && doc.docstatus == 2) ||
					(allow_print_for_draft && doc.docstatus == 0) ||
					nts.user.has_role("Administrator")
				);
			})
			.map((doc) => doc.name);

		const invalid_docs = docs.filter((doc) => !valid_docs.includes(doc.name));

		if (invalid_docs.length > 0) {
			nts.msgprint(__("You selected Draft or Cancelled documents"));
			return;
		}

		if (valid_docs.length === 0) {
			nts.msgprint(__("Select atleast 1 record for printing"));
			return;
		}

		if (valid_docs.length > MAX_PRINT_LIMIT) {
			nts.msgprint(
				__("You can only print upto {0} documents at a time", [MAX_PRINT_LIMIT])
			);
			return;
		}

		const dialog = new nts.ui.Dialog({
			title: __("Print Documents"),
			fields: [
				{
					fieldtype: "Select",
					label: __("Letter Head"),
					fieldname: "letter_sel",
					options: letterheads,
					default: letterheads[0],
				},
				{
					fieldtype: "Select",
					label: __("Print Format"),
					fieldname: "print_sel",
					options: nts.meta.get_print_formats(this.doctype),
					default: nts.get_meta(this.doctype).default_print_format,
				},
				{
					fieldtype: "Select",
					label: __("Page Size"),
					fieldname: "page_size",
					options: nts.meta.get_print_sizes(),
					default: print_settings.pdf_page_size,
				},
				{
					fieldtype: "Float",
					label: __("Page Height (in mm)"),
					fieldname: "page_height",
					depends_on: 'eval:doc.page_size == "Custom"',
					default: print_settings.pdf_page_height,
				},
				{
					fieldtype: "Float",
					label: __("Page Width (in mm)"),
					fieldname: "page_width",
					depends_on: 'eval:doc.page_size == "Custom"',
					default: print_settings.pdf_page_width,
				},
				{
					fieldtype: "Check",
					label: __("Background Print (required for >25 documents)"),
					fieldname: "background_print",
					default: valid_docs.length > BACKGROUND_PRINT_THRESHOLD,
					read_only: valid_docs.length > BACKGROUND_PRINT_THRESHOLD,
				},
			],
		});

		dialog.set_primary_action(__("Print"), (args) => {
			if (!args) return;
			const default_print_format = nts.get_meta(this.doctype).default_print_format;
			const with_letterhead = args.letter_sel == __("No Letterhead") ? 0 : 1;
			const print_format = args.print_sel ? args.print_sel : default_print_format;
			const json_string = JSON.stringify(valid_docs);
			const letterhead = args.letter_sel;

			let pdf_options;
			if (args.page_size === "Custom") {
				if (args.page_height === 0 || args.page_width === 0) {
					nts.throw(__("Page height and width cannot be zero"));
				}
				pdf_options = JSON.stringify({
					"page-height": args.page_height,
					"page-width": args.page_width,
				});
			} else {
				pdf_options = JSON.stringify({ "page-size": args.page_size });
			}

			if (args.background_print) {
				nts
					.call("nts.utils.print_format.download_multi_pdf_async", {
						doctype: this.doctype,
						name: json_string,
						format: print_format,
						no_letterhead: with_letterhead ? "0" : "1",
						letterhead: letterhead,
						options: pdf_options,
					})
					.then((response) => {
						let task_id = response.message.task_id;
						nts.realtime.task_subscribe(task_id);
						nts.realtime.on(`task_complete:${task_id}`, (data) => {
							nts.msgprint({
								title: __("Bulk PDF Export"),
								message: __("Your PDF is ready for download"),
								primary_action: {
									label: __("Download PDF"),
									client_action: "window.open",
									args: data.file_url,
								},
							});
							nts.realtime.task_unsubscribe(task_id);
							nts.realtime.off(`task_complete:${task_id}`);
						});
					});
			} else {
				const w = window.open(
					"/api/method/nts.utils.print_format.download_multi_pdf?" +
						"doctype=" +
						encodeURIComponent(this.doctype) +
						"&name=" +
						encodeURIComponent(json_string) +
						"&format=" +
						encodeURIComponent(print_format) +
						"&no_letterhead=" +
						(with_letterhead ? "0" : "1") +
						"&letterhead=" +
						encodeURIComponent(letterhead) +
						"&options=" +
						encodeURIComponent(pdf_options)
				);

				if (!w) {
					nts.msgprint(__("Please enable pop-ups"));
				}
			}
			dialog.hide();
		});
		dialog.show();
	}

	get_letterhead_options() {
		const letterhead_options = [__("No Letterhead")];
		nts.call({
			method: "nts.client.get_list",
			args: {
				doctype: "Letter Head",
				fields: ["name", "is_default"],
				filters: { disabled: 0 },
				limit_page_length: 0,
			},
			async: false,
			callback(r) {
				if (r.message) {
					r.message.forEach((letterhead) => {
						if (letterhead.is_default) {
							letterhead_options.unshift(letterhead.name);
						} else {
							letterhead_options.push(letterhead.name);
						}
					});
				}
			},
		});
		return letterhead_options;
	}

	delete(docnames, done = null) {
		nts
			.call({
				method: "nts.desk.reportview.delete_items",
				freeze: true,
				freeze_message:
					docnames.length <= 10
						? __("Deleting {0} records...", [docnames.length])
						: null,
				args: {
					items: docnames,
					doctype: this.doctype,
				},
			})
			.then((r) => {
				let failed = r.message;
				if (!failed) failed = [];

				if (failed.length && !r._server_messages) {
					nts.throw(
						__("Cannot delete {0}", [failed.map((f) => f.bold()).join(", ")])
					);
				}
				if (failed.length < docnames.length) {
					nts.utils.play_sound("delete");
					if (done) done();
				}
			});
	}

	assign(docnames, done) {
		if (docnames.length > 0) {
			const assign_to = new nts.ui.form.AssignToDialog({
				obj: this,
				method: "nts.desk.form.assign_to.add_multiple",
				doctype: this.doctype,
				docname: docnames,
				bulk_assign: true,
				re_assign: true,
				callback: done,
			});
			assign_to.dialog.clear();
			assign_to.dialog.show();
		} else {
			nts.msgprint(__("Select records for assignment"));
		}
	}

	clear_assignment(docnames, done) {
		if (docnames.length > 0) {
			nts
				.call({
					method: "nts.desk.form.assign_to.remove_multiple",
					args: {
						doctype: this.doctype,
						names: docnames,
						ignore_permissions: true,
					},
					freeze: true,
					freeze_message: "Removing assignments...",
				})
				.then(() => {
					done();
				});
		} else {
			nts.msgprint(__("Select records for removing assignment"));
		}
	}

	apply_assignment_rule(docnames, done) {
		if (docnames.length > 0) {
			nts
				.call("nts.automation.doctype.assignment_rule.assignment_rule.bulk_apply", {
					doctype: this.doctype,
					docnames: docnames,
				})
				.then(() => done());
		}
	}

	submit_or_cancel(docnames, action = "submit", done = null) {
		action = action.toLowerCase();
		const task_id = Math.random().toString(36).slice(-5);
		nts.realtime.task_subscribe(task_id);
		return nts
			.xcall("nts.desk.doctype.bulk_update.bulk_update.submit_cancel_or_update_docs", {
				doctype: this.doctype,
				action: action,
				docnames: docnames,
				task_id: task_id,
			})
			.then((failed_docnames) => {
				if (failed_docnames?.length) {
					const comma_separated_records = nts.utils.comma_and(failed_docnames);
					switch (action) {
						case "submit":
							nts.throw(__("Cannot submit {0}.", [comma_separated_records]));
							break;
						case "cancel":
							nts.throw(__("Cannot cancel {0}.", [comma_separated_records]));
							break;
						default:
							nts.throw(__("Cannot {0} {1}.", [action, comma_separated_records]));
					}
				}
				if (failed_docnames?.length < docnames.length) {
					nts.utils.play_sound(action);
					if (done) done();
				}
			})
			.finally(() => {
				nts.realtime.task_unsubscribe(task_id);
			});
	}

	edit(docnames, field_mappings, done) {
		let field_options = Object.keys(field_mappings).sort(function (a, b) {
			return __(cstr(field_mappings[a].label)).localeCompare(
				cstr(__(field_mappings[b].label))
			);
		});
		const status_regex = /status/i;

		const default_field = field_options.find((value) => status_regex.test(value));

		const dialog = new nts.ui.Dialog({
			title: __("Bulk Edit"),
			fields: [
				{
					fieldtype: "Select",
					options: field_options,
					default: default_field,
					label: __("Field"),
					fieldname: "field",
					reqd: 1,
					onchange: () => {
						set_value_field(dialog);
					},
				},
				{
					fieldtype: "Data",
					label: __("Value"),
					fieldname: "value",
					onchange() {
						show_help_text();
					},
				},
			],
			primary_action: ({ value }) => {
				const fieldname = field_mappings[dialog.get_value("field")].fieldname;
				dialog.disable_primary_action();
				nts
					.call({
						method: "nts.desk.doctype.bulk_update.bulk_update.submit_cancel_or_update_docs",
						args: {
							doctype: this.doctype,
							freeze: true,
							docnames: docnames,
							action: "update",
							data: {
								[fieldname]: value || null,
							},
						},
					})
					.then((r) => {
						let failed = r.message || [];

						if (failed.length && !r._server_messages) {
							dialog.enable_primary_action();
							nts.throw(
								__("Cannot update {0}", [
									failed.map((f) => (f.bold ? f.bold() : f)).join(", "),
								])
							);
						}
						done();
						dialog.hide();
						nts.show_alert(__("Updated successfully"));
					});
			},
			primary_action_label: __("Update {0} records", [docnames.length]),
		});

		if (default_field) set_value_field(dialog); // to set `Value` df based on default `Field`
		show_help_text();

		function set_value_field(dialogObj) {
			const new_df = Object.assign({}, field_mappings[dialogObj.get_value("field")]);
			/* if the field label has status in it and
			if it has select fieldtype with no default value then
			set a default value from the available option. */
			if (
				new_df.label.match(status_regex) &&
				new_df.fieldtype === "Select" &&
				!new_df.default
			) {
				let options = [];
				if (typeof new_df.options === "string") {
					options = new_df.options.split("\n");
				}
				//set second option as default if first option is an empty string
				new_df.default = options[0] || options[1];
			}
			new_df.label = __("Value");
			new_df.onchange = show_help_text;

			delete new_df.depends_on;
			dialogObj.replace_field("value", new_df);
			show_help_text();
		}

		function show_help_text() {
			let value = dialog.get_value("value");
			if (value == null || value === "") {
				dialog.set_df_property(
					"value",
					"description",
					__("You have not entered a value. The field will be set to empty.")
				);
			} else {
				dialog.set_df_property("value", "description", "");
			}
		}

		dialog.refresh();
		dialog.show();
	}

	add_tags(docnames, done) {
		const dialog = new nts.ui.Dialog({
			title: __("Add Tags"),
			fields: [
				{
					fieldtype: "MultiSelectPills",
					fieldname: "tags",
					label: __("Tags"),
					reqd: true,
					get_data: function (txt) {
						return nts.db.get_link_options("Tag", txt);
					},
				},
			],
			primary_action_label: __("Add"),
			primary_action: () => {
				let args = dialog.get_values();
				if (args && args.tags) {
					dialog.set_message("Adding Tags...");

					nts.call({
						method: "nts.desk.doctype.tag.tag.add_tags",
						args: {
							tags: args.tags,
							dt: this.doctype,
							docs: docnames,
						},
						callback: () => {
							dialog.hide();
							done();
						},
					});
				}
			},
		});
		dialog.show();
	}

	export(doctype, docnames) {
		nts.require("data_import_tools.bundle.js", () => {
			const data_exporter = new nts.data_import.DataExporter(
				doctype,
				"Insert New Records"
			);
			data_exporter.dialog.set_value("export_records", "by_filter");
			data_exporter.filter_group.add_filters_to_filter_group([
				[doctype, "name", "in", docnames, false],
			]);
		});
	}
}
