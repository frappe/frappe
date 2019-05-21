frappe.ui.form.Controller = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	}
});

frappe.ui.form.Form = class FrappeForm {
	constructor(doctype, parent, in_form) {
		this.docname = '';
		this.doctype = doctype;
		this.hidden = false;
		this.refresh_if_stale_for = 120;

		var me = this;
		this.opendocs = {};
		this.custom_buttons = {};
		this.sections = [];
		this.grids = [];
		this.cscript = new frappe.ui.form.Controller({frm:this});
		this.events = {};
		this.pformat = {};
		this.fetch_dict = {};
		this.parent = parent;

		this.setup_meta(doctype);

		// show in form instead of in dialog, when called using url (router.js)
		this.in_form = in_form ? true : false;

		// notify on rename
		$(document).on('rename', function(event, dt, old_name, new_name) {
			if(dt==me.doctype)
				me.rename_notify(dt, old_name, new_name);
		});
	}

	setup_meta() {
		this.meta = frappe.get_doc('DocType', this.doctype);
		this.perm = frappe.perm.get_perm(this.doctype); // for create
		if(this.meta.istable) {
			this.meta.in_dialog = 1;
		}
	}

	setup() {
		this.fields = [];
		this.fields_dict = {};
		this.state_fieldname = frappe.workflow.get_state_fieldname(this.doctype);

		// wrapper
		this.wrapper = this.parent;
		this.$wrapper = $(this.wrapper);
		frappe.ui.make_app_page({
			parent: this.wrapper,
			single_column: this.meta.hide_toolbar
		});
		this.page = this.wrapper.page;
		this.layout_main = this.page.main.get(0);

		this.toolbar = new frappe.ui.form.Toolbar({
			frm: this,
			page: this.page
		});

		// print layout
		this.setup_print_layout();

		// 2 column layout
		this.setup_std_layout();

		// client script must be called after "setup" - there are no fields_dict attached to the frm otherwise
		this.script_manager = new frappe.ui.form.ScriptManager({
			frm: this
		});
		this.script_manager.setup();
		this.watch_model_updates();

		if(!this.meta.hide_toolbar) {
			this.footer = new frappe.ui.form.Footer({
				frm: this,
				parent: $('<div>').appendTo(this.page.main.parent())
			});
			$("body").attr("data-sidebar", 1);
		}
		this.setup_file_drop();

		this.setup_done = true;
	}

	setup_print_layout() {
		this.print_preview = new frappe.ui.form.PrintPreview({
			frm: this
		});

		// show edit button for print view
		this.page.wrapper.on('view-change', () => {
			this.toolbar.set_primary_action();
		});
	}

	setup_std_layout() {
		this.form_wrapper 	= $('<div></div>').appendTo(this.layout_main);
		this.body 			= $('<div></div>').appendTo(this.form_wrapper);

		// only tray
		this.meta.section_style='Simple'; // always simple!

		// layout
		this.layout = new frappe.ui.form.Layout({
			parent: this.body,
			doctype: this.doctype,
			frm: this,
			with_dashboard: true
		});
		this.layout.make();

		this.fields_dict = this.layout.fields_dict;
		this.fields = this.layout.fields_list;

		this.dashboard = new frappe.ui.form.Dashboard({
			frm: this,
		});

		// workflow state
		this.states = new frappe.ui.form.States({
			frm: this
		});
	}

	watch_model_updates() {
		// watch model updates
		var me = this;

		// on main doc
		frappe.model.on(me.doctype, "*", function(fieldname, value, doc) {
			// set input
			if(doc.name===me.docname) {
				if ((value==='' || value===null) && !doc[fieldname]) {
					// both the incoming and outgoing values are falsy
					// the texteditor, summernote, changes nulls to empty strings on render,
					// so ignore those changes
				} else {
					me.dirty();
				}
				me.fields_dict[fieldname]
					&& me.fields_dict[fieldname].refresh(fieldname);

				me.layout.refresh_dependency();
				let object = me.script_manager.trigger(fieldname, doc.doctype, doc.name);
				return object;
			}
		});

		// on table fields
		var table_fields = frappe.get_children("DocType", me.doctype, "fields", {
			fieldtype: ["in", frappe.model.table_fields]
		});

		// using $.each to preserve df via closure
		$.each(table_fields, function(i, df) {
			frappe.model.on(df.options, "*", function(fieldname, value, doc) {
				if(doc.parent===me.docname && doc.parentfield===df.fieldname) {
					me.dirty();
					me.fields_dict[df.fieldname].grid.set_value(fieldname, value, doc);
					me.script_manager.trigger(fieldname, doc.doctype, doc.name);
				}
			});
		});
	}

	setup_file_drop() {
		var me = this;
		this.$wrapper.on('dragenter dragover', false)
			.on('drop', function(e) {
				var dataTransfer = e.originalEvent.dataTransfer;
				if (!(dataTransfer && dataTransfer.files && dataTransfer.files.length > 0)) {
					return;
				}

				e.stopPropagation();
				e.preventDefault();

				if(me.doc.__islocal) {
					frappe.msgprint(__("Please save before attaching."));
					throw "attach error";
				}

				if(me.attachments.max_reached()) {
					frappe.msgprint(__("Maximum Attachment Limit for this record reached."));
					throw "attach error";
				}

				new frappe.ui.FileUploader({
					doctype: me.doctype,
					docname: me.docname,
					files: dataTransfer.files,
					on_success(file_doc) {
						me.attachments.attachment_uploaded(file_doc);
					}
				});
			});
	}

	// REFRESH

	refresh(docname) {
		var switched = docname ? true : false;

		if(docname) {
			this.switch_doc(docname);
		}

		cur_frm = this;

		if(this.docname) { // document to show

			// set the doc
			this.doc = frappe.get_doc(this.doctype, this.docname);

			// check permissions
			if(!this.has_permission()) {
				frappe.show_not_permitted(__(this.doctype) + " " + __(this.docname));
				return;
			}

			// read only (workflow)
			this.read_only = frappe.workflow.is_read_only(this.doctype, this.docname);
			if (this.read_only) this.set_read_only(true);

			// check if doctype is already open
			if (!this.opendocs[this.docname]) {
				this.check_doctype_conflict(this.docname);
			} else {
				if (this.check_reload()) {
					return;
				}
			}

			// do setup
			if(!this.setup_done) {
				this.setup();
			}

			// load the record for the first time, if not loaded (call 'onload')
			this.trigger_onload(switched);

			// if print format is shown, refresh the format
			if(this.print_preview.wrapper.is(":visible")) {
				this.print_preview.preview();
			}

			if(switched) {
				if(this.show_print_first && this.doc.docstatus===1) {
					// show print view
					this.print_doc();
				}
			}

			// set status classes
			this.$wrapper.removeClass('validated-form')
				.toggleClass('editable-form', this.doc.docstatus===0)
				.toggleClass('submitted-form', this.doc.docstatus===1)
				.toggleClass('cancelled-form', this.doc.docstatus===2);

			this.show_conflict_message();
		}
	}

	switch_doc(docname) {
		// record switch
		if(this.docname != docname && (!this.meta.in_dialog || this.in_form) && !this.meta.istable) {
			frappe.utils.scroll_to(0);
			this.print_preview.hide();
		}
		// reset visible columns, since column headings can change in different docs
		this.grids.forEach(grid_obj => grid_obj.grid.visible_columns = null);
		frappe.ui.form.close_grid_form();
		this.docname = docname;
	}

	check_reload() {
		if(this.doc && (!this.doc.__unsaved) && this.doc.__last_sync_on &&
			(new Date() - this.doc.__last_sync_on) > (this.refresh_if_stale_for * 1000)) {
			this.reload_doc();
			return true;
		}
	}

	trigger_onload(switched) {
		this.cscript.is_onload = false;
		if(!this.opendocs[this.docname]) {
			var me = this;
			this.cscript.is_onload = true;
			this.initialize_new_doc();
			$(document).trigger("form-load", [this]);
			$(this.page.wrapper).on('hide',  function() {
				$(document).trigger("form-unload", [me]);
			});
		} else {
			this.render_form(switched);
			if (this.doc.localname) {
				// trigger form-rename and remove .localname
				delete this.doc.localname;
				$(document).trigger("form-rename", [this]);
			}
		}
	}

	initialize_new_doc() {
		// moved this call to refresh function
		// this.check_doctype_conflict(docname);
		var me = this;

		// hide any open grid
		this.script_manager.trigger("before_load", this.doctype, this.docname)
			.then(() => {
				me.script_manager.trigger("onload");
				me.opendocs[me.docname] = true;
				me.render_form();

				frappe.after_ajax(function() {
					me.trigger_link_fields();
				});

				frappe.breadcrumbs.add(me.meta.module, me.doctype);
			});

		// update seen
		if(this.meta.track_seen) {
			$('.list-id[data-name="'+ me.docname +'"]').addClass('seen');
		}
	}

	render_form(switched) {
		if(!this.meta.istable) {
			this.layout.doc = this.doc;
			this.layout.attach_doc_and_docfields();

			this.sidebar = new frappe.ui.form.Sidebar({
				frm: this,
				page: this.page
			});
			this.sidebar.make();

			// clear layout message
			this.layout.show_message();

			frappe.run_serially([
				// header must be refreshed before client methods
				// because add_custom_button
				() => this.refresh_header(switched),
				// trigger global trigger
				// to use this
				() => $(document).trigger('form-refresh', [this]),
				// fields
				() => this.refresh_fields(),
				// call trigger
				() => this.script_manager.trigger("refresh"),
				// call onload post render for callbacks to be fired
				() => {
					if(this.cscript.is_onload) {
						return this.script_manager.trigger("onload_post_render");
					}
				},
				() => this.dashboard.after_refresh()
			]);
			// focus on first input

			if(this.is_new()) {
				var first = this.form_wrapper.find('.form-layout input:first');
				if(!in_list(["Date", "Datetime"], first.attr("data-fieldtype"))) {
					first.focus();
				}
			}
		} else {
			this.refresh_header(switched);
		}

		this.$wrapper.trigger('render_complete');

		if(!this.hidden) {
			this.layout.show_empty_form_message();
		}

		this.scroll_to_element();
	}

	refresh_fields() {
		this.layout.refresh(this.doc);
		this.layout.primary_button = this.$wrapper.find(".btn-primary");

		// cleanup activities after refresh
		this.cleanup_refresh(this);
	}

	cleanup_refresh() {
		if(this.fields_dict['amended_from']) {
			if (this.doc.amended_from) {
				unhide_field('amended_from');
				if (this.fields_dict['amendment_date']) unhide_field('amendment_date');
			} else {
				hide_field('amended_from');
				if (this.fields_dict['amendment_date']) hide_field('amendment_date');
			}
		}

		if(this.fields_dict['trash_reason']) {
			if(this.doc.trash_reason && this.doc.docstatus == 2) {
				unhide_field('trash_reason');
			} else {
				hide_field('trash_reason');
			}
		}

		if(this.meta.autoname && this.meta.autonathis.substr(0,6)=='field:' && !this.doc.__islocal) {
			var fn = this.meta.autonathis.substr(6);

			if (this.doc[fn]) {
				this.toggle_display(fn, false);
			}
		}

		if(this.meta.autoname=="naming_series:" && !this.doc.__islocal) {
			this.toggle_display("naming_series", false);
		}
	}

	refresh_header(switched) {
		// set title
		// main title
		if(!this.meta.in_dialog || this.in_form) {
			frappe.utils.set_title(this.meta.issingle ? this.doctype : this.docname);
		}

		// show / hide buttons
		if(this.toolbar) {
			if (switched) {
				this.toolbar.current_status = undefined;
			}
			this.toolbar.refresh();
		}

		this.dashboard.refresh();

		this.show_submit_message();
		this.clear_custom_buttons();
		this.show_web_link();
	}

	// SAVE

	save_or_update() {
		if(this.save_disabled) return;

		if(this.doc.docstatus===0) {
			this.save();
		} else if(this.doc.docstatus===1 && this.doc.__unsaved) {
			this.save("Update");
		}
	}

	save(save_action, callback, btn, on_error) {
		let me = this;
		return new Promise((resolve, reject) => {
			btn && $(btn).prop("disabled", true);
			$(document.activeElement).blur();

			frappe.ui.form.close_grid_form();
			// let any pending js process finish
			setTimeout(function() {
				me.validate_and_save(save_action, callback, btn, on_error, resolve, reject);
			}, 100);
		}).then(() => {
			me.show_success_action();
		}).catch((e) => {
			console.error(e);
		});
	}

	validate_and_save(save_action, callback, btn, on_error, resolve, reject) {
		var me = this;
		if(!save_action) save_action = "Save";
		this.validate_form_action(save_action, resolve);

		if((!this.meta.in_dialog || this.in_form) && !this.meta.istable) {
			frappe.utils.scroll_to(0);
		}
		var after_save = function(r) {
			if(!r.exc) {
				if (["Save", "Update", "Amend"].indexOf(save_action)!==-1) {
					frappe.utils.play_sound("click");
				}

				me.script_manager.trigger("after_save");
				me.refresh();
			} else {
				if(on_error) {
					on_error();
					reject();
				}
			}
			callback && callback(r);
			resolve();
		};

		var fail = () => {
			btn && $(btn).prop("disabled", false);
			if(on_error) {
				on_error();
				reject();
			}
		};

		if(save_action != "Update") {
			// validate
			frappe.validated = true;
			frappe.run_serially([
				() => this.script_manager.trigger("validate"),
				() => this.script_manager.trigger("before_save"),
				() => {
					if(!frappe.validated) {
						fail();
						return;
					}

					frappe.ui.form.save(me, save_action, after_save, btn);
				}
			]).catch(fail);
		} else {
			frappe.ui.form.save(me, save_action, after_save, btn);
		}
	}

	savesubmit(btn, callback, on_error) {
		var me = this;
		return new Promise(resolve => {
			this.validate_form_action("Submit");
			frappe.confirm(__("Permanently Submit {0}?", [this.docname]), function() {
				frappe.validated = true;
				me.script_manager.trigger("before_submit").then(function() {
					if(!frappe.validated) {
						return me.handle_save_fail(btn, on_error);
					}

					me.save('Submit', function(r) {
						if(r.exc) {
							me.handle_save_fail(btn, on_error);
						} else {
							frappe.utils.play_sound("submit");
							callback && callback();
							me.script_manager.trigger("on_submit")
								.then(() => resolve(me));
						}
					}, btn, () => me.handle_save_fail(btn, on_error), resolve);
				});
			}, () => me.handle_save_fail(btn, on_error) );
		});
	}

	savecancel(btn, callback, on_error) {
		var me = this;

		this.validate_form_action('Cancel');
		frappe.confirm(__("Permanently Cancel {0}?", [this.docname]), function() {
			frappe.validated = true;
			me.script_manager.trigger("before_cancel").then(function() {
				if(!frappe.validated) {
					return me.handle_save_fail(btn, on_error);
				}

				var after_cancel = function(r) {
					if(r.exc) {
						me.handle_save_fail(btn, on_error);
					} else {
						frappe.utils.play_sound("cancel");
						me.refresh();
						callback && callback();
						me.script_manager.trigger("after_cancel");
					}
				};
				frappe.ui.form.save(me, "cancel", after_cancel, btn);
			});
		}, () => me.handle_save_fail(btn, on_error));
	}

	savetrash() {
		this.validate_form_action("Delete");
		frappe.model.delete_doc(this.doctype, this.docname, function() {
			window.history.back();
		});
	}

	amend_doc() {
		if(!this.fields_dict['amended_from']) {
			alert('"amended_from" field must be present to do an amendment.');
			return;
		}
		this.validate_form_action("Amend");
		var me = this;
		var fn = function(newdoc) {
			newdoc.amended_from = me.docname;
			if(me.fields_dict && me.fields_dict['amendment_date'])
				newdoc.amendment_date = frappe.datetime.obj_to_str(new Date());
		};
		this.copy_doc(fn, 1);
		frappe.utils.play_sound("click");
	}

	// HELPERS

	enable_save = function() {
		this.save_disabled = false;
		this.toolbar.set_primary_action();
	}

	disable_save() {
		// IMPORTANT: this function should be called in refresh event
		this.save_disabled = true;
		this.toolbar.current_status = null;
		this.page.clear_primary_action();
	}

	handle_save_fail(btn, on_error) {
		$(btn).prop('disabled', false);
		if (on_error) {
			on_error();
		}
	}

	trigger_link_fields() {
		// trigger link fields which have default values set
		if (this.is_new() && this.doc.__run_link_triggers) {
			$.each(this.fields_dict, function(fieldname, field) {
				if (field.df.fieldtype=="Link" && this.doc[fieldname]) {
					// triggers add fetch, sets value in model and runs triggers
					field.set_value(this.doc[fieldname]);
				}
			});

			delete this.doc.__run_link_triggers;
		}
	}

	show_conflict_message() {
		if(this.doc.__needs_refresh) {
			if(this.doc.__unsaved) {
				this.dashboard.clear_headline();
				this.dashboard.set_headline_alert(__("This form has been modified after you have loaded it")
					+ '<a class="btn btn-xs btn-primary pull-right" onclick="cur_frm.reload_doc()">'
					+ __("Refresh") + '</a>', "alert-warning");
			} else {
				this.reload_doc();
			}
		}
	}

	show_submit_message() {
		if(this.meta.is_submittable
			&& this.perm[0] && this.perm[0].submit
			&& !this.is_dirty()
			&& !this.is_new()
			&& !frappe.model.has_workflow(this.doctype) // show only if no workflow
			&& this.doc.docstatus===0) {
			this.dashboard.add_comment(__('Submit this document to confirm'), 'blue', true);
		}
	}

	show_web_link() {
		if(!this.doc.__islocal && this.doc.__onload && this.doc.__onload.is_website_generator) {
			this.web_link && this.web_link.remove();
			if(this.doc.__onload.published) {
				this.add_web_link("/" + this.doc.route);
			}
		}
	}

	add_web_link(path, label) {
		label = label || "See on Website";
		this.web_link = this.sidebar.add_user_action(__(label),
			function() {}).attr("href", path || this.doc.route).attr("target", "_blank");
	}

	has_permission() {
		// get perm
		var dt = this.parent_doctype ? this.parent_doctype : this.doctype;
		this.perm = frappe.perm.get_perm(dt, this.doc);

		if(!this.perm[0].read) {
			return 0;
		}
		return 1;
	}

	check_doctype_conflict(docname) {
		if(this.doctype=='DocType' && docname=='DocType') {
			frappe.msgprint(__('Allowing DocType, DocType. Be careful!'));
		} else if(this.doctype=='DocType') {
			if (frappe.views.formview[docname] || frappe.pages['List/'+docname]) {
				window.location.reload();
				//	frappe.msgprint(__("Cannot open {0} when its instance is open", ['DocType']))
				// throw 'doctype open conflict'
			}
		} else {
			if (frappe.views.formview.DocType && frappe.views.formview.DocType.frm.opendocs[this.doctype]) {
				window.location.reload();
				//	frappe.msgprint(__("Cannot open instance when its {0} is open", ['DocType']))
				// throw 'doctype open conflict'
			}
		}
	}

	// rename the form
	// notify this form of renamed records
	rename_notify(dt, old, name) {
		// from form
		if(this.meta.istable)
			return;

		if(this.docname == old)
			this.docname = name;
		else
			return;

		// cleanup
		if(this && this.opendocs[old] && frappe.meta.docfield_copy[dt]) {
			// delete docfield copy
			frappe.meta.docfield_copy[dt][name] = frappe.meta.docfield_copy[dt][old];
			delete frappe.meta.docfield_copy[dt][old];
		}

		delete this.opendocs[old];
		this.opendocs[name] = true;

		if(this.meta.in_dialog || !this.in_form) {
			return;
		}

		frappe.re_route[window.location.hash] = '#Form/' + encodeURIComponent(this.doctype) + '/' + encodeURIComponent(name);
		frappe.set_route('Form', this.doctype, name);
	}

	// UTILITIES

	print_doc() {
		this.print_preview.toggle();
	}

	rename_doc() {
		frappe.model.rename_doc(this.doctype, this.docname);
	}

	share_doc() {
		this.shared.show();
	}

	email_doc(message) {
		new frappe.views.CommunicationComposer({
			doc: this.doc,
			frm: this,
			subject: __(this.meta.name) + ': ' + this.docname,
			recipients: this.doc.email || this.doc.email_id || this.doc.contact_email,
			attach_document_print: true,
			message: message,
			real_name: this.doc.real_name || this.doc.contact_display || this.doc.contact_name
		});
	}

	copy_doc(onload, from_amend) {
		this.validate_form_action("Create");
		var newdoc = frappe.model.copy_doc(this.doc, from_amend);

		newdoc.idx = null;
		newdoc.__run_link_triggers = false;
		if(onload) {
			onload(newdoc);
		}
		frappe.set_route('Form', newdoc.doctype, newdoc.name);
	}

	reload_doc() {
		this.check_doctype_conflict(this.docname);

		if(!this.doc.__islocal) {
			frappe.model.remove_from_locals(this.doctype, this.docname);
			frappe.model.with_doc(this.doctype, this.docname, () => {
				this.refresh();
			});
		}
	}

	refresh_field(fname) {
		if(this.fields_dict[fname] && this.fields_dict[fname].refresh) {
			this.fields_dict[fname].refresh();
			this.layout.refresh_dependency();
		}
	}

	dirty() {
		this.doc.__unsaved = 1;
		this.$wrapper.trigger('dirty');
	}

	get_docinfo() {
		return frappe.model.docinfo[this.doctype][this.docname];
	}

	is_dirty() {
		return this.doc.__unsaved;
	}

	is_new = function() {
		return this.doc.__islocal;
	}

};
