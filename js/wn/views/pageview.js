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
		if(!name) name = wn.boot.home_page;
		wn.views.pageview.with_page(name, function(r) {
			if(r && r.exc) {
				if(!r['403'])wn.container.change_to('404');
			} else if(!wn.pages[name]) {
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


wn.views.make_404 = function() {
	var page = wn.container.add_page('404');
	$(page).html('<div class="layout-wrapper">\
		<h1>Not Found</h1><br>\
		<p>Sorry we were unable to find what you were looking for.</p>\
		<p><a href="#">Go back to home</a></p>\
		</div>').toggle(false);
};

wn.views.make_403 = function() {
	var page = wn.container.add_page('403');
	$(page).html('<div class="layout-wrapper">\
		<h1>Not Permitted</h1><br>\
		<p>Sorry you are not permitted to view this page.</p>\
		<p><a href="#">Go back to home</a></p>\
		</div>').toggle(false);
};