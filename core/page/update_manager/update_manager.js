wn.pages['update-manager'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Update This Application',
		single_column: true
	});					
	
	wrapper.update_this_app = new wn.UpdateThisApp(wrapper);
};

wn.UpdateThisApp = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.body = $(this.wrapper).find(".layout-main");
		this.wrapper.appframe.add_home_breadcrumb();
		this.wrapper.appframe.add_module_breadcrumb("Setup");
		this.wrapper.appframe.add_breadcrumb("icon-magnet");
		this.make();
	},
	
	make: function() {
		var me = this;
		
		if(wn.boot && wn.boot.expires_on) {
			wn.utils.set_intro(this.wrapper, $("<div></div>").appendTo(this.body), 
				wn._('This feature is only applicable to self hosted instances'));
			
		} else {
			this.wrapper.appframe.add_button(wn._("Get Latest Updates"), 
				function() { me.update_this_app(this); }, "icon-rss");

			this.wrapper.update_output = $('<pre class="well update-output"></pre>')
				.appendTo(this.body.append("<div></div>"));
			this.wrapper.update_output.text(wn._('Click on "Get Latest Updates"'));
		}
		
	},
	
	update_this_app: function(btn) {
		var me = this;
		wn.call({
			module: "core",
			page: "update_manager",
			method: "update_this_app",
			callback: function(r) {
				me.wrapper.update_output.text(r.message);
			},
			btn: btn,
		});
	},
});
