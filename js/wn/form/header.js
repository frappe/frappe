wn.provide('wn.form');

wn.form.Header = Class.extend({
	init: function(parent) {
		this.buttons = {};
		this.$w = $('<div><h1></h1>\
			<a class="close" onclick="window.history.back();">&times;</a>
			<div class="label-area"></div>\
			<div class="toolbar-area"></div></div><hr>').
			appendTo(parent);
	},
	refresh: function() {
		var m = cur_frm.meta;

		this.$w.toggle(!m.hide_heading && !cur_frm.in_dialog);
		this.$w.find('.toolbar-area').toggle(m.hide_toolbar);
		
		this.$w.find('.toolbar-area').empty();
		this.add_buttons();
	},
	
	add_buttons: function() {
		// Print View
		if(cur_frm.meta.read_only_onload && !cur_frm.doc.__islocal) {
			if(cur_frm.editable) {
				this.add_button({
					label:'Print View',
					click: function() { 
						cur_frm.is_editable[cur_frm.docname] = 0;				
						cur_frm.refresh();	
					},
					icon: 'icon-print'
				})
			}
		}
	
		switch(cur_frm.doc.docstatus) {
			case 0:
				if(p[WRITE]) {
					this.add_button({
						label:'Save', click:function() { cur_frm.save('Save'); }
					});
					if(!cur_frm.doc.__islocal) {
						this.add_button({
							label:'Submit', click:function() { cur_frm.savesubmit(); },
							icon: 'icon-lock'
						});	
					};
				}
				break;
			case 1:
				if(p[SUBMIT] && cur_frm.doc.__unsaved) {
					this.add_button({
						label:'Update', click: function() { cur_frm.saveupdate(); }
					});
				}
				if(p[CANCEL]) {
					this.add_button({
						label:'Cancel', click: function() { cur_frm.savecancel(); },
						icon: 'icon-remove'
					});
				}
				break;
			case 2:
				if(p[AMEND]) {
					this.add_button({
						label:'Amend', click: function() { cur_frm.amend_doc(); },
						icon: 'icon-pencil'
					});
				}
			
		}
		
	},
	
	add_button: function(opts) {
		// label, icon, click
		var b = $('<button class="btn btn-small"></button>')
			.text(opts.label)
			.click(click)
			.appendTo(this.$w.find('.toolbar-area'))
		if(opts.icon) {
			b.html('<i class="'+opts.icon+'"></i> ' + opts.label);
		}
		this.buttons[opts.label] = b;
	}
})