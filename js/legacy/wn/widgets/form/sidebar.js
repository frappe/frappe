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
						icon: 'ic-doc_new',
						display: function() { 
							return in_list(profile.can_create, form.doctype) 
						},
						onclick: function() { new_doc(me.form.doctype) }
					},

					{
						type: 'link',
						label: 'Refresh',
						icon: 'ic-playback_reload',
						onclick: function() { me.form.reload_doc() }
					},

					{
						type: 'link',
						label: 'Print',
						display: function() { 
							return !(me.form.doc.__islocal || me.form.meta.allow_print);
						},
						icon: 'ic-print',
						onclick: function() { me.form.print_doc() }
					},

					{
						type: 'link',
						label: 'Email',
						display: function() { 
							return !(me.form.doc.__islocal || me.form.meta.allow_email);
						},
						icon: 'ic-mail',
						onclick: function() { me.form.email_doc() }
					},

					{
						type: 'link',
						label: 'Copy',
						display: function() { 
							return in_list(profile.can_create, me.form.doctype) && !me.form.meta.allow_copy 
						},
						icon: 'ic-clipboard_copy',
						onclick: function() { me.form.copy_doc() }
					},
					
					{
						type: 'link',
						label: 'Delete',
						display: function() { 
							return me.form.meta.allow_trash && cint(me.form.doc.docstatus) != 2 
							&& (!me.form.doc.__islocal) && me.form.perm[0][CANCEL] 
						},
						icon: 'ic-trash',
						onclick: function() { me.form.savetrash() }
					}
				]
			},

/*			{
				title: 'Follow this ' + get_doctype_label(me.form.doctype),
				render: function(wrapper) {
					new wn.widgets.follow.Follow(wrapper, me.form.doctype, me.form.docname);
				},
				display: function() { return !me.form.doc.__islocal }
			},*/

			{
				title: 'Attachments',
				render: function(wrapper) {
					me.form.attachments = new wn.widgets.form.sidebar.Attachments(wrapper, me, me.form.doctype, me.form.docname);
				},
				display: function() { return me.form.meta.allow_attach }
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

			{
				title: 'Comments',
				render: function(wrapper) {
					new wn.widgets.form.sidebar.Comments(wrapper, me, me.form.doctype, me.form.docname);
				},
				display: function() { return !me.form.doc.__islocal }
			}
		]
	}
	
	this.refresh = function() {
		var parent = this.form.page_layout.sidebar_area;
		if(!this.sidebar) {
			$y(parent, {paddingTop:'37px'})
			this.sidebar = new wn.widgets.PageSidebar(parent, this.opts);
		} else {
			this.sidebar.refresh();
		}
	}
	

}}
