// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt



frappe.ui.form.AssignTo = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.btn = this.parent.find(".add-assignment-btn > button").on("click", () => this.add());
		this.btn_wrapper = this.btn.parent();

		this.refresh();
	},
	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.parent.toggle(false);
			return;
		}
		this.parent.toggle(true);
		this.render(this.frm.get_docinfo().assignments);
	},
	render: function(assignments) {
		this.frm.get_docinfo().assignments = assignments;
		this.parent.find(".assignment-row").remove();

		if (this.primary_action) {
			this.primary_action.remove();
			this.primary_action = null;
		}

		if (this.dialog) {
			this.dialog.hide();
		}

		let add_assignment_button = this.parent.find('.add-assignment-btn');
		assignments.forEach(assignment => {
			let user_info = frappe.user_info(assignment.owner);
			user_info.assign_to_name = assignment.name;
			user_info.owner = assignment.owner;
			user_info.avatar = frappe.avatar(assignment.owner);
			user_info.description = assignment.description || "";

			this.get_assignment_block(user_info).insertBefore(add_assignment_button);
			if (assignment.owner === frappe.session.user) {
				this.primary_action = this.frm.page.add_menu_item(__("Assignment Complete"), () => {
					this.remove(frappe.session.user);
				}, "fa fa-check", "btn-success");
			}
		});

	},
	get_assignment_block(info) {
		let remove_action = false;
		if (info.owner === frappe.session.user || this.frm.perm[0].write) {
			remove_action = this.remove.bind(this);
		}
		return $(`<li class="assignment-row">`)
			.append(frappe.get_data_pill(
				frappe.user.full_name(info.owner),
				info.owner,
				remove_action,
				frappe.avatar(info.owner, "avatar-xs")
			));
	},
	add: function() {
		var me = this;

		if(this.frm.is_new()) {
			frappe.throw(__("Please save the document before assignment"));
			return;
		}

		if(!me.assign_to) {
			me.assign_to = new frappe.ui.form.AssignToDialog({
				method: "frappe.desk.form.assign_to.add",
				doctype: me.frm.doctype,
				docname: me.frm.docname,
				frm: me.frm,
				callback: function (r) {
					me.render(r.message);
				}
			});
		}
		me.assign_to.dialog.clear();
		me.assign_to.dialog.show();
	},
	remove: function(owner) {
		var me = this;

		if(this.frm.is_new()) {
			frappe.throw(__("Please save the document before removing assignment"));
			return;
		}

		frappe.call({
			method:'frappe.desk.form.assign_to.remove',
			args: {
				doctype: me.frm.doctype,
				name: me.frm.docname,
				assign_to: owner
			},
			callback:function(r,rt) {
				me.render(r.message);
			}
		});
	}
});


frappe.ui.form.AssignToDialog = Class.extend({
	init: function(opts){
		$.extend(this, opts);

		this.make();
		this.set_description_from_doc();
	},
	make: function() {
		let me = this;

		me.dialog = new frappe.ui.Dialog({
			title: __('Add to ToDo'),
			fields: me.get_fields(),
			primary_action_label: __("Add"),
			primary_action: function() {
				let args = me.dialog.get_values();

				if (args && args.assign_to) {
					me.dialog.set_message("Assigning...");

					frappe.call({
						method: me.method,
						args: $.extend(args, {
							doctype: me.doctype,
							name: me.docname,
							assign_to: args.assign_to,
							bulk_assign: me.bulk_assign || false,
							re_assign: me.re_assign || false
						}),
						btn: me.dialog.get_primary_btn(),
						callback: function(r) {
							if (!r.exc) {
								if (me.callback) {
									me.callback(r);
								}
								me.dialog && me.dialog.hide();
							} else {
								me.dialog.clear_message();
							}
						},
					});
				}
			},
		});
	},
	assign_to_me: function() {
		let me = this;
		let assign_to = [];

		if (me.dialog.get_value("assign_to_me")) {
			assign_to.push(frappe.session.user);
		}

		me.dialog.set_value("assign_to", assign_to);
	},
	set_description_from_doc: function() {
		let me = this;

		if (me.frm && me.frm.meta.title_field) {
			me.dialog.set_value("description", me.frm.doc[me.frm.meta.title_field]);
		}
	},
	get_fields: function() {
		let me = this;

		return [
			{
				fieldtype: 'MultiSelectPills',
				fieldname: 'assign_to',
				label: __("Assign To"),
				reqd: true,
				get_data: function(txt) {
					return frappe.db.get_link_options("User", txt, {user_type: "System User", enabled: 1});
				}
			},
			{
				label: __("Assign to me"),
				fieldtype: 'Check',
				fieldname: 'assign_to_me',
				default: 0,
				onchange: () => me.assign_to_me()
			},
			{
				label: __("Comment"),
				fieldtype: 'Small Text',
				fieldname: 'description'
			},
			{
				fieldtype: 'Section Break'
			},
			{
				fieldtype: 'Column Break'
			},
			{
				label: __("Complete By"),
				fieldtype: 'Date',
				fieldname: 'date'
			},
			{
				fieldtype: 'Column Break'
			},
			{
				label: __("Priority"),
				fieldtype: 'Select',
				fieldname: 'priority',
				options: [
					{
						value: 'Low',
						label: __('Low')
					},
					{
						value: 'Medium',
						label: __('Medium')
					},
					{
						value: 'High',
						label: __('High')
					}
				],
				// Pick up priority from the source document, if it exists and is available in ToDo
				default: ["Low", "Medium", "High"].includes(me.frm && me.frm.doc.priority ? me.frm.doc.priority : 'Medium')
			}
		];
	}
});


frappe.ui.form.AssignmentDialog = class {
	constructor(opts) {
		// this.frm = opts.frm;
		this.assignments = opts.assignments;
		this.make();
	}

	make() {
		this.dialog = new frappe.ui.Dialog({
			title: __('Assign Users'),
			fields: [{
				'fieldtype': 'Link',
				'fieldname': 'selected_user',
				'options': 'User',
				'label': 'User',
				'change': () => {
					let user = this.dialog.get_value('selected_user');
					if (user && user !== '') {
						this.update_assignment(user);
						this.dialog.set_value('selected_user', null);
					}
				}
			}, {
				'fieldtype': 'HTML',
				'fieldname': 'assignment_list'
			}]
		});

		this.assignment_list = $(this.dialog.get_field('assignment_list').wrapper);

		this.assignments.forEach(assignment => {
			this.update_assignment(assignment);
		});
		this.dialog.show();
	}
	update_assignment(assignment) {
		this.assignment_list.append(this.get_assignment_row(assignment));
	}
	get_assignment_row(assignment) {
		let row = $(`
			<div class="dialog-assignment-row" data-user="${assignment}">
				<span>
					${frappe.avatar(assignment)}
					${frappe.user.full_name(assignment)}
				</span>
				<span class="remove-btn">
					${frappe.utils.icon('close')}
				</span>
			</div>
		`);
		row.find('.remove-btn').click(() => {
			row.remove();
		});
		return row;
	}
};