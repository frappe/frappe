frappe.provide('frappe.ui.form');

import './quick_entry';
import './toolbar';
import './dashboard';
import './workflow';
import './save';
import './print';
import './success_action';
import './script_manager';
import './script_helpers';
import './sidebar/form_sidebar';
import './footer/footer';

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

		if(this.meta.istable) {
			this.meta.in_dialog = 1;
		}

		this.perm = frappe.perm.get_perm(this.doctype); // for create
		this.action_perm_type_map = {
			"Create": "create",
			"Save": "write",
			"Submit": "submit",
			"Update": "submit",
			"Cancel": "cancel",
			"Amend": "amend",
			"Delete": "delete"
		};
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

		// navigate records keyboard shortcuts
		this.add_nav_keyboard_shortcuts();

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
		this.setup_doctype_actions();

		this.setup_done = true;
	}

	add_nav_keyboard_shortcuts() {
		frappe.ui.keys.add_shortcut({
			shortcut: 'shift+ctrl+>',
			action: () => this.navigate_records(0),
			page: this.page,
			description: __('Go to next record'),
			ignore_inputs: true,
			condition: () => !this.is_new()
		});

		frappe.ui.keys.add_shortcut({
			shortcut: 'shift+ctrl+<',
			action: () => this.navigate_records(1),
			page: this.page,
			description: __('Go to previous record'),
			ignore_inputs: true,
			condition: () => !this.is_new()
		});
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
				me.dirty();

				let field = me.fields_dict[fieldname];
				field && field.refresh(fieldname);

				// Validate value for link field explicitly
				field && ["Link", "Dynamic Link"].includes(field.df.fieldtype) && field.validate && field.validate(value);

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
					folder: 'Home/Attachments',
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
			if(!this.has_read_permission()) {
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

	// sets up the refresh event for custom buttons
	// added via configuration
	setup_doctype_actions() {
		if (this.meta.actions) {
			for (let action of this.meta.actions) {
				frappe.ui.form.on(this.doctype, 'refresh', () => {
					if (!this.is_new()) {
						this.add_custom_button(action.label, () => {
							if (action.action_type==='Server Action') {
								frappe.xcall(action.action, {doc: this.doc}).then(() => {
									frappe.msgprint({
										message: __('{} Complete', [action.label]),
										alert: true
									});
								});
							}
						}, action.group);
					}
				});
			}
		}
	}

	switch_doc(docname) {
		// record switch
		if(this.docname != docname && (!this.meta.in_dialog || this.in_form) && !this.meta.istable) {
			if (this.print_preview) {
				this.print_preview.hide();
			}
		}
		// reset visible columns, since column headings can change in different docs
		this.grids.forEach(grid_obj => {
			grid_obj.grid.visible_columns = null
			// reset page number to 1
			grid_obj.grid.grid_pagination.go_to_page(1);
		});
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
				() => this.run_after_load_hook(),
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

	run_after_load_hook() {
		if (frappe.route_hooks.after_load) {
			let route_callback = frappe.route_hooks.after_load;
			delete frappe.route_hooks.after_load;

			route_callback(this);
		}
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

		if(this.meta.autoname && this.meta.autoname.substr(0,6)=='field:' && !this.doc.__islocal) {
			var fn = this.meta.autoname.substr(6);

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
			console.error(e); // eslint-disable-line
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

				if (frappe.route_hooks.after_save) {
					let route_callback = frappe.route_hooks.after_save;
					delete frappe.route_hooks.after_save;

					route_callback(me);
				}
				// submit comment if entered
				if (me.timeline) {
					me.timeline.comment_area.submit();
				}
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

		var fail = (e) => {
			if (e) {
				console.error(e)
			}
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
								.then(() => resolve(me))
								.then(() => {
									if (frappe.route_hooks.after_submit) {
										let route_callback = frappe.route_hooks.after_submit;
										delete frappe.route_hooks.after_submit;
										route_callback(me);
									}
								});
						}
					}, btn, () => me.handle_save_fail(btn, on_error), resolve);
				});
			}, () => me.handle_save_fail(btn, on_error) );
		});
	}

	savecancel(btn, callback, on_error) {
		const me = this;
		this.validate_form_action('Cancel');

		frappe.call({
			method: "frappe.desk.form.linked_with.get_submitted_linked_docs",
			args: {
				doctype: me.doc.doctype,
				name: me.doc.name
			},
			freeze: true,
			callback: (r) => {
				if (!r.exc && r.message.count > 0) {
					me._cancel_all(r, btn, callback, on_error);
				} else {
					me._cancel(btn, callback, on_error, false);
				}
			}
		});
	}

	_cancel_all(r, btn, callback, on_error) {
		const me = this;

		// add confirmation message for cancelling all linked docs
		let links_text = "";
		let links = r.message.docs;
		const doctypes = Array.from(new Set(links.map(link => link.doctype)));

		for (let doctype of doctypes) {
			let docnames = links
				.filter((link) => link.doctype == doctype)
				.map((link) => frappe.utils.get_form_link(link.doctype, link.name, true))
				.join(", ");
			links_text += `<li><strong>${doctype}</strong>: ${docnames}</li>`;
		}
		links_text = `<ul>${links_text}</ul>`;

		let confirm_message = __('{0} {1} is linked with the following submitted documents: {2}',
			[(me.doc.doctype).bold(), me.doc.name, links_text]);

		let can_cancel = links.every((link) => frappe.model.can_cancel(link.doctype));
		if (can_cancel) {
			confirm_message += __('Do you want to cancel all linked documents?');
		} else {
			confirm_message += __('You do not have permissions to cancel all linked documents.');
		}

		// generate dialog box to cancel all linked docs
		let d = new frappe.ui.Dialog({
			title: __("Cancel All Documents"),
			fields: [{
				fieldtype: "HTML",
				options: `<p class="frappe-confirm-message">${confirm_message}</p>`
			}]
		}, () => me.handle_save_fail(btn, on_error));

		// if user can cancel all linked docs, add action to the dialog
		if (can_cancel) {
			d.set_primary_action("Cancel All", () => {
				d.hide();
				frappe.call({
					method: "frappe.desk.form.linked_with.cancel_all_linked_docs",
					args: {
						docs: links
					},
					freeze: true,
					callback: (resp) => {
						if (!resp.exc) {
							me.reload_doc();
							me._cancel(btn, callback, on_error, true);
						}
					}
				});
			});
		}

		d.show();
	};

	_cancel(btn, callback, on_error, skip_confirm) {
		const me = this;
		const cancel_doc = () => {
			frappe.validated = true;
			me.script_manager.trigger("before_cancel").then(() => {
				if (!frappe.validated) {
					return me.handle_save_fail(btn, on_error);
				}

				var after_cancel = function(r) {
					if (r.exc) {
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
		}

		if (skip_confirm) {
			cancel_doc();
		} else {
			frappe.confirm(__("Permanently Cancel {0}?", [this.docname]), cancel_doc, me.handle_save_fail(btn, on_error));
		}
	};

	savetrash() {
		this.validate_form_action("Delete");
		frappe.model.delete_doc(this.doctype, this.docname, function() {
			window.history.back();
		});
	}

	amend_doc() {
		if (!this.fields_dict['amended_from']) {
			frappe.msgprint(__('"amended_from" field must be present to do an amendment.'));
			return;
		}

		frappe.xcall('frappe.client.is_document_amended', {
			'doctype': this.doc.doctype,
			'docname': this.doc.name
		}).then(is_amended => {
			if (is_amended) {
				frappe.throw(__('This document is already amended, you cannot ammend it again'));
			}
			this.validate_form_action("Amend");
			var me = this;
			var fn = function(newdoc) {
				newdoc.amended_from = me.docname;
				if (me.fields_dict && me.fields_dict['amendment_date'])
					newdoc.amendment_date = frappe.datetime.obj_to_str(new Date());
			};
			this.copy_doc(fn, 1);
			frappe.utils.play_sound("click");
		});
	}

	validate_form_action(action, resolve) {
		var perm_to_check = this.action_perm_type_map[action];
		var allowed_for_workflow = false;
		var perms = frappe.perm.get_perm(this.doc.doctype)[0];

		// Allow submit, write, cancel and create permissions for read only documents that are assigned by
		// workflows if the user already have those permissions. This is to allow for users to
		// continue through the workflow states and to allow execution of functions like Duplicate.
		if ((frappe.workflow.is_read_only(this.doctype, this.docname) && (perms["write"] ||
			perms["create"] || perms["submit"] || perms["cancel"])) || !frappe.workflow.is_read_only(this.doctype, this.docname)) {
			allowed_for_workflow = true;
		}

		if (!this.perm[0][perm_to_check] && !allowed_for_workflow) {
			if(resolve) {
				// re-enable buttons
				resolve();
			}
			frappe.throw (__("No permission to '{0}' {1}", [__(action), __(this.doc.doctype)]));
		}
	}

	// HELPERS

	enable_save() {
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

	has_read_permission() {
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

	// ACTIONS

	print_doc() {
		this.print_preview.toggle();
	}

	navigate_records(prev) {
		let filters, sort_field, sort_order;
		let list_view = frappe.get_list_view(this.doctype);
		if (list_view) {
			filters = list_view.get_filters_for_args();
			sort_field = list_view.sort_field;
			sort_order = list_view.sort_order;
		} else {
			let list_settings = frappe.get_user_settings(this.doctype)['List'];
			if (list_settings) {
				filters = list_settings.filters;
				sort_field = list_settings.sort_field;
				sort_order = list_settings.sort_order;
			}
		}

		let args = {
			doctype: this.doctype,
			value: this.docname,
			filters,
			sort_order,
			sort_field,
			prev,
		};

		frappe.call('frappe.desk.form.utils.get_next', args).then(r => {
			if (r.message) {
				frappe.set_route('Form', this.doctype, r.message);
				this.focus_on_first_input();
			}
		});
	}

	focus_on_first_input() {
		let $first_input_el = $(frappe.container.page).find('.frappe-control:visible').eq(0);
		$first_input_el.find('input, select, textarea').focus();
	}

	rename_doc() {
		frappe.model.rename_doc(this.doctype, this.docname, () => this.refresh_header());
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

	// UTILITIES
	add_fetch(link_field, src_field, tar_field) {
		if(!this.fetch_dict[link_field]) {
			this.fetch_dict[link_field] = {'columns':[], 'fields':[]};
		}
		this.fetch_dict[link_field].columns.push(src_field);
		this.fetch_dict[link_field].fields.push(tar_field);
	}

	has_perm(ptype) {
		return frappe.perm.has_perm(this.doctype, 0, ptype, this.doc);
	}

	dirty() {
		this.doc.__unsaved = 1;
		this.$wrapper.trigger('dirty');
	}

	get_docinfo() {
		return frappe.model.docinfo[this.doctype][this.docname];
	}

	is_dirty() {
		return !!this.doc.__unsaved;
	}

	is_new() {
		return this.doc.__islocal;
	}

	get_perm(permlevel, access_type) {
		return this.perm[permlevel] ? this.perm[permlevel][access_type] : null;
	}

	set_intro(txt, color) {
		this.dashboard.set_headline_alert(txt, color);
	}

	set_footnote(txt) {
		this.footnote_area = frappe.utils.set_footnote(this.footnote_area, this.body, txt);
	}

	add_custom_button(label, fn, group) {
		// temp! old parameter used to be icon
		if(group && group.indexOf("fa fa-")!==-1) group = null;
		var btn = this.page.add_inner_button(label, fn, group);
		if(btn) {
			this.custom_buttons[label] = btn;
		}
		return btn;
	}

	clear_custom_buttons() {
		this.page.clear_inner_toolbar();
		this.page.clear_user_actions();
		this.custom_buttons = {};
	}

	//Remove specific custom button by button Label
	remove_custom_button(label, group) {
		this.page.remove_inner_button(label, group);
	}

	set_print_heading(txt) {
		this.pformat[this.docname] = txt;
	}

	scroll_to_element() {
		if (frappe.route_options && frappe.route_options.scroll_to) {
			var scroll_to = frappe.route_options.scroll_to;
			delete frappe.route_options.scroll_to;

			var selector = [];
			for (var key in scroll_to) {
				var value = scroll_to[key];
				selector.push(repl('[data-%(key)s="%(value)s"]', {key: key, value: value}));
			}

			selector = $(selector.join(" "));
			if (selector.length) {
				frappe.utils.scroll_to(selector);
			}
		}
	}

	show_success_action() {
		const route = frappe.get_route();
		if (route[0] !== 'Form') return;
		if (this.meta.is_submittable && this.doc.docstatus !== 1) return;

		const success_action = new frappe.ui.form.SuccessAction(this);
		success_action.show();
	}

	get_doc() {
		return locals[this.doctype][this.docname];
	}

	set_currency_labels(fields_list, currency, parentfield) {
		// To set the currency in the label
		// For example Total Cost(INR), Total Cost(USD)
		if (!currency) return;
		var me = this;
		var doctype = parentfield ? this.fields_dict[parentfield].grid.doctype : this.doc.doctype;
		var field_label_map = {};
		var grid_field_label_map = {};

		$.each(fields_list, function(i, fname) {
			var docfield = frappe.meta.docfield_map[doctype][fname];
			if(docfield) {
				var label = __(docfield.label || "").replace(/\([^\)]*\)/g, ""); // eslint-disable-line
				if(parentfield) {
					grid_field_label_map[doctype + "-" + fname] =
						label.trim() + " (" + __(currency) + ")";
				} else {
					field_label_map[fname] = label.trim() + " (" + currency + ")";
				}
			}
		});

		$.each(field_label_map, function(fname, label) {
			me.fields_dict[fname].set_label(label);
		});

		$.each(grid_field_label_map, function(fname, label) {
			fname = fname.split("-");
			var df = frappe.meta.get_docfield(fname[0], fname[1], me.doc.name);
			if(df) df.label = label;
		});
	}

	field_map(fnames, fn) {
		if(typeof fnames==='string') {
			if(fnames == '*') {
				fnames = Object.keys(this.fields_dict);
			} else {
				fnames = [fnames];
			}
		}
		for (var i=0, l=fnames.length; i<l; i++) {
			var fieldname = fnames[i];
			var field = frappe.meta.get_docfield(cur_frm.doctype, fieldname, this.docname);
			if(field) {
				fn(field);
				this.refresh_field(fieldname);
			}
		}
	}

	get_docfield(fieldname1, fieldname2) {
		if(fieldname2) {
			// for child
			var doctype = this.get_docfield(fieldname1).options;
			return frappe.meta.get_docfield(doctype, fieldname2, this.docname);
		} else {
			// for parent
			return frappe.meta.get_docfield(this.doctype, fieldname1, this.docname);
		}
	}

	set_df_property(fieldname, property, value, docname, table_field) {
		var df;
		if (!docname && !table_field){
			df = this.get_docfield(fieldname);
		} else {
			var grid = this.fields_dict[table_field].grid,
				fname = frappe.utils.filter_dict(grid.docfields, {'fieldname': fieldname});
			if (fname && fname.length)
				df = frappe.meta.get_docfield(fname[0].parent, fieldname, docname);
		}
		if(df && df[property] != value) {
			df[property] = value;
			refresh_field(fieldname, table_field);
		}
	}

	toggle_enable(fnames, enable) {
		this.field_map(fnames, function(field) {
			field.read_only = enable ? 0 : 1;
		});
	}

	toggle_reqd(fnames, mandatory) {
		this.field_map(fnames, function(field) {
			field.reqd = mandatory ? true : false;
		});
	}

	toggle_display(fnames, show) {
		this.field_map(fnames, function(field) {
			field.hidden = show ? 0 : 1;
		});
	}

	get_files() {
		return this.attachments
			? frappe.utils.sort(this.attachments.get_attachments(), "file_name", "string")
			: [] ;
	}

	set_query(fieldname, opt1, opt2) {
		if(opt2) {
			// on child table
			// set_query(fieldname, parent fieldname, query)
			this.fields_dict[opt1].grid.get_field(fieldname).get_query = opt2;
		} else {
			// on parent table
			// set_query(fieldname, query)
			if(this.fields_dict[fieldname]) {
				this.fields_dict[fieldname].get_query = opt1;
			}
		}
	}

	clear_table(fieldname) {
		frappe.model.clear_table(this.doc, fieldname);
	}

	add_child(fieldname, values) {
		var doc = frappe.model.add_child(this.doc, frappe.meta.get_docfield(this.doctype, fieldname).options, fieldname);
		if(values) {
			// Values of unique keys should not be overridden
			var d = {};
			var unique_keys = ["idx", "name"];

			Object.keys(values).map((key) => {
				if(!unique_keys.includes(key)) {
					d[key] = values[key];
				}
			});

			$.extend(doc, d);
		}
		return doc;
	}

	set_value(field, value, if_missing) {
		var me = this;
		var _set = function(f, v) {
			var fieldobj = me.fields_dict[f];
			if(fieldobj) {
				if(!if_missing || !frappe.model.has_value(me.doctype, me.doc.name, f)) {
					if(frappe.model.table_fields.includes(fieldobj.df.fieldtype) && $.isArray(v)) {

						frappe.model.clear_table(me.doc, fieldobj.df.fieldname);

						for (var i=0, j=v.length; i < j; i++) {
							var d = v[i];
							var child = frappe.model.add_child(me.doc, fieldobj.df.options,
								fieldobj.df.fieldname, i+1);
							$.extend(child, d);
						}

						me.refresh_field(f);
						return Promise.resolve();
					} else {
						return frappe.model.set_value(me.doctype, me.doc.name, f, v);
					}
				}
			} else {
				frappe.msgprint(__("Field {0} not found.",[f]));
				throw "frm.set_value";
			}
		};

		if(typeof field=="string") {
			return _set(field, value);
		} else if($.isPlainObject(field)) {
			let tasks = [];
			for (let f in field) {
				let v = field[f];
				if(me.get_field(f)) {
					tasks.push(() => _set(f, v));
				}
			}
			return frappe.run_serially(tasks);
		}
	}

	call(opts, args, callback) {
		var me = this;
		if(typeof opts==='string') {
			// called as frm.call('do_this', {with_arg: 'arg'});
			opts = {
				method: opts,
				doc: this.doc,
				args: args,
				callback: callback
			};
		}
		if(!opts.doc) {
			if(opts.method.indexOf(".")===-1)
				opts.method = frappe.model.get_server_module_name(me.doctype) + "." + opts.method;
			opts.original_callback = opts.callback;
			opts.callback = function(r) {
				if($.isPlainObject(r.message)) {
					if(opts.child) {
						// update child doc
						opts.child = locals[opts.child.doctype][opts.child.name];

						var std_field_list = ["doctype"].concat(frappe.model.std_fields_list);
						for (var key in r.message) {
							if (std_field_list.indexOf(key)===-1) {
								opts.child[key] = r.message[key];
							}
						}

						me.fields_dict[opts.child.parentfield].refresh();
					} else {
						// update parent doc
						me.set_value(r.message);
					}
				}
				opts.original_callback && opts.original_callback(r);
			};
		} else {
			opts.original_callback = opts.callback;
			opts.callback = function(r) {
				if(!r.exc) me.refresh_fields();

				opts.original_callback && opts.original_callback(r);
			};

		}
		return frappe.call(opts);
	}

	get_field(field) {
		return this.fields_dict[field];
	}

	set_read_only() {
		var perm = [];
		var docperms = frappe.perm.get_perm(this.doc.doctype);
		for (var i=0, l=docperms.length; i<l; i++) {
			var p = docperms[i];
			perm[p.permlevel || 0] = {read:1, print:1, cancel:1, email:1};
		}
		this.perm = perm;
	}

	trigger(event, doctype, docname) {
		return this.script_manager.trigger(event, doctype, docname);
	}

	get_formatted(fieldname) {
		return frappe.format(this.doc[fieldname],
			frappe.meta.get_docfield(this.doctype, fieldname, this.docname),
			{no_icon:true}, this.doc);
	}

	open_grid_row() {
		return frappe.ui.form.get_open_grid_form();
	}

	get_title() {
		if(this.meta.title_field) {
			return this.doc[this.meta.title_field];
		} else {
			return this.doc.name;
		}
	}

	get_selected() {
		// returns list of children that are selected. returns [parentfield, name] for each
		var selected = {}, me = this;
		frappe.meta.get_table_fields(this.doctype).forEach(function(df) {
			// handle TableMultiselect child fields
			let _selected = [];

			if(me.fields_dict[df.fieldname].grid) {
				_selected = me.fields_dict[df.fieldname].grid.get_selected();
			}

			if(_selected.length) {
				selected[df.fieldname] = _selected;
			}
		});
		return selected;
	}

	set_indicator_formatter(fieldname, get_color, get_text) {
		// get doctype from parent
		var doctype;
		if(frappe.meta.docfield_map[this.doctype][fieldname]) {
			doctype = this.doctype;
		} else {
			frappe.meta.get_table_fields(this.doctype).every(function(df) {
				if(frappe.meta.docfield_map[df.options][fieldname]) {
					doctype = df.options;
					return false;
				} else {
					return true;
				}
			});
		}

		frappe.meta.docfield_map[doctype][fieldname].formatter =
			function(value, df, options, doc) {
				if(value) {
					var label;
					if(get_text) {
						label = get_text(doc);
					} else if(frappe.form.link_formatters[df.options]) {
						label = frappe.form.link_formatters[df.options](value, doc);
					} else {
						label = value;
					}

					const escaped_name = encodeURIComponent(value);

					return repl('<a class="indicator %(color)s" href="#Form/%(doctype)s/%(name)s">%(label)s</a>', {
						color: get_color(doc || {}),
						doctype: df.options,
						name: escaped_name,
						label: label
					});
				} else {
					return '';
				}
			};
	}

	can_create(doctype) {
		// return true or false if the user can make a particlar doctype
		// will check permission, `can_make_methods` if exists, or will decided on
		// basis of whether the document is submittable
		if(!frappe.model.can_create(doctype)) {
			return false;
		}

		if(this.custom_make_buttons && this.custom_make_buttons[doctype]) {
			// custom buttons are translated and so are the keys
			const key = __(this.custom_make_buttons[doctype]);
			// if the button is present, then show make
			return !!this.custom_buttons[key];
		}

		if(this.can_make_methods && this.can_make_methods[doctype]) {
			return this.can_make_methods[doctype](this);
		} else {
			if(this.meta.is_submittable && !this.doc.docstatus==1) {
				return false;
			} else {
				return true;
			}
		}
	}

	make_new(doctype) {
		// make new doctype from the current form
		// will handover to `make_methods` if defined
		// or will create and match link fields
		var me = this;
		if(this.make_methods && this.make_methods[doctype]) {
			return this.make_methods[doctype](this);
		} else if(this.custom_make_buttons && this.custom_make_buttons[doctype]) {
			this.custom_buttons[__(this.custom_make_buttons[doctype])].trigger('click');
		} else {
			frappe.model.with_doctype(doctype, function() {
				var new_doc = frappe.model.get_new_doc(doctype);

				// set link fields (if found)
				frappe.get_meta(doctype).fields.forEach(function(df) {
					if(df.fieldtype==='Link' && df.options===me.doctype) {
						new_doc[df.fieldname] = me.doc.name;
					} else if (['Link', 'Dynamic Link'].includes(df.fieldtype) && me.doc[df.fieldname]) {
						new_doc[df.fieldname] = me.doc[df.fieldname];
					}
				});

				frappe.ui.form.make_quick_entry(doctype, null, null, new_doc);
				// frappe.set_route('Form', doctype, new_doc.name);
			});
		}
	}

	update_in_all_rows(table_fieldname, fieldname, value) {
		// update the child value in all tables where it is missing
		if(!value) return;
		var cl = this.doc[table_fieldname] || [];
		for(var i = 0; i < cl.length; i++){
			if(!cl[i][fieldname]) cl[i][fieldname] = value;
		}
		refresh_field("items");
	}

	get_sum(table_fieldname, fieldname) {
		let sum = 0;
		for (let d of (this.doc[table_fieldname] || [])) {
			sum += d[fieldname];
		}
		return sum;
	}

	scroll_to_field(fieldname) {
		let field = this.get_field(fieldname);
		if (!field) return;

		let $el = field.$wrapper;

		// uncollapse section
		if (field.section.is_collapsed()) {
			field.section.collapse(false);
		}

		// scroll to input
		frappe.utils.scroll_to($el, true, 15);

		// highlight input
		$el.addClass('has-error');
		setTimeout(() => {
			$el.removeClass('has-error');
			$el.find('input, select, textarea').focus();
		}, 1000);
	}

	show_tour(on_finish) {
		if (!Array.isArray(frappe.tour[this.doctype])) {
			return;
		}

		const driver = new frappe.Driver({
			overlayClickNext: true,
			keyboardControl: true,
			nextBtnText: 'Next',
			prevBtnText: 'Previous',
			opacity: 0.25,
			onNext: () => {
				if (!driver.hasNextStep()) {
					on_finish && on_finish();
				}
			}
		});

		this.layout.sections.forEach(section => section.collapse(false));

		let steps = frappe.tour[this.doctype].map(step => {
			let field = this.get_docfield(step.fieldname);
			return {
				element: `.frappe-control[data-fieldname='${step.fieldname}']`,
				popover: {
					title: step.title || field.label,
					description: step.description
				}
			};
		});

		driver.defineSteps(steps);
		driver.start();
	}
};

frappe.validated = 0;
// Proxy for frappe.validated
Object.defineProperty(window, 'validated', {
	get: function() {
		console.warn('Please use `frappe.validated` instead of `validated`. It will be deprecated soon.'); // eslint-disable-line
		return frappe.validated;
	},
	set: function(value) {
		console.warn('Please use `frappe.validated` instead of `validated`. It will be deprecated soon.'); // eslint-disable-line
		frappe.validated = value;
		return frappe.validated;
	}
});
