// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

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
				obj: me,
				method: 'frappe.desk.form.assign_to.add',
				doctype: me.frm.doctype,
				docname: me.frm.docname,
				callback: function(r) {
					me.render(r.message);
				}
			});
		}
		me.assign_to.dialog.clear();

		if(me.frm.meta.title_field) {
			me.assign_to.dialog.set_value("description", me.frm.doc[me.frm.meta.title_field])
		}

		me.assign_to.dialog.show();
		me.assign_to = null;
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
		var me = this
		var dialog = new frappe.ui.Dialog({
			title: __('Add to To Do'),
			fields: [
				{fieldtype: 'Link', fieldname:'assign_to', options:'User',
					label:__("Assign To"), reqd:true, filters: {'user_type': 'System User'}},
				{fieldtype:'Check', fieldname:'myself', label:__("Assign to me"), "default":0},
				{fieldtype:'Small Text', fieldname:'description', label:__("Comment")},
				{fieldtype: 'Section Break'},
				{fieldtype: 'Column Break'},
				{fieldtype:'Date', fieldname:'date', label: __("Complete By")},
				{fieldtype:'Check', fieldname:'notify',
					label:__("Notify by Email")},
				{fieldtype: 'Column Break'},
				{fieldtype:'Select', fieldname:'priority', label: __("Priority"),
					options:[
						{value:'Low', label:__('Low')},
						{value:'Medium', label:__('Medium')},
						{value:'High', label:__('High')}],
					'default':'Medium'},
			],
			primary_action: function() { frappe.ui.add_assignment(opts, this) },
			primary_action_label: __("Add")
		})
		$.extend(me, dialog);

		me.dialog = dialog;

		me.dialog.fields_dict.assign_to.get_query = "frappe.core.doctype.user.user.user_query";

		var myself = me.dialog.get_input("myself").on("click", function() {
			me.toggle_myself(this);
		});
		me.toggle_myself(myself);
	},
	toggle_myself: function(myself) {
		var me = this;
		if($(myself).prop("checked")) {
			me.dialog.set_value("assign_to", frappe.session.user);
			me.dialog.set_value("notify", 0);
			me.dialog.get_field("notify").$wrapper.toggle(false);
			me.dialog.get_field("assign_to").$wrapper.toggle(false);
		} else {
			me.dialog.set_value("assign_to", "");
			me.dialog.get_field("notify").$wrapper.toggle(true);
			me.dialog.get_field("assign_to").$wrapper.toggle(true);
		}
	},

});

frappe.ui.add_assignment = function(opts, dialog) {
	var assign_to = dialog.fields_dict.assign_to.get_value();
	var args = dialog.get_values();
	if(args && assign_to) {
		return frappe.call({
			method: opts.method,
			args: $.extend(args, {
				doctype: opts.doctype,
				name: opts.docname,
				assign_to: assign_to,
				bulk_assign:  opts.bulk_assign || false,
				re_assign: opts.re_assign || false
			}),
			callback: function(r,rt) {
				if(!r.exc) {
					if(opts.callback){
						opts.callback(r);
					}
					dialog && dialog.hide();
				}
			},
			btn: this
		});
	}
}
