wn.pages['update-manager'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Update ' + wn.app.name,
		single_column: true
	});					
	
	wrapper.update_this_app = new wn.UpdateThisApp(wrapper);
};

wn.UpdateThisApp = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.body = $(this.wrapper).find(".layout-main");
		this.wrapper.appframe.add_home_breadcrumb();
		this.wrapper.appframe.add_module_icon("Setup");
		this.wrapper.appframe.add_breadcrumb("icon-magnet");
		this.make();
	},
	
	make: function() {
		var me = this;
		
		if(wn.boot && wn.boot.expires_on) {
			wn.utils.set_intro(this.wrapper, $("<div></div>").appendTo(this.body), 
				wn._('This feature is only applicable to self hosted instances'));
			
		} else {
			this.wrapper.appframe.add_button(wn._("Update"), 
				function() { me.update_this_app(this); }, "icon-rss");

			this.wrapper.update_output = $('<pre class="update-output"></pre>')
				.appendTo(this.body);
			this.wrapper.update_output.toggle(false);
			
			this.wrapper.progress_bar = $('<div class="app-update-progress-bar well"></div>')
				.appendTo(this.body);
			this.wrapper.progress_bar.text(wn._('Click on "Get Latest Updates"'));
		}
		
	},
	
	update_this_app: function(btn) {
		var me = this;
		
		me.wrapper.update_output.toggle(false);
		me.wrapper.progress_bar.empty().toggle(true);
		this.wrapper.progress_bar.html('<div class="progress progress-striped active"> \
			    <div class="progress-bar progress-bar-info" style="width: 100%;"></div> \
		    </div> \
			<div>' + wn._("Update is in progress. This may take some time.") + '</div>');
		
		return wn.call({
			module: "core",
			page: "update_manager",
			method: "update_this_app",
			callback: function(r) {
				me.wrapper.update_output.toggle(true);
				me.wrapper.progress_bar.empty().toggle(false);
				me.wrapper.update_output.text(r.message);
			},
			btn: btn,
		});
	},
});
