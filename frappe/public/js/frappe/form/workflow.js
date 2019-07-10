// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.States = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.state_fieldname = frappe.workflow.get_state_fieldname(this.frm.doc);

		// no workflow?
		if(!this.state_fieldname)
			return;

		this.update_fields = frappe.workflow.get_update_fields(this.frm.doc);

		var me = this;
		$(this.frm.wrapper).bind("render_complete", function() {
			me.refresh();
		});
	},

	setup_help: function() {
		var me = this;
		var html_content = undefined;
		var state = me.get_state();
		if (!this.frm.doc.workflow_def) return;
		frappe.xcall('frappe.model.workflow.get_user_actions',{doc:cur_frm.doc}).then(r => {
			if (r && r.length){
				var action_html = function(actions){ 
					return $.map(actions.split(';'),
						function(d) {return d.split(':')[0]
							    };
					).join(", ") || __("None: End of Workflow");
				}
				var next_html = function(user_status){
					return $.map(user_status, function(u){
						return '<p>' + action_html(u.actions).bold() + ' by user ' + u.user.bold() + '</p>'
					}).join(' ')
				}
				html_content = "<p>"+__("Current status")+": " + state.bold() + "</p>"
				+ "<p>"+__("Document is only editable by users of role")+": "
					+ frappe.workflow.get_document_state(me.frm.doc, state).allow_edit.bold() + "</p>"
				+ "<p>"+__("Next actions")+": "+ next_html(r) +"</p>"
				+ (me.frm.doc.__islocal ? ("<div class='alert alert-info'>"
					+__("Workflow will start after saving.")+"</div>") : "")
				+ "<p class='help'>"+__("Note: Other permission rules may also apply")+"</p>";			
			}
			else{return;
			    }
		}).then(()=>{	
			if (html_content && html_content.length){			
				me.frm.page.add_action_item(__("Help"), function() {				
					var d = new frappe.ui.Dialog({
						title: "Workflow: " + me.frm.doc.workflow_def
					});			
					$(d.body).html(html_content).css({padding: '15px'});
					d.show();
				}, true);
			}
		})
	},

	refresh: function() {
		const me = this;
		// hide if its not yet saved
		if(this.frm.doc.__islocal) {
			this.set_default_state();
			return;
		}

		// state text
		const state = this.get_state();

		let doctype = this.frm.doctype;

		if(state) {
			// show actions from that state
			this.show_actions(state);
			this.refresh_field_status(state);
		}
	},

	refresh_field_status: function(state){
		const frm = this.frm;
		const docname = this.frm.docname;
		frappe.xcall('frappe.model.workflow.get_workflow_field_status',
			{workflow_name: frm.doc.workflow_def, state: state}).then((field_status)=>{
			$.each(field_status, function(i, f) {
				var parent_field = null;
				var field=f.field_name;
				if (f.field_name.indexOf('.')>0){
					parent_field= f.field_name.split('.')[0];
					field =f.field_name.split('.')[1];
				}
				if (f.reqd){frm.workflow_mandatory_entry = 1
					   }
				frm.set_df_property(field, 'read_only', f.read_only, docname, parent_field);
				frm.set_df_property(field, 'reqd', f.reqd, docname, parent_field);													
				frm.set_df_property(field, 'hidden', f.hidden, docname, parent_field);
			})
			if (frm.workflow_mandatory_entry){frm.perm[0].write=1;};
		})

	},

	show_actions: function() {
		var added = false;
		var me = this;
		var actions = '';
		var action_list = [];

		this.frm.page.clear_actions_menu();

		// if the loaded doc is dirty, don't show workflow buttons
		if (this.frm.doc.__unsaved===1) {
			return;
		}
		this.setup_help();
		function has_approval_access(allow_self_approval) {
			let approval_access = false;
			const user = frappe.session.user;
			if (user === 'Administrator'
				|| allow_self_approval
				|| user !== me.frm.doc.owner) {
				approval_access = true;
			}
			return approval_access;
		}
		frappe.xcall('frappe.model.workflow.get_user_actions',
			{doc:me.frm.doc, user: frappe.session.user}).then(r => {
			if (r && r.length){
				actions = r[0].actions;
				action_list = actions.split(';');
			}
			else{
				return;
			}
			$.each(action_list, function(i, d) {
				let action_arr = d.split(':');
				let action = action_arr[0];
				let transition = action_arr[1];
				let allow_self_approval = action_arr[2];
				if(has_approval_access(allow_self_approval)) {
					added = true;
					me.frm.page.add_action_item(__(action), function() {
						var apply_workflow =function(comment){
							frappe.xcall('frappe.model.workflow.apply_workflow',
								{doc: me.frm.doc, action: action, transition_name: transition,
								action_source: r[0].action_source, previous_user: r[0].previous_user,
								comment: comment})
								.then((doc) => {
									frappe.model.sync(doc);
									me.frm.refresh();
							});
						};
						const is_reqd = action.toLowerCase() == 'reject'? 1 : 0;
						var d = new frappe.ui.Dialog({
							title: __(action),
							
							fields:  [{fieldtype:'Data', fieldname:'comment', 
								label: __('Comment to Next User'), reqd:is_reqd}],
							primary_action: function() {
								var data = d.get_values();
								d.hide();							
								if (me.frm.workflow_mandatory_entry && action.toLowerCase() != 'reject' ){
									me.frm.save().then(apply_workflow(data.comment));
								}
								else{	
									apply_workflow(data.comment);
								}
							},
							primary_action_label: __(action)
						});
						d.show();																		
					});
				}
			});
			if(added && frappe.workflow.get_state(this.frm.doc) != frappe.workflow.get_default_state(this.frm.doc, this.frm.doc.docstatus)) {
				var special_actions = ['Forward', 'Add Additional Check'];
				$.each(special_actions, function(i, action) {
					me.frm.page.add_action_item(__(action), function() {
						var d = new frappe.ui.Dialog({
							title: __(action),
							fields:  [{fieldtype:'Link', fieldname:'next_user', options:'User',
								label: __('Select the Next User'), reqd:1},
							{fieldtype:'Data', fieldname:'comment',	label: __('Comment to Next User')}],
							primary_action: function() {
								var data = d.get_values();
								d.hide();							
								frappe.xcall('frappe.model.workflow.apply_workflow',
									{doc: me.frm.doc, actions: actions, action: action, 
									next_user: data.next_user, comment:data.comment})
								.then((doc) => {
									frappe.model.sync(doc);
									me.frm.refresh();
								});
							},
							primary_action_label: __(action)
						});
						d.show();
					});										
				});								
			}
			this.setup_btn(added);
		});

	},

	setup_btn: function(action_added) {
		if(action_added) {
			this.frm.page.btn_primary.addClass("hide");
			this.frm.page.btn_secondary.addClass("hide");
			this.frm.toolbar.current_status = "";
			
		}		
	},

	set_default_state: function() {
		var default_state = frappe.workflow.get_default_state(this.frm.doc, this.frm.doc.docstatus);
		if(default_state) {
			this.frm.set_value(this.state_fieldname, default_state);
		}
	},

	get_state: function() {
		if(!this.frm.doc[this.state_fieldname]) {
			this.set_default_state();
		}
		return this.frm.doc[this.state_fieldname];
	}
});
