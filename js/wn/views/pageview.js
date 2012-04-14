wn.provide('wn.views.pageview');

wn.views.pageview = {
	pages: {},
	with_page: function(name, callback) {
		if(!locals.Page[name]) {
			wn.call({
				method: 'webnotes.widgets.page.getpage', 
				args: {'name':name },
				callback: callback
			});
		} else {
			callback();
		}		
	},
	show: function(name) {
		if(!name) return;
		wn.views.pageview.with_page(name, function() {
			if(!wn.pages[name]) {
				wn.views.pageview.pages[name]  = new wn.views.Page(name);
			}
			wn.container.change_to(name);			
		});
	}
}

wn.views.Page = Class.extend({
	init: function(name) {
		this.name = name;
		var me = this;
		this.pagedoc = locals.Page[this.name];
		this.wrapper = wn.container.add_page(this.name);
		this.wrapper.label = this.pagedoc.title || this.pagedoc.name;
		
		// set content, script and style
		this.wrapper.innerHTML = this.pagedoc.content;
		wn.dom.eval(this.pagedoc.__script || this.pagedoc.script || '');
		wn.dom.set_style(this.pagedoc.style);
		
		this.trigger('onload');
		
		// set events
		$(this.wrapper).bind('show', function() {
			cur_frm = null;
			me.trigger('onshow');
			me.trigger('refresh');
		});
	},
	trigger: function(eventname) {
		var me = this;
		try {
			if(pscript[eventname+'_'+this.name]) {
				pscript[eventname+'_'+this.name](me.wrapper);				
			} else if(me.wrapper[eventname]) {
				me.wrapper[eventname](me.wrapper);
			}
		} catch(e) { 
			console.log(e); 
		}
	}
})
