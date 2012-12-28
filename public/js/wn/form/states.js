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
		this.state_fieldname = wn.meta.get_state_fieldname(this.frm.doctype);
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
				<i class="icon-small"></i> <span class="state-text"></span> <span class="caret"></span></button>\
				<ul class="dropdown-menu">\
				</ul>\
			</div>\
		</div>').appendTo(this.frm.page_layout.body_header);
	},
		
	refresh: function() {
		// hide if its not yet saved
		if(this.frm.doc.__islocal) {
			this.set_default_state();
			this.$wrapper.toggle(false);
			return;
		}
		this.$wrapper.toggle(true);
		
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
			this.$wrapper.find(".btn").removeClass()
				.addClass("btn dropdown-toggle")
				.addClass("btn-" + state_doc.style.toLowerCase());
			
			// show actions from that state
			this.show_actions(state);
			
			// disable if not allowed
		} else {
			this.$wrapper.toggle(false);
		}				
	},
	
	show_actions: function(state) {
		var $ul = this.$wrapper.find("ul");
		$ul.empty();
		$.each(wn.model.get("Workflow Transition", {
			parent: this.frm.doctype,
			state: state,
		}), function(i, d) {
			if(in_list(user_roles, d.allowed)) {
				d.icon = wn.model.get("Workflow State", {name:d.next_state})[0].icon;
				
				$(repl('<li><a href="#" data-action="%(action)s">\
					<i class="icon icon-%(icon)s"></i> %(action)s</a></li>', d))
					.appendTo($ul);		
			}
		});
		
		// disable the button if user cannot change state
		this.$wrapper.find('.btn').attr('disabled', $ul.find("li").length ? false : true);
	},

	set_default_state: function() {
		var d = wn.model.get("Workflow Document State", {
			parent: this.frm.doctype,
			idx: 1
		});
		
		if(d && d.length) {
			this.frm.set_value_in_locals(this.frm.doctype, this.frm.docname, 
				this.state_fieldname, d[0].state);
			refresh_field(this.state_fieldname);
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
			var next_state = wn.model.get("Workflow Transition", {
				parent: me.frm.doctype,
				state: me.frm.doc[me.state_fieldname],
				action: action,
			})[0].next_state;
			
			me.frm.doc[me.state_fieldname] = next_state;
			
			var new_state = wn.model.get("Workflow Document State", {
				parent: me.frm.doctype,
				state: next_state
			})[0];

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
				me.frm.saveupdate();
			} else if(new_docstatus==2 && me.frm.doc.docstatus==1) {
				me.frm.savecancel();
			} else {
				msgprint("Docstatus transition from " + me.frm.doc.docstatus + " to" + 
					new_docstatus + " is not allowed.");
				return;
			}
			
			// hide dropdown
			$(this).parents(".dropdown-menu").prev().dropdown('toggle');
			
			return false;
		})
	}	
});