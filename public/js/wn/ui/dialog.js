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

wn.provide('wn.ui');

wn.ui.Dialog = wn.ui.FieldGroup.extend({
	init: function(opts) {
		this.display = false;
		if(!opts.width) opts.width = 480;

		$.extend(this, opts);
		this.make();
		
		this.dialog_wrapper = this.wrapper;
		
		// init fields
		if(this.fields) {
			this.parent = this.body
			this._super({});
		}
	},
	make: function() {		
		this.$wrapper = $('<div class="modal fade in" style="overflow: auto;">\
			<div class="modal-dialog">\
				<div class="modal-content">\
					<div class="modal-header">\
						<button type="button" class="close" \
							data-dismiss="modal" aria-hidden="true">&times;</button>\
						<h4 class="modal-title"></h4>\
					</div>\
					<div class="modal-body">\
					</div>\
				</div>\
			</div>\
			</div>')
			.appendTo(document.body);
		this.wrapper = this.$wrapper.find('.modal-dialog').get(0);

		this.make_head();
		this.body = this.$wrapper.find(".modal-body").get(0);	
	},
	make_head: function() {
		var me = this;
		//this.appframe = new wn.ui.AppFrame(this.wrapper);
		//this.appframe.set_document_title = false;
		this.set_title(this.title);
	},
	set_title: function(t) {
		this.$wrapper.find(".modal-title").html(t);
	},
	show: function() {
		// already live, do nothing
		var me = this;
		if(this.display) return;

		// show it
		this.$wrapper.modal("show").on("hide", function() {
			me.hide(true);
		});
		
		this.display = true;
		cur_dialog = this;

		// call onshow
		if(this.onshow)this.onshow();
		
		// focus on first input
		var first = $(this.wrapper).find(':input:first');
		if(first.attr("data-fieldtype")!="Date") {
			first.focus();
		}
	},
	hide: function(from_event) {
		// call onhide
		if(this.onhide) this.onhide();

		// hide
		if(!from_event)
			this.$wrapper.modal("hide");

		// flags
		this.display = false;
		cur_dialog = null;
	},
	no_cancel: function() {
		this.appframe.$titlebar.find('.close').toggle(false);
	}
});

// close open dialogs on ESC
$(document).bind('keydown', function(e) {
	if(cur_dialog && !cur_dialog.no_cancel_flag && e.which==27) {
		cur_dialog.hide();
	}
});