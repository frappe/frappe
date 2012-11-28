wn.ui.AppFrame = Class.extend({
	init: function(parent, title, module) {
		this.set_document_title = true;
		this.buttons = {};
		this.$w = $('<div></div>').appendTo(parent);
				
		this.$titlebar = $('<div class="appframe-titlebar">\
			<div class="appframe-marker"></div>\
			<span class="appframe-center">\
				<span class="appframe-title"></span>\
				<span class="appframe-subject"></span>\
			</span>\
			<span class="close" style="margin-top: 5px; margin-right: 7px;">&times;</span>\
		</div>').appendTo(this.$w);
		
		this.$w.find('.close').click(function() {
			window.history.back();
		})
		
		if(title) 
			this.set_title(title);
		if(module) 
			this.set_marker(module);
	},
	title: function(txt) {
		this.set_title(txt);
	},
	set_title: function(txt) {
		if(this.set_document_title) 
			document.title = txt;
		this.$titlebar.find(".appframe-title").html(txt);
	},
	set_marker: function(module) {
		var color = wn.get_module_color(module);
		this.$titlebar.find(".appframe-marker")
			.css({
				"background-color": color
			});
	},
	add_tab: function(tab_name, opacity, click) {		
		var span = $('<span class="appframe-tab"></span>')
			.html(tab_name).insertAfter(this.$titlebar.find(".close"));
		opacity && span.css("opacity", opacity);
		click && span.click(click);
		return span		
	},
	
	remove_tabs: function() {
		this.$w.find(".appframe-tab").remove();
	},
	
	add_module_tab: function(module) {
		this.add_tab('<span class="small-module-icons small-module-icons-'+
			module.toLowerCase()+'"></span>'+' <span>'
			+ wn._(module) + "</span>", 0.7, function() {
				wn.set_route(erpnext.modules[module]);
		});	
	},
		
	add_button: function(label, click, icon) {
		this.add_toolbar();
		args = { label: label, icon:'' };
		if(icon) {
			args.icon = '<i class="icon '+icon+'"></i>';
		}
		this.buttons[label] = $(repl('<button class="btn btn-small">\
			%(icon)s %(label)s</button>', args))
			.click(click)
			.appendTo(this.toolbar);
		return this.buttons[label];
	},

	add_help_button: function(txt) {
		this.add_toolbar();
		$('<button class="btn btn-small" style="float:right;" button-type="help">\
			<b>?</b></button>')
			.data('help-text', txt)
			.click(function() { msgprint($(this).data('help-text'), 'Help'); })
			.appendTo(this.toolbar);			
	},

	clear_buttons: function() {
		this.toolbar && this.toolbar.empty();
	},

	add_toolbar: function() {
		if(!this.toolbar)
			this.$w.append('<div class="appframe-toolbar"></div>');
		this.toolbar = this.$w.find('.appframe-toolbar');
	},
	add_label: function(label) {
		return $("<span class='label'>"+label+" </span>").appendTo(this.toolbar);
	},
	add_select: function(label, options) {
		this.add_toolbar();
		return $("<select style='width: 100px;'>")
			.add_options(options).appendTo(this.toolbar);
	},
	add_data: function(label) {
		this.add_toolbar();
		return $("<input style='width: 100px;' placeholder='"+ label +"'>")
			.appendTo(this.toolbar);
	}, 
	add_date: function(label, date) {
		this.add_toolbar();
		return $("<input style='width: 80px;'>").datepicker({
			dateFormat: sys_defaults.date_format.replace("yyyy", "yy"),
			changeYear: true,
		}).val(dateutil.str_to_user(date) || "").appendTo(this.toolbar);
	},
	add_ripped_paper_effect: function(wrapper) {
		if(!wrapper) var wrapper = wn.container.page;
		var layout_main = $(wrapper).find('.layout-main');
		if(!layout_main.length) {
			layout_main = $(wrapper).find('.layout-main-section');
		}
		layout_main.css({"padding-top":"25px"});
		$('<div class="ripped-paper-border"></div>')
			.prependTo(layout_main)
			.css({"width": $(layout_main).width()});
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
	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;
	if(opts.title) opts.parent.appframe.title(opts.title);
	if(opts.module) opts.parent.appframe.set_marker(opts.module);
}