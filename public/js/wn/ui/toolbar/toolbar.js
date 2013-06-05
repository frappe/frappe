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
		//this.make_modules();
		this.make_quick_search();
		this.make_file();
		//this.make_actions();
		wn.ui.toolbar.recent = new wn.ui.toolbar.RecentDocs();
		wn.ui.toolbar.bookmarks = new wn.ui.toolbar.Bookmarks();
		this.make_tools();
		this.set_user_name();
		this.make_logout();
		$('.dropdown-toggle').dropdown();
		
		$(document).trigger('toolbar_setup');
		
		// clear all custom menus on page change
		$(document).on("page-change", function() {
			$("header .navbar .custom-menu").remove();
		})
	},
	make: function() {
		$('header').append('<div class="navbar navbar-fixed-top navbar-inverse" style="min-height: 50px;">\
			<div class="container">\
				<button type="button" class="navbar-toggle" data-toggle="collapse" \
					data-target=".navbar-responsive-collapse">\
					<span class="icon-bar"></span>\
					<span class="icon-bar"></span>\
					<span class="icon-bar"></span>\
				</button>\
				<a class="navbar-brand" href="#"></a>\
				<div class="nav-collapse collapse navbar-responsive-collapse">\
					<ul class="nav navbar-nav">\
					</ul>\
					<img src="lib/images/ui/spinner.gif" id="spinner"/>\
					<ul class="nav navbar-nav pull-right">\
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
		$('.navbar-brand').attr('href', "#");
	},

	make_modules: function() {
		$('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#"\
				title="'+wn._("Modules")+'"\
				onclick="return false;">'+wn._("Modules")+'</a>\
			<ul class="dropdown-menu modules">\
			</ul>\
			</li>').prependTo('.navbar .nav:first');

		var modules_list = wn.user.get_desktop_items().sort();
		var menu_list = $(".navbar .modules");

		var _get_list_item = function(m) {
			args = {
				module: m,
				module_page: wn.modules[m].link,
				module_label: wn._(wn.modules[m].label || m),
				icon: wn.modules[m].icon
			}

			return repl('<li><a href="#%(module_page)s" \
				data-module="%(module)s"><i class="%(icon)s" style="display: inline-block; \
					width: 21px; margin-top: -2px; margin-left: -7px;"></i>\
				%(module_label)s</a></li>', args);
		}

		// desktop
		$('<li><a href="#desktop"><i class="icon-th"></i> '
			+ wn._("Desktop") + '</a></li>\
			<li class="divider"></li>').appendTo(menu_list) 

		// add to dropdown
		$.each(modules_list,function(i, m) {
			if(m!='Setup') {
				menu_list.append(_get_list_item(m));			
			}
		})

		// setup for system manager
		if(user_roles.indexOf("System Manager")!=-1) {
			menu_list.append('<li class="divider">' + _get_list_item("Setup"));
		}
	
	},
	make_quick_search: function() {
		$('.navbar .nav:first').append('<li class="dropdown" id="go-dropdown"> \
			<a class="dropdown-toggle" href="#"  data-toggle="dropdown"\
				title="'+wn._("Go")+'"\
				onclick="return false;">'+wn._("Go")+'</a>\
			<ul class="dropdown-menu" id="navbar-doctype">\
				<li><form>\
					<div class="input-group col col-lg-7" style="width: 300px; margin: 20px 10px;">\
						<select id="go-doctype-list"></select>\
						<span class="input-group-btn">\
							<button class="btn btn-default" type="button" id="go-new-btn">\
								<span class="icon icon-plus"></span></button>\
						</span> \
					</div> \
					<div class="input-group col col-lg-7" style="width: 300px; margin: 20px 10px;">\
						<input type="text" id="go-search-input"></input>\
						<span class="input-group-btn">\
							<button class="btn btn-default" type="button" id="go-search-btn">\
								<span class="icon icon-search"></span></button>\
						</span> \
					</div> \
				</form></li>\
			</ul>\
			</li>');
		
		this.bind_quick_search_events();
	},
	
	bind_quick_search_events: function() {
		// render searchable doctype list
		$("#go-doctype-list")
			.empty().add_options(wn.boot.profile.can_search.sort())
			.on("change", function() {
				if(wn.boot.profile.can_create.indexOf($(this).val()) === -1) {
					$("#go-new-btn").attr("disabled", "disabled");
				} else {
					$("#go-new-btn").removeAttr("disabled");
				}
			})
			.trigger("change");
			
		$("#go-search-input").keypress(function(ev){
			if(ev.which==13) { $("#go-search-btn").trigger("click"); }
		});
		
		// new button
		$("#go-new-btn").on("click", function() {
			$("#go-dropdown").removeClass("open");
			new_doc($("#go-doctype-list").val());
		});
		
		// search button
		$("#go-search-btn").on("click", function() {
			var doctype = doctype = $("#go-doctype-list").val(),
				search_string = $("#go-search-input").val();
				
			if(search_string) {
				wn.call({
					type: "GET",
					method: 'webnotes.client.get_value',
					args: {
						doctype: doctype,
						fieldname: "name",
						filters: {name: ["like", "%" + search_string + "%"]}
					},
					callback: function(r) {
						if(!r.exc && r.message && r.message.name) {
							console.log("opening " + doctype + " " + r.message.name);
							$("#go-dropdown").removeClass("open");
							wn.set_route("Form", doctype, r.message.name);
						}
					}
				});
			} else {
				$("#go-dropdown").removeClass("open");
				wn.set_route("List", $("#go-doctype-list").val());
			}
		});
	},
	
	make_file: function() {
		wn.ui.toolbar.new_dialog = new wn.ui.toolbar.NewDialog();
		wn.ui.toolbar.search = new wn.ui.toolbar.Search();
		wn.ui.toolbar.report = new wn.ui.toolbar.Report();
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" href="#"  data-toggle="dropdown"\
				title="'+wn._("File")+'"\
				onclick="return false;">'+wn._("File")+'</a>\
			<ul class="dropdown-menu" id="navbar-file">\
				<li><a href="#" onclick="return wn.ui.toolbar.new_dialog.show();">\
					<i class="icon-plus"></i> '+wn._('New')+'...</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.search.show();">\
					<i class="icon-search"></i> '+wn._('Search')+'...</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.report.show();">\
					<i class="icon-list"></i> '+wn._('Report')+'...</a></li>\
			</ul>\
		</li>');
	},


	// make_actions: function() {
	// 	$('.navbar .nav:first').append('<li class="dropdown">\
	// 		<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
	// 			title="'+wn._("Actions")+'"\
	// 			onclick="return false;">'+wn._("Actions")+'</a>\
	// 		<ul class="dropdown-menu" id="navbar-actions">\
	// 		</ul>\
	// 	</li>');
	// },

	make_tools: function() {
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
				title="'+wn._("Tools")+'"\
				onclick="return false;">Tools</a>\
			<ul class="dropdown-menu" id="toolbar-tools">\
				<li><a href="#" onclick="return wn.ui.toolbar.clear_cache();">'
					+wn._('Clear Cache & Refresh')+'</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.show_about();">'
					+wn._('About')+'</a></li>\
			</ul>\
		</li>');
		
		if(has_common(user_roles,['Administrator','System Manager'])) {
			$('#toolbar-tools').append('<li><a href="#" \
				onclick="return wn.ui.toolbar.download_backup();">'
				+wn._('Download Backup')+'</a></li>');
		}
	},
	set_user_name: function() {
		var fn = user_fullname;
		if(fn.length > 15) fn = fn.substr(0,12) + '...';
		$('#toolbar-user-link').html(fn + '<b class="caret"></b>');
	},

	make_logout: function() {
		// logout
		$('#toolbar-user').append('<li><a href="#" onclick="return wn.app.logout();">'
			+wn._('Logout')+'</a></li>');
	}
});

wn.ui.toolbar.clear_cache = function() {
	localStorage && localStorage.clear();
	$c('webnotes.sessions.clear',{},function(r,rt){ 
		if(!r.exc) {
			show_alert(r.message);
			location.reload();
		}
	});
	return false;
}

wn.ui.toolbar.download_backup = function() {
	msgprint(wn._("Your download is being built, this may take a few moments..."));
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
