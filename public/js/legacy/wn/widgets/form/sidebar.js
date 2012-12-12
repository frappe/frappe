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

wn.widgets.form.sidebar = { Sidebar: function(form) {
	var me = this;
	this.form = form;
	this.opts = {
		sections: [
			{
				title: 'Actions',
				items: [
					{
						type: 'link',
						label: 'New',
						icon: 'icon-plus',
						display: function() { 
							return in_list(profile.can_create, form.doctype) 
						},
						onclick: function() { new_doc(me.form.doctype) }
					},
					
					{
						type: 'link',
						label: 'Print',
						display: function() { 
							return !(me.form.doc.__islocal || me.form.meta.allow_print);
						},
						icon: 'icon-print',
						onclick: function() { me.form.print_doc() }
					},

					{
						type: 'link',
						label: 'Email',
						display: function() { 
							return !(me.form.doc.__islocal || me.form.meta.allow_email);
						},
						icon: 'icon-envelope',
						onclick: function() { me.form.email_doc() }
					},

					{
						type: 'link',
						label: 'Copy',
						display: function() { 
							return in_list(profile.can_create, me.form.doctype) && !me.form.meta.allow_copy 
						},
						icon: 'icon-file',
						onclick: function() { me.form.copy_doc() }
					},
					
					{
						type: 'link',
						label: 'Delete',
						display: function() { 
							return (cint(me.form.doc.docstatus) != 1) && !me.form.doc.__islocal
								&& wn.model.can_delete(me.form.doctype);
						},
						icon: 'icon-remove-sign',
						onclick: function() { me.form.savetrash() }
					},

					{
						type: 'link',
						label: 'Rename',
						display: function() { 
							return me.form.meta.allow_rename && me.form.perm[0][WRITE];
						},
						icon: 'icon-retweet',
						onclick: function() { me.form.rename_doc() }
					},
					
					{
						type: 'link',
						label: 'Linked With',
						display: function() { 
							return !me.form.doc.__islocal && !me.form.meta.issingle;
						},
						icon: 'icon-random',
						onclick: function() { 
							if(!me.form.linked_with) {
								me.form.linked_with = new wn.ui.form.LinkedWith({
									frm: me.form
								});
							}
							me.form.linked_with.show();
						}
					}
					
				],
				display: function() {
					return me.form.meta.hide_toolbar ? false : true;
				}
			},

			{
				title: 'Assign To',
				render: function(wrapper) {
					me.form.assign_to = new wn.widgets.form.sidebar.AssignTo(wrapper, me, me.form.doctype, me.form.docname);
				},
				display: function() { return !me.form.doc.__islocal }
			},
			
			{
				title: 'Attachments',
				render: function(wrapper) {
					me.form.attachments = new wn.ui.form.Attachments({parent: $(wrapper), frm:me.form});
					me.form.attachments.refresh();
				},
				display: function() { return me.form.meta.allow_attach }
			},

			{
				title: 'Comments',
				render: function(wrapper) {
					new wn.widgets.form.sidebar.Comments(wrapper, me, me.form.doctype, me.form.docname);
				},
				display: function() { 
					$(cur_frm.page_layout.body).find(".latest-comment").toggle(false);
					return !me.form.doc.__islocal;
				}
			},

			{
				title: 'Tags',
				render: function(wrapper) {
					me.form.taglist = new TagList(wrapper, 
						me.form.doc._user_tags ? me.form.doc._user_tags.split(',') : [], 
						me.form.doctype, me.form.docname, 0, 
						function() {	});
				},
				display: function() { return !me.form.doc.__islocal }
			},
		]
	}
	
	this.refresh = function() {
		var parent = this.form.page_layout.sidebar_area;
		if(!this.sidebar) {
			//$y(parent, {paddingTop:'37px'})
			this.sidebar = new wn.widgets.PageSidebar(parent, this.opts);
		} else {
			this.sidebar.refresh();
		}
	}
	

}}
