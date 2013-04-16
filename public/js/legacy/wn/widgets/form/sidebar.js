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
				title: wn._('Assign'),
				render: function(wrapper) {
					me.form.assign_to = new wn.ui.form.AssignTo({
						parent: $(wrapper),
						frm: me.form
					});
					me.form.assign_to.refresh();
				},
				display: function() { return !me.form.doc.__islocal }
			},
			
			{
				title: wn._('Attachments'),
				render: function(wrapper) {
					me.form.attachments = new wn.ui.form.Attachments({
						parent: $(wrapper), 
						frm:me.form
					});
					me.form.attachments.refresh();
				},
				display: function() { return me.form.meta.allow_attach }
			},

			{
				title: wn._('Comments'),
				render: function(wrapper) {
					new wn.widgets.form.sidebar.Comments(wrapper, me, me.form.doctype, me.form.docname);
				},
				display: function() { 
					$(cur_frm.body).find(".latest-comment").toggle(false);
					return !me.form.doc.__islocal;
				}
			},

			{
				title: wn._('Tags'),
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
		var parent = this.form.sidebar_area;
		if(!this.sidebar) {
			//$y(parent, {paddingTop:'37px'})
			this.sidebar = new wn.widgets.PageSidebar(parent, this.opts);
		} else {
			this.sidebar.refresh();
		}
	}
	

}}
