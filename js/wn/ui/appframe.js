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
		this.clear_breadcrumbs();
		this.add_breadcrumb(txt);
	},
	make_toolbar: function() {
		if(!this.$w.find('.appframe-toolbar').length)
			this.$w.append('<div class="appframe-toolbar"></div>');	
	},
	add_button: function(label, click, icon) {
		this.make_toolbar();
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
	add_help_button: function(txt) {
		this.make_toolbar();
		$('<button class="btn btn-small" style="float:right;" button-type="help">\
			<b>?</b></button>')
			.data('help-text', txt)
			.click(function() { msgprint($(this).data('help-text'), 'Help'); })
			.appendTo(this.$w.find('.appframe-toolbar'));			
	},
	clear_buttons: function() {
		this.$w.find('.appframe-toolbar').empty();
	},
	add_breadcrumb: function(html) {
		if(!this.$breadcrumbs)
			this.$breadcrumbs = $('</span>\
				<span class="breadcrumb-area"></span>').appendTo(this.$titlebar);
		
		var crumb = $('<span>').html(html);
		
		// first breadcrumb is a title
		if(!this.$breadcrumbs.find('span').length) {
			crumb.addClass('appframe-title');
		}
		crumb.appendTo(this.$breadcrumbs);
	},
	clear_breadcrumbs: function() {
		this.$breadcrumbs && this.$breadcrumbs.empty();
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