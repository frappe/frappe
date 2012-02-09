wn.require('lib/css/bootstrap/bootstrap-topbar.css');

wn.ui.toolbar.Toolbar = Class.extend({
	init: function() {
		this.make();
		this.make_home();
		this.make_new();
		this.make_search();
		this.make_report();
		wn.ui.toolbar.recent = new wn.ui.toolbar.RecentDocs();
		if(in_list(user_roles, 'Administrator'))
			this.make_options();
		this.make_tools();
		this.set_user_name();
		this.make_logout();
		
		$('.topbar').dropdown();
		
		$(document).trigger('toolbar_setup');
	},
	make: function() {
		$('header').append('<div class="topbar">\
			<div class="topbar-inner">\
			<div class="container">\
				<a class="brand"></a>\
				<ul class="nav">\
				</ul>\
				<img src="lib/images/ui/spinner.gif" id="spinner"/>\
				<ul class="nav secondary-nav">\
					<li class="dropdown">\
						<a class="dropdown-toggle" href="#" onclick="return false;" id="toolbar-user-link"></a>\
						<ul class="dropdown-menu" id="toolbar-user">\
						</ul>\
					</li>\
				</ul>\
			</div>\
			</div>\
			</div>');		
	},
	make_home: function() {
		$('.topbar .nav:first').append('<li><a href="#'+home_page+'">Home</a></li>')
	},
	make_new: function() {
		$('.topbar .nav:first').append('<li><a href="#" \
			onclick="return wn.ui.toolbar.new_dialog.show();">New</a></li>');
	},
	make_search: function() {
		$('.topbar .nav:first').append('<li><a href="#" \
			onclick="return wn.ui.toolbar.search.show();">Search</a></li>');
	},
	make_report: function() {
		$('.topbar .nav:first').append('<li><a href="#" \
			onclick="return wn.ui.toolbar.report.show();">Report</a></li>');
	},
	make_tools: function() {
		$('.topbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" href="#" onclick="return false;">Tools</a>\
			<ul class="dropdown-menu" id="toolbar-tools">\
				<li><a href="#" onclick="return err_console.show();">Error Console</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.clear_cache();">Clear Cache</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.show_about();">About</a></li>\
			</ul>\
		</li>');
		
		if(has_common(user_roles,['Administrator','System Manager'])) {
			$('#toolbar-tools').append('<li><a href="#" \
				onclick="return wn.ui.toolbar.download_backup();">\
				Download Backup</a></li>');
		}
	},
	make_options: function() {
		$('.topbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" href="#" onclick="return false;">Options</a>\
			<ul class="dropdown-menu" id="toolbar-options">\
			</ul>\
		</li>');

		profile.start_items.sort(function(a,b){return (a[4]-b[4])});
		
		for(var i=0;i< profile.start_items.length;i++) {
			var d = profile.start_items[i];
			var ispage = d[0]=='Page';
			$('#toolbar-options').append(repl('<li><a href="#%(type)s%(dt)s%(dn)s">\
				%(dn)s</a></li>', {
					type : (ispage ? '' : 'Form/'),
					dt : (ispage ? '' : (d[0] + '/')), 
					dn : d[5] || d[1]
				}));		
		}
	},

	set_user_name: function() {
		var fn = user_fullname;
		if(fn.length > 15) fn = fn.substr(0,12) + '...';
		$('#toolbar-user-link').html(fn);
	},

	make_logout: function() {
		// logout
		$('#toolbar-user').append('<li><a href="#" onclick="return logout();">Logout</a></li>');
	}
});

wn.ui.toolbar.clear_cache = function() {
	localStorage && localStorage.clear();
	$c('webnotes.session_cache.clear',{},function(r,rt){ show_alert(r.message); });
	return false;
}

wn.ui.toolbar.download_backup = function() {
	$c('webnotes.utils.backups.get_backup',{},function(r,rt) {});
	return false;
}

wn.ui.toolbar.show_about = function() {
	try {
		wn.require('lib/js/wn/misc/about.js');
		wn.ui.misc.about();		
	} catch(e) {
		console.log(e);
	}
	return false;
}
