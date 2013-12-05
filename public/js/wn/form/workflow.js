// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.ui.form.States = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.state_fieldname = wn.workflow.get_state_fieldname(this.frm.doctype);
		
		// no workflow?
		if(!this.state_fieldname)
			return;

		this.update_fields = wn.workflow.get_update_fields(this.frm.doctype);

		var me = this;
		$(this.frm.wrapper).bind("render_complete", function() {
			me.refresh();
		})
	},
	
	make: function() {
		this.parent = this.frm.appframe.parent
			.find(".workflow-button-area")
			.empty()
			.removeClass("hide");
		
		this.workflow_button = $('<button class="btn btn-default dropdown-toggle" data-toggle="dropdown">\
			<i class="icon-small"></i> <span class="state-text"></span>\
			<span class="caret"></span></button>')
			.appendTo(this.parent).dropdown();
		this.dropdown = $('<ul class="dropdown-menu">').insertAfter(this.workflow_button);
		this.help_btn = $('<button class="btn btn-default"><i class="icon-question-sign"></i></button').
			insertBefore(this.workflow_button);
		this.setup_help();
		this.bind_action();
	},

	setup_help: function() {
		var me = this;
		this.help_btn.click(function() {
			wn.workflow.setup(me.frm.doctype);
			var state = me.get_state();
			var d = new wn.ui.Dialog({
				title: "Workflow: "
					+ wn.workflow.workflows[me.frm.doctype].name
			})
			var next_html = $.map(wn.workflow.get_transitions(me.frm.doctype, state), 
				function(d) { 
					return d.action.bold() + wn._(" by Role ") + d.allowed;
				}).join(", ") || wn._("None: End of Workflow").bold();
			
			$(d.body).html("<p>"+wn._("Current status")+": " + state.bold() + "</p>"
				+ "<p>"+wn._("Document is only editable by users of role")+": " 
					+ wn.workflow.get_document_state(me.frm.doctype,
						state).allow_edit.bold() + "</p>"
				+ "<p>"+wn._("Next actions")+": "+ next_html +"</p>"
				+ (me.frm.doc.__islocal ? ("<div class='alert alert-info'>"
					+wn._("Workflow will start after saving.")+"</div>") : "")
				+ "<p class='help'>"+wn._("Note: Other permission rules may also apply")+"</p>"
				).css({padding: '15px'});
			d.show();
		});
	},
	
	refresh: function() {
		// hide if its not yet saved
		if(this.frm.doc.__islocal) {
			this.set_default_state();
			this.parent.toggle(false);
			return;
		}

		this.make();
		
		// state text
		var state = this.get_state();
		
		if(state) {
			// show current state on the button
			this.workflow_button.find(".state-text").text(state);
			
			var state_doc = wn.model.get("Workflow State", {name:state})[0];

			if (state_doc) {
				// set the icon
				this.workflow_button.find('i').removeClass()
					.addClass("icon-white")
					.addClass("icon-" + state_doc.icon);

				// set the style
				this.workflow_button.removeClass().addClass("btn btn-default dropdown-toggle")

				if(state_doc && state_doc.style)
					this.workflow_button.addClass("btn-" + state_doc.style.toLowerCase());
			}

			// show actions from that state
			this.show_actions(state);

			if(this.frm.doc.__islocal) {
				this.workflow_button.prop('disabled', true);
			}
		}
	},
	
	show_actions: function(state) {
		var $ul = this.dropdown;
		$ul.empty();

		$.each(wn.workflow.get_transitions(this.frm.doctype, state), function(i, d) {
			if(in_list(user_roles, d.allowed)) {
				d.icon = wn.model.get("Workflow State", {name:d.next_state})[0].icon;
				
				$(repl('<li><a href="#" data-action="%(action)s">\
					<i class="icon icon-%(icon)s"></i> %(action)s</a></li>', d))
					.appendTo($ul);		
			}
		});

		// disable the button if user cannot change state
		var is_final = !$ul.find("li").length;
		this.workflow_button
			.prop('disabled', is_final);
		this.workflow_button.find(".caret").toggle(is_final ? false : true)
	},

	set_default_state: function() {
		var default_state = wn.workflow.get_default_state(this.frm.doctype);
		if(default_state) {
			this.frm.set_value(this.state_fieldname, default_state);
		}
	},
	
	get_state: function() {
		if(!this.frm.doc[this.state_fieldname]) {
			this.set_default_state();
		}			
		return this.frm.doc[this.state_fieldname];
	},
	
	bind_action: function() {
		var me = this;
		this.dropdown.on("click", "[data-action]", function() {
			var action = $(this).attr("data-action");
			// capture current state
			var doc_before_action = copy_dict(me.frm.doc);

			// set new state
			var next_state = wn.workflow.get_next_state(me.frm.doctype,
					me.frm.doc[me.state_fieldname], action);			
			me.frm.doc[me.state_fieldname] = next_state;
			var new_state = wn.workflow.get_document_state(me.frm.doctype, next_state);
			var new_docstatus = cint(new_state.doc_status);

			// update field and value
			if(new_state.update_field) {
				me.frm.set_value(new_state.update_field, new_state.update_value);
			}

			// revert state on error
			var on_error = function() {
				// reset in locals
				locals[me.frm.doctype][me.frm.docname] = doc_before_action;
				me.frm.refresh();
			}

			if(new_docstatus==1 && me.frm.doc.docstatus==0) {
				me.frm.savesubmit(null, on_error);
			} else if(new_docstatus==0 && me.frm.doc.docstatus==0) {
				me.frm.save("Save", null, null, on_error);
			} else if(new_docstatus==1 && me.frm.doc.docstatus==1) {
				me.frm.save("Update", null, null, on_error);
			} else if(new_docstatus==2 && me.frm.doc.docstatus==1) {
				me.frm.savecancel(null, on_error);
			} else {
				msgprint(wn._("Document Status transition from ") + me.frm.doc.docstatus + " " 
					+ wn._("to") + 
					new_docstatus + " " + wn._("is not allowed."));
				return false;
			}
			
			// hide dropdown
			me.workflow_button.dropdown('toggle');
			
			return false;
		})
	}	
});
