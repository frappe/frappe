// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.IconBar = class IconBar {
	constructor(parent, n_groups) {
		this.parent = parent;
		this.buttons = {};
		this.make(n_groups);
	}
	make(n_groups) {
		this.$wrapper = $('<div class="iconbar-wrapper hide"></div>').appendTo(this.parent);
		for (var i = 0; i < n_groups; i++) {
			this.get_group(i + 1);
		}
	}
	get_group(group) {
		var $ul = this.$wrapper.find(".iconbar-" + group + " ul");

		if (!$ul.length)
			$ul = $('<div class="iconbar iconbar-' + group + ' hide"><ul></ul></div>')
				.appendTo(this.$wrapper)
				.find("ul");

		return $ul;
	}
	add_btn(group, icon, label, click) {
		var $ul = this.get_group(group);
		var $li = $('<li><i class="' + icon + '"></i></li>')
			.appendTo($ul)
			.on("click", function () {
				click.apply(this);
				return false;
			});

		$li.find("i")
			.attr("title", label)
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		this.$wrapper.find(".iconbar-" + group).removeClass("hide");
		this.show();
		return $li;
	}
	hide(group) {
		if (group) {
			this.$wrapper.find(".iconbar-" + group).addClass("hide");
			this.check_if_all_hidden();
		} else {
			this.$wrapper.addClass("hide").trigger("hidden");
		}
	}
	show(group) {
		if (group) {
			this.$wrapper.find(".iconbar-" + group).removeClass("hide");
			this.show();
		} else {
			if (this.$wrapper.hasClass("hide")) this.$wrapper.removeClass("hide").trigger("shown");
		}
	}
	clear(group) {
		var me = this;
		this.$wrapper
			.find(".iconbar-" + group)
			.addClass("hide")
			.find("ul")
			.empty();
		this.check_if_all_hidden();
	}
	check_if_all_hidden() {
		if (!this.$wrapper.find(".iconbar:visible").length) {
			this.hide();
		}
	}
};
