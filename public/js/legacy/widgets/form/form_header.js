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

// features
// --------
// toolbar - standard and custom
// label - saved, submitted etc
// save / submit button toggle based on "saved" or not
// highlight and fade name based on refresh

_f.FrmHeader = Class.extend({
	init: function(parent, frm) {
		this.appframe = frm.appframe;
		this.$w = this.appframe.$w;
		this.frm = frm;
		
		this.appframe.add_home_breadcrumb();
		this.appframe.add_module_icon(frm.meta.module)
		this.appframe.set_views_for(frm.meta.name, "form");
		
		if(!frm.meta.issingle) {
			if(frm.cscript.add_list_breadcrumb) {
				frm.cscript.add_list_breadcrumb(this.appframe);
			} else {
				this.appframe.add_list_breadcrumb(frm.meta.name);
			}
		}
		this.appframe.add_breadcrumb("icon-file");
	},
	refresh: function() {
		var me = this;
		var title = this.frm.docname;
		if(title.length > 30) {
			title = title.substr(0,30) + "...";
		}
		this.appframe.set_title(title, wn._(this.frm.docname));
		this.appframe.set_sub_title(this.frm.doc.__islocal ? "Not Saved" 
			: "Last Updated on " + dateutil.str_to_user(this.frm.doc.modified) + " by " + this.frm.doc.modified_by)
		//this.refresh_timestamps();
	},
	refresh_timestamps: function() {
		this.$w.find(".avatar").remove();
		
		var doc = this.frm.doc;
		if(doc.__islocal || !doc.owner || !doc.modified_by) 
			return;
		
		$(repl('<span class="avatar avatar avatar-small">\
			<img title="%(created_by)s" src="%(avatar_created)s"/></span>\
			<span class="avatar avatar avatar-small">\
			<img title="%(modified_by)s" src="%(avatar_modified)s"/></span>', {
				created_by: wn.user_info(doc.owner).fullname,
				avatar_created: wn.utils.get_file_link(wn.user_info(doc.owner).image),
				modified_by: wn.user_info(doc.modified_by).fullname,
				avatar_modified: wn.utils.get_file_link(wn.user_info(doc.modified_by).image),
		})).insertAfter(this.$w.find(".appframe-title"));
		
		this.$w.find(".avatar:eq(0)").popover({
			trigger:"hover",
			title: wn._("Created By"),
			content: wn.user_info(this.frm.doc.owner).fullname 
				+" on "+ dateutil.str_to_user(this.frm.doc.creation)
		});

		this.$w.find(".avatar:eq(1)").popover({
			trigger:"hover",
			title: wn._("Modified By"),
			content: wn.user_info(this.frm.doc.modified_by).fullname 
				+" on "+ dateutil.str_to_user(this.frm.doc.modified)
		});
		
		this.$w.find('.avatar img').centerImage();
	},	
	hide_close: function() {
		this.$w.find('.close').toggle(false);
	}
})
