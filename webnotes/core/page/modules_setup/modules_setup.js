
wn.pages['modules_setup'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Show or Hide Modules',
		single_column: true
	});
	
	wrapper.appframe.set_title_right("Update", function() {
		wn.modules_setup.update(this);
	})
	
	$('<div class="alert alert-info">'
		+wn._("Select modules to be shown (based on permission). If hidden, they will be hidden for all users.")+'</div>').appendTo($(wrapper).find(".layout-main"));
	$('<div id="modules-list">').appendTo($(wrapper).find(".layout-main"));
	
	wn.modules_setup.refresh_page();
}

wn.modules_setup = {
	refresh_page: function() {
		$('#modules-list').empty();
		
		var wrapper = $('<div class="list-group"></div>').appendTo("#modules-list");

		$.each(keys(wn.modules).sort(), function(i, m) {
			if(m!="Setup" && wn.modules[m].link) {
				var row = $('<div class="list-group-item">\
					<span class="check-area" style="margin-right: 10px;"></span> '
						+wn.ui.app_icon.get_html(m, true) 
						+ " <span> " +m+'</span></div>').appendTo("#modules-list");
				var $chk = $("<input type='checkbox' data-module='"+m+"' style='margin-top: -2px'>")
					.appendTo(row.find(".check-area"));
				if(!wn.boot.hidden_modules || wn.boot.hidden_modules.indexOf(m)==-1) {
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
		
		return wn.call({
			method: 'webnotes.core.page.modules_setup.modules_setup.update',
			args: {
				ml: ml
			},
			callback: function(r) {
				if(r.exc) msgprint("There were errors.")
			},
			btn: btn
		});
	}
	
}