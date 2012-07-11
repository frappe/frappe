wn.ui.AppFrame = Class.extend({
	init: function(parent, title) {
		this.buttons = {};
		this.$w = $('<div></div>').appendTo(parent);
		
		this.$titlebar = $('<div class="appframe-titlebar">\
			<span class="appframe-title"></span>\
			<span class="close">&times;</span>\
		</div>').appendTo(this.$w);

		this.$w.find('.close').click(function() {
			window.history.back();
		})
		
		if(title) this.title(title);

	},
	title: function(txt) {
		this.$titlebar.find('.appframe-title').html(txt);
	},
	add_button: function(label, click, icon) {
		if(!this.$w.find('.appframe-toolbar').length)
			this.$w.append('<div class="appframe-toolbar"></div>');

		args = { label: label, icon:'' };
		if(icon) {
			args.icon = '<i class="icon '+icon+'"></i>';
		}
		this.buttons[label] = $(repl('<button class="btn btn-small">\
			%(icon)s %(label)s</button>', args))
			.click(click)
			.appendTo(this.$w.find('.appframe-toolbar'));
		return this.buttons[label];
	},
	clear_buttons: function() {
		this.$w.find('.appframe-toolbar').empty();
	}
});

// parent, title, single_column
// standard page with appframe

wn.ui.make_app_page = function(opts) {
	if(opts.single_column) {
		$(opts.parent).html('<div class="layout-wrapper layout-wrapper-appframe">\
			<div class="layout-appframe"></div>\
			<div class="layout-main"></div>\
		</div>');			
	} else {
		$(opts.parent).html('<div class="layout-wrapper layout-wrapper-background">\
			<div class="layout-appframe"></div>\
			<div class="layout-main-section"></div>\
			<div class="layout-side-section"></div>\
			<div class="clear"></div>\
		</div>');			
	}
	opts.parent.appframe = new wn.ui.AppFrame($(opts.parent).find('.layout-appframe'));
	if(opts.title) opts.parent.appframe.title(opts.title);
}