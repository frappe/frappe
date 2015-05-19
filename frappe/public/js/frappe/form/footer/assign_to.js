// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// assign to is lined to todo
// refresh - load todos
// create - new todo
// delete to do

frappe.provide("frappe.ui.form");

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
				info.owner = d[i].owner;
				info.image = frappe.user_info(d[i].owner).image;
				info.description = d[i].description || "";

				$(repl('<li class="assignment-row">\
					<a class="close" data-owner="%(owner)s">&times;</a>\
					<div class="text-ellipsis" style="width: 80%">\
						<div class="avatar avatar-small">\
							<img class="media-object" src="%(image)s" alt="%(fullname)s">\
						</div>\
						<span>%(fullname)s</span>\
					</div>\
				</li>', info))
					.appendTo(this.parent);

				if(d[i].owner===user) {
					me.primary_action = this.frm.page.add_menu_item(__("Assignment Complete"), function() {
						me.remove(user);
					}, "icon-ok", "btn-success")
				}

				if(!(d[i].owner === user || me.frm.perm[0].write)) {
					me.parent.find('a.close').remove();
				}
			}

			// set remove
			this.parent.find('a.close').click(function() {
				me.remove($(this).attr('data-owner'));
				return false;
			});

			this.btn_wrapper.addClass("hide");
		} else {
			this.btn_wrapper.removeClass("hide");
		}
	},
	add: function() {
		var me = this;

		if(this.frm.doc.__unsaved == 1) {
			frappe.throw(__("Please save the document before assignment"));
			return;
		}

		if(!me.dialog) {
			me.dialog = new frappe.ui.Dialog({
				title: __('Add to To Do'),
				fields: [
					{fieldtype:'Link', fieldname:'assign_to', options:'User',
						label:__("Assign To"),
						description:__("Add to To Do List Of"), reqd:true},
					{fieldtype:'Data', fieldname:'description', label:__("Comment"), reqd:true},
					{fieldtype:'Check', fieldname:'notify',
						label:__("Notify by Email"), "default":1},
					{fieldtype:'Date', fieldname:'date', label: __("Complete By")},
					{fieldtype:'Select', fieldname:'priority', label: __("Priority"),
						options:'Low\nMedium\nHigh', 'default':'Medium'},
				],
				primary_action: function() { me.add_assignment(); },
				primary_action_label: __("Add")
			});

			me.dialog.fields_dict.assign_to.get_query = "frappe.core.doctype.user.user.user_query";
		}
		me.dialog.clear();

		if(me.frm.meta.title_field) {
			me.dialog.set_value("description", me.frm.doc[me.frm.meta.title_field])
		}

		me.dialog.show();
	},
	add_assignment: function() {
		var me = this;
		var assign_to = me.dialog.fields_dict.assign_to.get_value();
		var args = me.dialog.get_values();
		if(args && assign_to) {
			return frappe.call({
				method:'frappe.desk.form.assign_to.add',
				args: $.extend(args, {
					doctype: me.frm.doctype,
					name: me.frm.docname,
					assign_to: assign_to
				}),
				callback: function(r,rt) {
					if(!r.exc) {
						me.render(r.message);
						me.frm.reload_doc();
					}
				},
				btn: this
			});
		}
	},
	remove: function(owner) {
		var me = this;

		if(this.frm.doc.__unsaved == 1) {
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
				me.frm.reload_doc();
			}
		});
	}
});

