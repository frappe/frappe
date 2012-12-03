// for license information please see license.txt

wn.provide("wn.ui.form")

wn.ui.form.LinkedWith = Class.extend({
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
	},
	show: function() {
		if(!this.dialog)
			this.make_dialog();
		
		this.dialog.show();
		this.dialog.get_input("list_by").change();
	},
	make_dialog: function() {
		var me = this;
		this.linked_with = this.frm.meta.__linked_with;
		var links = $.map(keys(this.linked_with), function(v) {
			return in_list(wn.boot.profile.can_get_report, v) ? {value:v, label:wn._(v)} : null
		}).sort(function(a, b) { return a.label > b.label ? 1 : -1 });
		
		this.dialog = new wn.ui.Dialog({
			width: 640,
			title: wn._("Linked With"),
			fields: [
				{ fieldtype: "HTML", label: "help", 
					options:"<div class='help'>" + wn._("List of records in which this document is linked") 
						+"</div>" },
				{ fieldtype: "Select", options: links, 
					label: wn._("Type"), fieldname: "list_by" },
				{ fieldtype: "HTML", label: "hr", options:"<hr>" },
				{ fieldtype: "HTML", label: "list" }
			]
		});
		
		this.dialog.get_input("list_by").val(links[0].value);
		
		if(!links) {
			this.dialog.fields_dict.list.$wrapper.html("<div class='alert'>"
			+ this.frm.doctype + ": "
			+ (this.linked_with ? wn._("Not Linked to any record.") : wn._("Not enough permission to see links."))
			+ "</div>")
			this.dialog.fields_dict.list_by.$wrapper.toggle(false);
			this.dialog.fields_dict.help.$wrapper.toggle(false);
			return;
		}
		
		this.dialog.get_input("list_by").change(function() {
			me.doctype = me.dialog.get_input("list_by").val();
			me.is_table = (!in_list(wn.boot.profile.can_read, me.doctype) &&
				in_list(wn.boot.profile.can_get_report, me.doctype))
			
			wn.model.with_doctype(me.doctype, function(r) {
				me.make_listing();
				me.lst.run();
			})
		})
	},
	make_listing: function() {
		var me = this;
		this.lst = new wn.ui.Listing({
			hide_refresh: true,
			no_loading: true,
			no_toolbar: true,
			doctype: me.doctype,
			show_filters: true,
			parent: $(this.dialog.fields_dict.list.wrapper).empty().css("min-height", "300px")
				.get(0),
			method: 'webnotes.widgets.reportview.get',
			get_args: function() {
				return {
					doctype: me.doctype,
					fields: [ '`tab' + me.doctype + '`.name', 
						'`tab' + me.doctype + '`.modified',
						'`tab' + me.doctype + '`.modified_by',
						'`tab' + me.doctype + '`.docstatus'],
					filters: me.lst.filter_list.get_filters(),
					docstatus: ['0','1']
				}
			},
			render_row: function(parent, data) {
				$(parent).html(repl('%(avatar)s \
					<a href="#Form/%(doctype)s/%(name)s" onclick="cur_dialog.hide()">\
						%(doctype)s: %(name)s</a>\
					<span class="help">Last Updated: %(modified)s</span>', {
						avatar: wn.avatar(data.modified_by, null, 
							"Last Modified By: " + wn.user_info(data.modified_by).fullname),
						doctype: me.is_table ? data.parenttype : me.doctype,
						modified: dateutil.comment_when(data.modified),
						name: me.is_table ? data.parent : data.name
					})).find('.avatar img').centerImage();
			},
			get_no_result_message: function() {
				return repl("<div class='alert'>%(doctype)s: " + wn._("Not linked") + "</div>", {
					name: me.frm.doc.name,
					doctype: wn._(me.doctype)
				})
			}
		});
		me.lst.filter_list.show_filters(true);
		me.lst.filter_list.clear_filters();
		me.lst.set_filter(me.linked_with[me.doctype], me.frm.doc.name);
	}
});