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

wn.ui.form.States = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.state_fieldname = wn.workflow.get_state_fieldname(this.frm.doctype);
		
		// no workflow?
		if(!this.state_fieldname)
			return;

		this.update_fields = wn.workflow.get_update_fields(this.frm.doctype);

		this.make();
		this.bind_action();

		var me = this;
		$(this.frm.wrapper).bind("render_complete", function() {
			me.refresh();
		})
	},
	
	make: function() {
		this.$wrapper = $('<div class="states" style="margin-bottom: 11px; height: 26px;">\
			<div class="btn-group">\
				<button class="btn dropdown-toggle" data-toggle="dropdown">\
				<i class="icon-small"></i> <span class="state-text"></span> <span class="caret"></span>\
				</button>\
				<ul class="dropdown-menu">\
				</ul>\
			</div>\
			<button class="btn btn-help">?</button>\
		</div>').appendTo(this.frm.page_layout.body_header);
		this.$wrapper.toggle(false);
		this.setup_help();
	},

	setup_help: function() {
		var me = this;
		this.$wrapper.find(".btn-help").click(function() {
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
				+ (me.frm.doc.__islocal ? ("<div class='alert'>"
					+wn._("Workflow will start after saving.")+"</div>") : "")
				+ "<p class='help'>"+wn._("Note: Other permission rules may also apply")+"</p>"
				).css({padding: '15px'});
			d.show();
		});
	},
	
	refresh: function() {
		// hide if its not yet saved
		this.$wrapper.toggle(false);
		if(this.frm.doc.__islocal) {
			this.set_default_state();
		}
		
		// state text
		var state = this.get_state();
		
		if(state) {
			// show current state on the button
			this.$wrapper.find(".state-text").text(state);
			
			var state_doc = wn.model.get("Workflow State", {name:state})[0];

			// set the icon
			this.$wrapper.find('.icon-small').removeClass()
				.addClass("icon-small icon-white")
				.addClass("icon-" + state_doc.icon);

			// set the style
			var btn = this.$wrapper.find(".btn:first");
			btn.removeClass().addClass("btn dropdown-toggle")

			if(state_doc && state_doc.style)
				btn.addClass("btn-" + state_doc.style.toLowerCase());
			
			// show actions from that state
			this.show_actions(state);
			
			this.$wrapper.toggle(true);
			if(this.frm.doc.__islocal) {
				this.$wrapper.find('.btn:first').attr('disabled', true);
			}
		}
	},
	
	show_actions: function(state) {
		var $ul = this.$wrapper.find("ul");
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
		this.$wrapper.find('.btn:first')
			.attr('disabled', $ul.find("li").length ? false : true);
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
		$(this.$wrapper).on("click", "[data-action]", function() {
			var action = $(this).attr("data-action");
			var next_state = wn.workflow.get_next_state(me.frm.doctype,
					me.frm.doc[me.state_fieldname], action);
			var current_state = me.frm.doc[me.state_fieldname];

			me.frm.doc[me.state_fieldname] = next_state;
			
			var new_state = wn.workflow.get_document_state(me.frm.doctype, next_state);
			var new_docstatus = new_state.doc_status;
			
			// update field and value
			if(new_state.update_field) {
				me.frm.set_value(new_state.update_field, new_state.update_value);
			}
			
			if(new_docstatus==1 && me.frm.doc.docstatus==0) {
				me.frm.savesubmit();
			} else if(new_docstatus==0 && me.frm.doc.docstatus==0) {
				me.frm.save();
			} else if(new_docstatus==1 && me.frm.doc.docstatus==1) {
				me.frm.save("Update");
			} else if(new_docstatus==2 && me.frm.doc.docstatus==1) {
				me.frm.savecancel();
			} else {
				msgprint(wn._("Document Status transition from ") + me.frm.doc.docstatus + " " 
					+ wn._("to") + 
					new_docstatus + " " + wn._("is not allowed."));
				return;
			}
			
			// hide dropdown
			$(this).parents(".dropdown-menu").prev().dropdown('toggle');
			
			return false;
		})
	}	
});
