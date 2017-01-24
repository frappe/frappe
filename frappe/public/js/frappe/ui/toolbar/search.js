frappe.provide('frappe.search');

frappe.search.UnifiedSearch = Class.extend({

	setup: function() {
		var me = this;
		var d = new frappe.ui.Dialog();

		$(frappe.render_template("search")).appendTo($(d.body));
		$(d.header).html($(frappe.render_template("search_header")));

		this.search_dialog = d;
		this.search_modal = $(d.$wrapper);
		this.search_modal.addClass('search-dialog');

		this.input = this.search_modal.find(".search-input");
		this.sidebar = this.search_modal.find(".search-sidebar");
		this.results_area = this.search_modal.find(".result-area .module-body");
	},

	setup_search: function(keywords, search_objects) {
		var me = this;
		this.search_objects = search_objects;
		this.reset(keywords);
		this.input.val(keywords);
		this.input.on("input", function() {
			var $this = $(this);
			clearTimeout($this.data('timeout'));

			$this.data('timeout', setTimeout(function(){
				var keywords = me.input.val();
				me.sidebar.empty();
				me.results_area.empty();
				if(keywords.length > 0) {
					me.reset(keywords);
					me.build_results(keywords);
				}
			}, 250));
		});
		this.build_results(keywords);
		setTimeout(function() { me.input.select(); }, 500);
	},

	reset: function(keywords) {
		this.sidebar.empty();
		this.results_area.empty();
		var input = this.input.val();
		if(input.length > 0) {
			this.results_area.html('<p class="result-status text-muted">'+
			'No results found for: '+ "'"+ keywords +"'" +'</p>');
		}
	},

	build_results: function(keywords) {
		var me = this;
		this.sidebar.empty();
		this.results_area.empty();
		this.count = 1;
		this.search_objects.forEach(function(search_object) {
			search_object.build_results_object(me, keywords);
			
		});
	},

	show_results: function(results_obj, search_obj) {
		if(results_obj) {
			this.render_results(results_obj);
			this.bind_events(results_obj, search_obj);
		}
	},

	render_results: function(results_obj){
		var me = this;
		this.sidebar.append(results_obj.sidelist);
		results_obj.sections.forEach(function(section) {
			me.results_area.append(section);
		});
	},

	bind_events: function(results_obj, search_obj) {
		var me = this;
		this.sidebar.find('.list-link').on('click', function() {
			me.sidebar.find(".list-link a").removeClass("disabled");
			$(this).find('a').addClass("disabled");
			var type = $(this).attr('data-category');

			console.log("doclist defined?", results_obj.lists[type]);
			me.results_area.empty().html(results_obj.lists[type]);

			search_obj.start[type] = search_obj.more_length;
			var more_button = me.results_area.find('.list-more');
			more_button.on('click', function() {
				var more_data = search_obj.get_more_results(type);
				var more_results = more_data[0];
				var more = more_data[1];
				me.results_area.find('.list-more').before(more_results);

				if(!more) {
					me.results_area.find('.list-more').hide();
				}
			});

			return false;
		});
		this.results_area.find('.section-more').on('click', function() {
			var type = $(this).attr('data-category');
			me.sidebar.find('*[data-category="'+ type +'"]').trigger("click");
		});

		// If there's only one link in sidebar, show its full list
		if(this.sidebar.find('.list-link').length === 1) {
			this.sidebar.find('.list-link').trigger("click");
		}
	},

	add_more_results: function(more_data) {
		var more_results = more_data[0];
		var more = more_data[1];
		this.results_area.find('.list-more').before(more_results);
		if(!more) {
			this.results_area.find('.list-more').hide();
		}
	}

});

frappe.search.Search = Class.extend({

	setup: function() {
		this.search_type = '';
		this.types = [];
		this.sections = [];
		this.lists = {};
		this.more_length = 5;
		this.start = {};
		this.section_length = 3;
		this.set_types();
	},

	set_types: function() {
		var me = this;
		this.search_type = 'Global Search';
		frappe.call({
			method: "frappe.utils.global_search.get_doctypes",
			args: {},
			callback: function(r) {
				if(r.message) {
					r.message.forEach(function(d) {
						me.types.push(d.doctype);
						me.start[d.doctype] = 0;
					});
					me.sidelist = me.make_sidelist();
					me.get_results();
				}
			}
		});
	}, 

	get_results: function() {
		var me = this;
		this.types.forEach(function(type) {
			me.get_result_set(type);
		});
	},

	get_result_set: function(doctype){
		var me = this;
		var more = true;
		var keywords = this.keywords;
		var start = this.start[doctype];
		var limit = this.more_length;
		var last_type = (doctype == this.types.slice(-1));
		frappe.call({
			method: "frappe.utils.global_search.search_in_doctype",
			args: { 
				doctype: doctype, 
				text: keywords, 
				start: 0, 
				limit: 20,
			},
			callback: function(r) {
				if(r.message) {
					me.make_type_results(doctype, r.message, more);
					if(last_type) {
						me.show_results();
					}
				} 
			}
		});
	},

	get_more_results: function(doctype) {
		var me = this;
		var more = true;
		frappe.call({
			method: "frappe.utils.global_search.search_in_doctype",
			args: { 
				doctype: doctype, 
				text: keywords, 
				start: 0, 
				limit: 20,
			},
			callback: function(r) {
				if(r.message) {
					me.make_more_list(doctype, r.message, more);
				} 
			}
		});
	},

	make_type_results: function(type, results, more) {
		var me = this;
		if(results.length > 0) {
			this.sections.push(this.make_section(type, results));
			this.lists[type] = this.make_full_list(type, results, more);
		}
	},
	
	build_results_object: function(r, keywords) {
		console.log("this setup called");
		this.render_object = r;
		this.keywords = keywords;
		this.setup();
		console.log("this setup done");
	},

	show_results: function() {
		var me = this;
		if(this.sections.length > 0) {
			console.log(me.search_type);
			console.log(me.lists);
			this.render_object.show_results({
				sidelist: me.sidelist,
				sections: me.sections,
				lists: me.lists
			}, me);
		}
	},

	make_result_item: function(type, result) {
		var link_html = '<div class="result '+ type +'-result">' +
			'<a href="{0}" class="module-section-link small">{1}</a>' +
			'<p class="small">{2}</p>' +
			'</div>';
		var formatted_result = this.format_result(result);
		return $(__(link_html, formatted_result));
	},

	format_result: function(result) {
		var route = '#Form/' + result.doctype + '/' + result.name;
		return [route, result.name, this.get_finds(result.content)]
	},
	
	get_finds: function(searchables) {
		var me = this;
		parts = searchables.split("|||");
		content = "";
		parts.forEach(function(part) {
			if(part.toLowerCase().indexOf(me.keywords) !== -1) {
				content += part;
			}
		});
		return content;
	},

	make_section: function(type, results) {
		var me = this;
		var results_module = $('<div class="row module-section '+type+'-section">'+
			'<div class="col-sm-12 module-section-column">' +
			'<div class="h4 section-head">'+type+'</div>' +
			'<div class="section-body"></div>'+
			'</div></div>');
		var results_col = results_module.find('.module-section-column');
		results.slice(0, this.section_length).forEach(function(result) {
			results_col.append(me.make_result_item(type, result));
		});
		if(results.length > this.section_length) {
			results_col.append('<a class="small section-more" data-category="' + type + '">More...</a>');
		}
		return results_module;
	},

	make_full_list: function(type, results, more) {
		var me = this;
		var results_module = $('<div class="row module-section '+type+'-section">'+
			'<div class="col-sm-12 module-section-column">' +
			'<div class="h4 section-head">'+type+'</div>' +
			'<div class="section-body"></div>'+
			'</div></div>');
		var results_col = results_module.find('.module-section-column');
		results.forEach(function(result) {
			results_col.append(me.make_result_item(type, result));
		});
		if(more) {
			results_col.append('<a class="small list-more" data-category="' + type + '">More...</a>');
		}
		return results_module;
	},

	make_more_list: function(type, results, more) {
		var me = this;
		if(results.length < this.more_length) { more = false; }

		var more_results = $('<div></div>');
		results.forEach(function(result) {
			more_results.append(me.make_result_item(type, result));
		});
		return [more_results, more];
	},

	make_sidelist: function() {
		var me = this;
		var sidelist = $('<ul class="list-unstyled sidebar-menu nav-list"></ul>');
		sidelist.append('<li class="h6">'+ me.search_type +'</li>');
		this.types.forEach(function(type) {
			sidelist.append(me.make_sidelist_item(type));
		});
		sidelist.append('<li class="divider"></li>');
		return sidelist;
	},

	make_sidelist_item: function(type) {
		var sidelist_item = '<li class="list-link"' + 
			'data-category="{0}"><a href="#">{0}</a></li>';
		return $(__(sidelist_item, [type]));
	},

});

frappe.search.NavSearch = frappe.search.Search.extend({
	set_types: function() {
		var me = this;
		var keywords = this.keywords;
		this.search_type = 'Navigation';
		this.awesome_bar = new frappe.search.AwesomeBar();
		this.nav_results = {
			"Lists": me.awesome_bar.get_doctypes(keywords),
			"Reports": me.awesome_bar.get_reports(keywords),
			"Pages": me.awesome_bar.get_pages(keywords),
			"Modules": me.awesome_bar.get_modules(keywords)
		}
		var types = ["Lists", "Reports", "Pages", "Modules"];
		types.forEach(function(type) {
			if(me.nav_results[type].length > 0) {
				me.types.push(type);
				me.start[type] = 0;
			}
		});
		if(this.types.length > 0) {
			this.sidelist = this.make_sidelist();
			this.get_results();
		}
	}, 
	get_result_set: function(type) {
		var last_type = (type == this.types.slice(-1));

		var results = this.nav_results[type].slice(this.start[type], this.more_length);
		this.start[type] += this.more_length;
		var more = true;
		if(results.slice(-1)[0] === this.nav_results[type].slice(-1)[0]) {
			more = false;
		}
		this.make_type_results(type, results, more);
		if(last_type) {
			this.show_results();
		}
	},

	get_more_results: function(type) {	
		var results = this.nav_results[type].slice(this.start[type], this.start[type]+this.more_length);
		this.start[type] += this.more_length;
		var more = true;
		if(results.slice(-1)[0] === this.nav_results[type].slice(-1)[0]) {
			more = false;
		}
		return this.make_more_list(type, results, more)
	},

	make_result_item: function(type, result) {
		var link_html = '<div class="result '+ type +'-result">' +
			'<a href="{0}" class="module-section-link small">{1}</a>' +
			'<p class="small">{2}</p>' +
			'</div>';
		var formatted_result = this.format_result(result);
		return $(__(link_html, formatted_result));
	},

	format_result: function(result) {
		return [this.make_path(result.route), result.label, ""];
	},

	make_path: function(route) {
		var path = "#";
		route.forEach(function(r) { path += r + '/'; });
		if(path === '#'){ return path }
		return path.slice(0, -1);
	},
	// Render OnClicks!!!

	// make_condensed_section: function() {
	// 	this.section_length = 6;

	// }
});

frappe.search.HelpSearch = frappe.search.Search.extend({
	set_types: function() {
		this.search_type = 'Help';
		this.types = ['Help'];
		this.sidelist = this.make_sidelist();
		this.get_results();
	}, 

	get_result_set: function(type, start) {
		var me = this;
		var keywords = this.keywords;
		frappe.call({
			method: "frappe.utils.help.get_help",
			args: {
				text: keywords
			},
			callback: function(r) {
				if(r.message) {
					me.make_type_results(type, r.message, false);
					me.show_results();
				} 
			}
		});
	},

	make_result_item: function(type, result) {
		var link_html = '<div class="result '+ type +'-result">' +
			'<a href="{0}" class="module-section-link small">{1}</a>' +
			'<p class="small">{2}</p>' +
			'</div>';
		var formatted_result = this.format_result(result);
		return $(__(link_html, formatted_result));
	},

	format_result: function(result) {
		var route = '#" data-path="' + result[2];
		return [route, result[0], result[1]]
	},

	// show results modal
	show_article: function() {
		var path = $(this).attr("data-path");
		if(path) {
			e.preventDefault();
			frappe.call({
				method: "frappe.utils.help.get_help_content",
				args: {
					path: path
				},
				callback: function (r) {
					if(r.message && r.message.title) {
						$result_modal.find('.modal-title').html("<span>"
							+ r.message.title + "</span>");
						$result_modal.find('.modal-body').html(r.message.content);
						$result_modal.modal('show');
					}
				}
			});
		}
	}
});
