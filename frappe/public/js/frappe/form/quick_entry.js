frappe.provide("frappe.ui.form");

frappe.quick_edit = function (doctype, name) {
<<<<<<< HEAD
=======
	if (!name) name = doctype; // single
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	frappe.db.get_doc(doctype, name).then((doc) => {
		frappe.ui.form.make_quick_entry(doctype, null, null, doc);
	});
};

frappe.ui.form.make_quick_entry = (doctype, after_insert, init_callback, doc, force) => {
	var trimmed_doctype = doctype.replace(/ /g, "");
	var controller_name = "QuickEntryForm";

	if (frappe.ui.form[trimmed_doctype + "QuickEntryForm"]) {
		controller_name = trimmed_doctype + "QuickEntryForm";
	}

	frappe.quick_entry = new frappe.ui.form[controller_name](
		doctype,
		after_insert,
		init_callback,
		doc,
		force
	);
	return frappe.quick_entry.setup();
};

<<<<<<< HEAD
frappe.ui.form.QuickEntryForm = class QuickEntryForm {
	constructor(doctype, after_insert, init_callback, doc, force) {
=======
frappe.ui.form.QuickEntryForm = class QuickEntryForm extends frappe.ui.Dialog {
	constructor(doctype, after_insert, init_callback, doc, force) {
		super({ auto_make: false });
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		this.doctype = doctype;
		this.after_insert = after_insert;
		this.init_callback = init_callback;
		this.doc = doc;
		this.force = force ? force : false;
<<<<<<< HEAD
=======
		this.dialog = this; // for backward compatibility
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	}

	setup() {
		return new Promise((resolve) => {
			frappe.model.with_doctype(this.doctype, () => {
				this.check_quick_entry_doc();
				this.set_meta_and_mandatory_fields();
				if (this.is_quick_entry() || this.force) {
<<<<<<< HEAD
=======
					this.setup_script_manager();
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
					this.render_dialog();
					resolve(this);
				} else {
					// no quick entry, open full form
					frappe.quick_entry = null;
					frappe
						.set_route("Form", this.doctype, this.doc.name)
						.then(() => resolve(this));
					// call init_callback for consistency
					if (this.init_callback) {
						this.init_callback(this.doc);
					}
				}
			});
		});
	}

	set_meta_and_mandatory_fields() {
		this.meta = frappe.get_meta(this.doctype);
		let fields = this.meta.fields;

<<<<<<< HEAD
		this.mandatory = fields.filter((df) => {
=======
		this.docfields = fields.filter((df) => {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			return (
				(df.reqd || df.allow_in_quick_entry) &&
				!df.read_only &&
				!df.is_virtual &&
				df.fieldtype !== "Tab Break"
			);
		});
	}

	check_quick_entry_doc() {
		if (!this.doc) {
			this.doc = frappe.model.get_new_doc(this.doctype, null, null, true);
		}
	}

	is_quick_entry() {
		if (this.meta.quick_entry != 1) {
			return false;
		}

		this.validate_for_prompt_autoname();

<<<<<<< HEAD
		if (this.has_child_table() || !this.mandatory.length) {
=======
		if (this.has_child_table() || !this.docfields.length) {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			return false;
		}

		return true;
	}

	too_many_mandatory_fields() {
<<<<<<< HEAD
		if (this.mandatory.length > 7) {
=======
		if (this.docfields.length > 7) {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			// too many fields, show form
			return true;
		}
		return false;
	}

	has_child_table() {
		if (
<<<<<<< HEAD
			$.map(this.mandatory, function (d) {
=======
			$.map(this.docfields, function (d) {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
				return d.fieldtype === "Table" ? d : null;
			}).length
		) {
			// has mandatory table, quit!
			return true;
		}
		return false;
	}

	validate_for_prompt_autoname() {
		if (this.meta.autoname && this.meta.autoname.toLowerCase() === "prompt") {
<<<<<<< HEAD
			this.mandatory = [
=======
			this.docfields = [
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
				{
					fieldname: "__newname",
					label: __("{0} Name", [__(this.meta.name)]),
					reqd: 1,
					fieldtype: "Data",
				},
<<<<<<< HEAD
			].concat(this.mandatory);
		}
	}

	render_dialog() {
		var me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("New {0}", [__(this.doctype)]),
			fields: this.mandatory,
			doc: this.doc,
		});

		this.register_primary_action();
		!this.force && this.render_edit_in_full_page_link();
		// ctrl+enter to save
		this.dialog.wrapper.keydown(function (e) {
			if ((e.ctrlKey || e.metaKey) && e.which == 13) {
				if (!frappe.request.ajax_count) {
					// not already working -- double entry
					me.dialog.get_primary_btn().trigger("click");
					e.preventDefault();
					return false;
				}
			}
		});

		this.dialog.onhide = () => (frappe.quick_entry = null);
		this.dialog.show();

		this.dialog.refresh_dependency();
		this.set_defaults();

		if (this.init_callback) {
			this.init_callback(this.dialog);
=======
			].concat(this.docfields);
		}
	}

	setup_script_manager() {
		this.script_manager = new frappe.ui.form.ScriptManager({
			frm: this,
		});
		this.script_manager.setup();
	}

	get mandatory() {
		// Backwards compatibility
		console.warn("QuickEntryForm: .mandatory is deprecated, use .docfields instead");
		return this.docfields;
	}

	set mandatory(value) {
		// Backwards compatibility
		console.warn("QuickEntryForm: .mandatory is deprecated, use .docfields instead");
		this.docfields = value;
	}

	render_dialog() {
		var me = this;

		this.fields = this.docfields;
		this.title = this.get_title();

		super.make();
		this.register_primary_action();
		this.render_edit_in_full_page_link();
		this.setup_cmd_enter_for_save();

		this.onhide = () => (frappe.quick_entry = null);
		this.show();

		this.refresh_dependency();
		this.set_defaults();

		this.script_manager.trigger("refresh");

		if (this.init_callback) {
			this.init_callback(this);
		}
	}

	get_title() {
		if (this.title) {
			return this.title;
		} else if (this.meta.issingle) {
			return __(this.doctype);
		} else {
			return __("New {0}", [__(this.doctype)]);
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		}
	}

	register_primary_action() {
		var me = this;
<<<<<<< HEAD
		this.dialog.set_primary_action(__("Save"), function () {
=======
		this.set_primary_action(__("Save"), function () {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			if (me.dialog.working) {
				return;
			}
			var data = me.dialog.get_values();

			if (data) {
				me.dialog.working = true;
<<<<<<< HEAD
				me.dialog.set_message(__("Saving..."));
				me.insert().then(() => {
					me.dialog.clear_message();
=======
				me.script_manager.trigger("validate").then(() => {
					me.insert().then(() => {
						let messagetxt = __("{1} saved", [__(me.doctype), this.doc.name.bold()]);
						me.dialog.animation_speed = "slow";
						me.dialog.hide();
						setTimeout(function () {
							frappe.show_alert({ message: messagetxt, indicator: "green" }, 3);
						}, 500);
					});
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
				});
			}
		});
	}

	insert() {
		let me = this;
		return new Promise((resolve) => {
			me.update_doc();
			frappe.call({
				method: "frappe.client.save",
				args: {
					doc: me.dialog.doc,
				},
				callback: function (r) {
<<<<<<< HEAD
					if (frappe.model.is_submittable(me.doctype)) {
=======
					if (
						frappe.model.is_submittable(me.doctype) &&
						!frappe.model.has_workflow(me.doctype)
					) {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
						frappe.run_serially([
							() => (me.dialog.working = true),
							() => {
								me.dialog.set_primary_action(__("Submit"), function () {
									me.submit(r.message);
								});
							},
						]);
					} else {
<<<<<<< HEAD
						me.dialog.hide();
						// delete the old doc
						frappe.model.clear_doc(me.dialog.doc.doctype, me.dialog.doc.name);
						me.dialog.doc = r.message;
						if (frappe._from_link) {
							frappe.ui.form.update_calling_link(me.dialog.doc);
						} else {
							if (me.after_insert) {
								me.after_insert(me.dialog.doc);
							} else {
								me.open_form_if_not_list();
							}
						}
=======
						me.process_after_insert(r);
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
					}
				},
				error: function () {
					if (!me.skip_redirect_on_error) {
						me.open_doc(true);
					}
				},
				always: function () {
					me.dialog.working = false;
					resolve(me.dialog.doc);
				},
<<<<<<< HEAD
				freeze: true,
=======
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			});
		});
	}

	submit(doc) {
		var me = this;
		frappe.call({
			method: "frappe.client.submit",
			args: {
				doc: doc,
			},
			callback: function (r) {
<<<<<<< HEAD
				me.dialog.hide();
				// delete the old doc
				frappe.model.clear_doc(me.dialog.doc.doctype, me.dialog.doc.name);
				me.dialog.doc = r.message;
				if (frappe._from_link) {
					frappe.ui.form.update_calling_link(me.dialog.doc);
				} else {
					if (me.after_insert) {
						me.after_insert(me.dialog.doc);
					} else {
						me.open_form_if_not_list();
					}
				}

=======
				me.process_after_insert(r);
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
				cur_frm && cur_frm.reload_doc();
			},
		});
	}

<<<<<<< HEAD
	open_form_if_not_list() {
		let route = frappe.get_route();
		let doc = this.dialog.doc;
=======
	process_after_insert(r) {
		// delete the old doc
		frappe.model.clear_doc(this.doc.doctype, this.doc.name);
		this.doc = r.message;
		if (this.script_manager.has_handler("after_save")) {
			return this.script_manager.trigger("after_save");
		} else if (frappe._from_link) {
			frappe.ui.form.update_calling_link(this.doc);
		} else if (this.after_insert) {
			this.after_insert(this.doc);
		} else {
			this.open_form_if_not_list();
		}
	}

	setup_cmd_enter_for_save() {
		var me = this;
		// ctrl+enter to save
		this.wrapper.keydown(function (e) {
			if ((e.ctrlKey || e.metaKey) && e.which == 13) {
				if (!frappe.request.ajax_count) {
					// not already working -- double entry
					me.dialog.get_primary_btn().trigger("click");
					e.preventDefault();
					return false;
				}
			}
		});
	}

	open_form_if_not_list() {
		if (this.meta.issingle) return;
		let route = frappe.get_route();
		let doc = this.doc;
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		if (route && !(route[0] === "List" && route[1] === doc.doctype)) {
			frappe.run_serially([() => frappe.set_route("Form", doc.doctype, doc.name)]);
		}
	}

	update_doc() {
		var me = this;
<<<<<<< HEAD
		var data = this.dialog.get_values(true);
=======
		var data = this.get_values(true);
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		$.each(data, function (key, value) {
			if (!is_null(value)) {
				me.dialog.doc[key] = value;
			}
		});
<<<<<<< HEAD
		return this.dialog.doc;
	}

	open_doc(set_hooks) {
		this.dialog.hide();
=======
		return this.doc;
	}

	open_doc(set_hooks) {
		this.hide();
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		this.update_doc();
		if (set_hooks && this.after_insert) {
			frappe.route_options = frappe.route_options || {};
			frappe.route_options.after_save = (frm) => {
				this.after_insert(frm);
			};
		}
		this.doc.__run_link_triggers = false;
		frappe.set_route("Form", this.doctype, this.doc.name);
	}

	render_edit_in_full_page_link() {
<<<<<<< HEAD
		var me = this;
		this.dialog.add_custom_action(__("Edit Full Form"), () => me.open_doc(true));
=======
		if (this.force || this.hide_full_form_button) return;
		this.add_custom_action(__("Edit Full Form"), () => this.open_doc(true));
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	}

	set_defaults() {
		var me = this;
		// set defaults
<<<<<<< HEAD
		$.each(this.dialog.fields_dict, function (fieldname, field) {
=======
		$.each(this.fields_dict, function (fieldname, field) {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			field.doctype = me.doc.doctype;
			field.docname = me.doc.name;

			if (!is_null(me.doc[fieldname])) {
				field.set_input(me.doc[fieldname]);
			}
		});
	}
};
