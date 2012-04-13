wn.ui.AppFrame = Class.extend({
	init: function(parent) {
		this.buttons = {};
		this.$w = $('<div></div>').appendTo(parent);
		
		this.$titlebar = $('<div class="appframe-titlebar">\
			<span class="appframe-title"></span>\
			<span class="close">&times;</span>\
		</div>').appendTo(this.$w);

		this.$w.find('.close').click(function() {
			window.history.back();
		})

	},
	add_button: function(label, click, icon) {
		if(!this.$w.find('.appframe-toolbar').length)
			this.$w.append('<div class="appframe-toolbar"></div>');

		args = { label: label, icon:'' };
		if(icon) {
			args.icon = '<i class="'+icon+'"></i>';
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
})