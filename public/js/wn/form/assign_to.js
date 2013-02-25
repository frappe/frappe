// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

// assign to is lined to todo
// refresh - load todos
// create - new todo
// delete to do

wn.provide("wn.ui.form");

wn.ui.form.AssignTo = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		var me = this;
		this.wrapper = $('<div>\
			<button class="btn btn-small"><i class="icon-plus"></i></button>\
			<div class="alert-list"></div>\
		</div>').appendTo(this.parent);

		this.$list = this.wrapper.find(".alert-list");
		
		this.wrapper.find(".btn").click(function() {
			me.add();
		});
	},
	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.parent.toggle(false);
			return;
		}
		this.parent.toggle(true);

		var me = this;
		wn.call({
			method: 'webnotes.widgets.form.assign_to.get',
			type: "GET",
			args: {
				doctype: me.frm.doctype,
				name: me.frm.docname
			},
			callback: function(r) {
				me.render(r.message)
			}
		})
	},
	render: function(d) {
		var me = this;
		this.$list.empty();
		if(this.dialog) {
			this.dialog.hide();			
		}
				
		for(var i=0; i<d.length; i++) {	
			$.extend(d[i], wn.user_info(d[i].owner));
			d[i].avatar = wn.avatar(d[i].owner);
			
			$(repl('<div class="alert alert-success" style="height: 19px; margin-top: 3px">\
				%(avatar)s %(fullname)s \
				<a class="close" href="#" style="top: 1px;"\
					data-owner="%(owner)s">&times;</a></div>', d[i]))
				.appendTo(this.$list);
				
			this.$list.find(".avatar").css("margin-top", "-7px")
			this.$list.find('.avatar img').centerImage();
		}

		// set remove
		this.$list.find('a.close').click(function() {
			wn.call({
				method:'webnotes.widgets.form.assign_to.remove', 
				args: {
					doctype: me.frm.doctype,
					name: me.frm.docname,
					assign_to: $(this).attr('data-owner')	
				}, 
				callback:function(r,rt) {me.render(r.message);}
			});
			return false;
		});
	},
	add: function() {
		var me = this;
		if(!me.dialog) {
			me.dialog = new wn.ui.Dialog({
				title: wn._('Add to To Do'),
				width: 350,
				fields: [
					{fieldtype:'Link', fieldname:'assign_to', options:'Profile', 
						label:wn._("Assign To"), 
						description:wn._("Add to To Do List of"), reqd:true},
					{fieldtype:'Data', fieldname:'description', label:wn._("Comment")}, 
					{fieldtype:'Date', fieldname:'date', label: wn._("Complete By")}, 
					{fieldtype:'Select', fieldname:'priority', label: wn._("Priority"),
						options:'Low\nMedium\nHigh', 'default':'Medium'},
					{fieldtype:'Check', fieldname:'notify', label: wn._("Notify By Email")},
					{fieldtype:'Button', label:wn._("Add"), fieldname:'add_btn'}
				]
			});
			me.dialog.fields_dict.add_btn.input.onclick = function() {
				
				var assign_to = me.dialog.fields_dict.assign_to.get_value();
				if(assign_to) {
					wn.call({
						method:'webnotes.widgets.form.assign_to.add', 
						args: {
							doctype: me.frm.doctype,
							name: me.frm.docname,
							assign_to: assign_to,
							description: me.dialog.fields_dict.description.get_value(),
							priority: me.dialog.fields_dict.priority.get_value(),
							date: me.dialog.fields_dict.date.get_value(),
							notify: me.dialog.fields_dict.notify.get_value()
						}, 
						callback: function(r,rt) {
							if(!r.exc) {
								if(cint(me.dialog.fields_dict.notify.get_value()))
									msgprint("Email sent to " + assign_to);
								me.render(r.message);
							}
						}
					});
				}
			}
			me.dialog.fields_dict.assign_to.get_query = function() {
				return "select name, concat_ws(' ', first_name, middle_name, last_name) \
					from `tabProfile` where ifnull(enabled, 0)=1 and docstatus < 2 and \
					name not in ('Administrator', 'Guest') and (%(key)s like \"%s\" or \
					concat_ws(' ', first_name, middle_name, last_name) like \"%%%s\") \
					order by \
					case when name like \"%s%%\" then 0 else 1 end, \
					case when concat_ws(' ', first_name, middle_name, last_name) \
						like \"%s%%\" then 0 else 1 end, \
					name asc limit 50";
			};
		}
		me.dialog.clear();
		me.dialog.show();
	}
});

