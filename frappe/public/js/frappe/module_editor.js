frappe.ModuleEditor = Class.extend({
	init: function(frm, wrapper) {
		this.wrapper = $('<div class="row module-block-list"></div>').appendTo(wrapper);
		this.frm = frm;
		this.make();
	},
	make: function() {
		var me = this;
		this.frm.doc.__onload.all_modules.forEach(function(m) {
			$(repl('<div class="col-sm-6"><div class="checkbox">\
				<label><input type="checkbox" class="block-module-check" data-module="%(module)s">\
				%(module)s</label></div></div>', {module: m})).appendTo(me.wrapper);
		});
		this.bind();
	},
	refresh: function() {
		var me = this;
		this.wrapper.find(".block-module-check").prop("checked", true);
		$.each(this.frm.doc.block_modules, function(i, d) {
			me.wrapper.find(".block-module-check[data-module='"+ d.module +"']").prop("checked", false);
		});
	},
	bind: function() {
		var me = this;
		this.wrapper.on("change", ".block-module-check", function() {
			var module = $(this).attr('data-module');
			if ($(this).prop("checked")) {
				// remove from block_modules
				me.frm.doc.block_modules = $.map(me.frm.doc.block_modules || [], function(d) {
					if (d.module != module) {
						return d;
					}
				});
			} else {
				me.frm.add_child("block_modules", {"module": module});
			}
		});
	}
});