// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

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
	},
	make_dialog: function() {
		var me = this;
		this.linked_with = this.frm.meta.__linked_with;

		var links = [];
		$.each(this.linked_with, function(doctype, tmp) {
			if(wn.model.can_get_report(doctype)) {
				links.push({label: wn._(doctype), value: doctype});
			}
		});
		
		links = wn.utils.sort(links, "label");
				
		this.dialog = new wn.ui.Dialog({
			width: 700,
			hide_on_page_refresh: true,
			title: wn._("Linked With"),
			fields: [
				{ fieldtype: "HTML", label: "list" }
			]
		});
				
		if(!links) {
			this.dialog.fields_dict.list.$wrapper.html("<div class='alert alert-warning'>"
			+ this.frm.doctype + ": "
			+ (this.linked_with ? wn._("Not Linked to any record.") : wn._("Not enough permission to see links."))
			+ "</div>")
			return;
		}
		
		this.dialog.onshow = function() {
			me.dialog.fields_dict.list.$wrapper.html('<div class="progress">\
					<div class="progress-bar progress-bar-striped" style="width: 100%;">\
					</div></div>');
			
			wn.call({
				method:"webnotes.widgets.form.utils.get_linked_docs",
				args: {
					doctype: me.frm.doctype,
					name: me.frm.docname
				},
				callback: function(r) {
					if(r.message) {
						var html = "";
						$.each(keys(r.message).sort(), function(i, key) {
							html += "<h4>" + wn._(key) + "</h4><ul class='linked-with-list'>"
							$.each(r.message[key], function(i, d) {
								html += "<li><a href='#Form/"+key+"/"+d.name+"'>" + d.name + "</a>"+
									'<span class="text-muted small"> ' + 
									$.map(d, function(v, k) { 
										return ["name", "modified"].indexOf(k)!==-1 ? null : v }).join(", ")
									+ '</span>'
									+ '<span class="pull-right text-muted small">' + comment_when(d.modified) + '<span>'
									+"</li>";
							})
							html+="</ul>"
						})
					} else {
						html = wn._("Not Linked to any record.");
					}
					me.dialog.fields_dict.list.$wrapper.html(html);
				}
			})
		}
		
	},
});