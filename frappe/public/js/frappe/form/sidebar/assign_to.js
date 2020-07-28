// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt



frappe.ui.form.AssignTo = Class.extend({
	init: function(opts) {
		var me = this;

		$.extend(this, opts);
		this.btn = this.parent.find(".add-assignment").on("click", function() { me.add(); });
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
	render: function(d) {
		var me = this;
		this.frm.get_docinfo().assignments = d;
		this.parent.find(".assignment-row").remove();

		if(me.primary_action) {
			me.primary_action.remove();
			me.primary_action = null;
		}

		if(this.dialog) {
			this.dialog.hide();
		}

		if(d && d.length) {
			for(var i=0; i<d.length; i++) {
				var info = frappe.user_info(d[i].owner);
				info.assign_to_name = d[i].name
				info.owner = d[i].owner;
				info.avatar = frappe.avatar(d[i].owner);
				info.description = d[i].description || "";

				info._fullname = info.fullname;
				if(info.fullname.length > 10) {
					info._fullname = info.fullname.substr(0, 10) + '...';
				}

				$(repl('<li class="assignment-row">\
					<a class="close" data-owner="%(owner)s">&times;</a>\
					%(avatar)s\
					<span><a href="#Form/ToDo/%(assign_to_name)s">%(_fullname)s</a></span>\
				</li>', info))
					.insertBefore(this.parent.find('.add-assignment'));

				if(d[i].owner===frappe.session.user) {
					me.primary_action = this.frm.page.add_menu_item(__("Assignment Complete"), function() {
						me.remove(frappe.session.user);
					}, "fa fa-check", "btn-success")
				}

				if(!(d[i].owner === frappe.session.user || me.frm.perm[0].write)) {
					me.parent.find('a.close').remove();
				}
			}

			// set remove
			this.parent.find('a.close').click(function() {
				me.remove($(this).attr('data-owner'));
				return false;
			});

			//this.btn_wrapper.addClass("hide");
		} else {
			//this.btn_wrapper.removeClass("hide");
		}
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
					return frappe.db.get_link_options("User", txt, {user_type: "System User", enabled: 1, disable_assignments: 0});
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
