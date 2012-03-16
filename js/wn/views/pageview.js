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
		this.render();
	},
	render: function() {
		var me = this;
		
		this.pagedoc = locals.Page[this.name];
		this.wrapper = wn.container.add_page(this.name);
		
		// set content, script and style
		this.wrapper.innerHTML = this.pagedoc.content;
		wn.dom.eval(this.pagedoc.__script || this.pagedoc.script || '');
		wn.dom.set_style(this.pagedoc.style);
		
		this.trigger('onload');
		
		// set events
		$(this.wrapper).bind('show', function() {
			cur_frm = null;
			me.trigger('onshow');
		});
	},
	trigger: function(event) {
		var me = this;
		try {
			if(pscript[event+'_'+this.name]) {
				pscript[event+'_'+this.name](me.wrapper);				
			}
			if(me.wrapper[event]) {
				me.wrapper[event](me.wrapper);
			}
		} catch(e) { 
			console.log(e); 
		}
	}
})