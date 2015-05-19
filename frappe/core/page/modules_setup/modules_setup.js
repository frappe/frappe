
frappe.pages['modules_setup'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Show or Hide Modules'),
		single_column: true
	});

	frappe.breadcrumbs.add("Setup");

	wrapper.page.set_primary_action(__("Update"), function() {
		frappe.modules_setup.update(this);
	});

	page.main.css({"padding":"15px"});

	$('<p>'
		+__("Select modules to be shown (based on permission). If hidden, they will be hidden for all users.")+'</p>').appendTo($(wrapper).find(".layout-main"));
	$('<div id="modules-list">').appendTo(page.main);

	frappe.modules_setup.refresh_page();
}

frappe.modules_setup = {
	refresh_page: function() {
		$('#modules-list').empty();

		var wrapper = $('<div class="list-group"></div>').appendTo("#modules-list");

		$.each(keys(frappe.modules).sort(), function(i, m) {
			if(m!="Setup") {
				var row = $('<div class="list-group-item">\
					<span class="check-area" style="margin-right: 10px;"></span> '
				+ " <span> " + __(m) +'</span></div>').appendTo("#modules-list");
				var $chk = $("<input type='checkbox' data-module='"+m+"' style='margin-top: -2px'>")
					.appendTo(row.find(".check-area"));
				if(!frappe.boot.hidden_modules || frappe.boot.hidden_modules.indexOf(m)==-1) {
					$chk.prop("checked", true);
				}
			}
		});
	},
	update: function(btn) {
		var ml = [];
		$('#modules-list [data-module]:checkbox:not(:checked)').each(function() {
			ml.push($(this).attr('data-module'));
		});

		return frappe.call({
			method: 'frappe.core.page.modules_setup.modules_setup.update',
			args: {
				ml: ml
			},
			callback: function(r) {
				if(r.exc) msgprint(__("There were errors"))
			},
			btn: btn
		});
	}

}
