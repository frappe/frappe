// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 


wn.ui.toolbar.Toolbar = Class.extend({
	init: function() {
		this.make();
		this.make_home();
		this.make_document();
		wn.ui.toolbar.recent = new wn.ui.toolbar.RecentDocs();
		this.make_tools();
		this.set_user_name();
		this.make_logout();
		$('.dropdown-toggle').dropdown();
		
		$(document).trigger('toolbar_setup');
	},
	make: function() {
		$('header').append('<div class="navbar navbar-fixed-top">\
			<div class="navbar-inner">\
			<div class="container">\
				<a class="brand"></a>\
				<ul class="nav">\
				</ul>\
				<img src="images/lib/ui/spinner.gif" id="spinner"/>\
				<ul class="nav pull-right">\
					<li class="dropdown">\
						<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
							onclick="return false;" id="toolbar-user-link"></a>\
						<ul class="dropdown-menu" id="toolbar-user">\
						</ul>\
					</li>\
				</ul>\
			</div>\
			</div>\
			</div>');		
	},
	make_home: function() {
		$('.navbar .brand').attr('href', "#");
	},

	make_document: function() {
		wn.ui.toolbar.new_dialog = new wn.ui.toolbar.NewDialog();
		wn.ui.toolbar.search = new wn.ui.toolbar.Search();
		wn.ui.toolbar.report = new wn.ui.toolbar.Report();
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" href="#"  data-toggle="dropdown"\
				onclick="return false;">Document<b class="caret"></b></a>\
			<ul class="dropdown-menu" id="toolbar-document">\
				<li><a href="#" onclick="return wn.ui.toolbar.new_dialog.show();">\
					<i class="icon-plus"></i> New</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.search.show();">\
					<i class="icon-search"></i> Search</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.report.show();">\
					<i class="icon-list"></i> Report</a></li>\
			</ul>\
		</li>');
	},

	make_tools: function() {
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
				onclick="return false;">Tools<b class="caret"></b></a>\
			<ul class="dropdown-menu" id="toolbar-tools">\
				<li><a href="#" onclick="return wn.ui.toolbar.clear_cache();">Clear Cache & Refresh</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.show_about();">About</a></li>\
			</ul>\
		</li>');
		
		if(has_common(user_roles,['Administrator','System Manager'])) {
			$('#toolbar-tools').append('<li><a href="#" \
				onclick="return wn.ui.toolbar.download_backup();">\
				Download Backup</a></li>');
		}
	},
	set_user_name: function() {
		var fn = user_fullname;
		if(fn.length > 15) fn = fn.substr(0,12) + '...';
		$('#toolbar-user-link').html(fn + '<b class="caret"></b>');
	},

	make_logout: function() {
		// logout
		$('#toolbar-user').append('<li><a href="#" onclick="return wn.app.logout();">Logout</a></li>');
	}
});

wn.ui.toolbar.clear_cache = function() {
	localStorage && localStorage.clear();
	$c('webnotes.session_cache.clear',{},function(r,rt){ 
		if(!r.exc) {
			show_alert(r.message);
			location.reload();
		}
	});
	return false;
}

wn.ui.toolbar.download_backup = function() {
	$c('webnotes.utils.backups.get_backup',{},function(r,rt) {});
	return false;
}

wn.ui.toolbar.show_about = function() {
	try {
		wn.ui.misc.about();		
	} catch(e) {
		console.log(e);
	}
	return false;
}
