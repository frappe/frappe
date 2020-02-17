// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Dashboard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.section = this.frm.fields_dict._form_dashboard.wrapper;
		this.parent = this.section.find('.section-body');
		this.wrapper = $(frappe.render_template('form_dashboard',
			{frm: this.frm})).appendTo(this.parent);

		this.progress_area = this.wrapper.find(".progress-area");
		this.heatmap_area = this.wrapper.find('.form-heatmap');
		this.chart_area = this.wrapper.find('.form-graph');
		this.stats_area = this.wrapper.find('.form-stats');
		this.stats_area_row = this.stats_area.find('.row');
		this.links_area = this.wrapper.find('.form-links');
		this.transactions_area = this.links_area.find('.transactions');

	},
	reset: function() {
		this.section.addClass('hidden');
		this.clear_headline();

		// clear progress
		this.progress_area.empty().addClass('hidden');

		// clear links
		this.links_area.addClass('hidden');
		this.links_area.find('.count, .open-notification').addClass('hidden');

		// clear stats
		this.stats_area.addClass('hidden')
		this.stats_area_row.empty();

		// clear custom
		this.wrapper.find('.custom').remove();
	},
	set_headline: function(html, color) {
		this.frm.layout.show_message(html, color);
	},
	clear_headline: function() {
		this.frm.layout.show_message();
	},

	add_comment: function(text, alert_class, permanent) {
		var me = this;
		this.set_headline_alert(text, alert_class);
		if(!permanent) {
			setTimeout(function() {
				me.clear_headline();
			}, 10000);
		}
	},

	clear_comment: function() {
		this.clear_headline();
	},

	set_headline_alert: function(text, color) {
		if(text) {
			this.set_headline(`<div>${text}</div>`, color);
		} else {
			this.clear_headline();
		}
	},

	add_section: function(html) {
		return $('<div class="form-dashboard-section custom">'+html+'</div>').appendTo(this.wrapper);
	},

	add_progress: function(title, percent, message) {
		var progress_chart = this.make_progress_chart(title);

		if(!$.isArray(percent)) {
			percent = this.format_percent(title, percent);
		}

		var progress = $('<div class="progress"></div>').appendTo(progress_chart);
		$.each(percent, function(i, opts) {
			$(repl('<div class="progress-bar %(progress_class)s" style="width: %(width)s" \
				title="%(title)s"></div>', opts)).appendTo(progress);
		});

		if (!message) message = '';
		$(`<p class="progress-message text-muted small">${message}</p>`).appendTo(progress_chart);

		this.show();

		return progress_chart;
	},

	show_progress: function(title, percent, message) {
		this._progress_map = this._progress_map || {};
		let progress_chart = this._progress_map[title];
		// create a new progress chart if it doesnt exist
		// or the previous one got detached from the DOM
		if (!progress_chart || progress_chart.parent().length == 0) {
			progress_chart = this.add_progress(title, percent, message);
			this._progress_map[title] = progress_chart;
		}

		if (!$.isArray(percent)) {
			percent = this.format_percent(title, percent);
		}
		progress_chart.find('.progress-bar').each((i, progress_bar) => {
			const { progress_class, width } = percent[i];
			$(progress_bar).css('width', width)
				.removeClass('progress-bar-danger progress-bar-success')
				.addClass(progress_class);
		});

		if (!message) message = '';
		progress_chart.find('.progress-message').text(message);
	},

	hide_progress: function(title) {
		if (title){
			this._progress_map[title].remove();
			delete this._progress_map[title];
		} else {
			this._progress_map = {};
			this.progress_area.empty();
		}
	},

	format_percent: function(title, percent) {
		var width = cint(percent) < 1 ? 1 : cint(percent);
		var progress_class = "progress-bar-success";

		return [{
			title: title,
			width: width + '%',
			progress_class: progress_class
		}];
	},
	make_progress_chart: function(title) {
		var progress_chart = $('<div class="progress-chart" title="'+(title || '')+'"></div>')
			.appendTo(this.progress_area.removeClass('hidden'));
		return progress_chart;
	},

	refresh: function() {
		this.reset();
		if(this.frm.doc.__islocal) {
			return;
		}

		if(!this.data) {
			this.init_data();
		}

		var show = false;

		if(this.data && ((this.data.transactions || []).length
			|| (this.data.reports || []).length)) {
			if(this.data.docstatus && this.frm.doc.docstatus !== this.data.docstatus) {
				// limited docstatus
				return;
			}
			this.render_links();
			this.set_open_count();
			show = true;
		}

		if(this.data.heatmap) {
			this.render_heatmap();
			show = true;
		}

		if(this.data.graph) {
			this.setup_graph();
			show = true;
		}

		if(show) {
			this.show();
		}
	},

	after_refresh: function() {
		var me = this;
		// show / hide new buttons (if allowed)
		this.links_area.find('.btn-new').each(function() {
			if(me.frm.can_create($(this).attr('data-doctype'))) {
				$(this).removeClass('hidden');
			}
		});
	},

	init_data: function() {
		this.data = this.frm.meta.__dashboard || {};
		if(!this.data.transactions) this.data.transactions = [];
		if(!this.data.internal_links) this.data.internal_links = {};
		this.filter_permissions();
	},

	add_transactions: function(opts) {
		// add additional data on dashboard
		let group_added = [];

		if(!Array.isArray(opts)) opts=[opts];

		if(!this.data) {
			this.init_data();
		}

		if(this.data && (this.data.transactions || []).length) {
			// check if label already exists, add items to it
			this.data.transactions.map(group => {
				opts.map(d => {
					if(d.label == group.label) {
						group_added.push(d.label);
						group.items.push(...d.items);
					}
				});
			});

			// if label not already present, add new label and items under it
			opts.map(d => {
				if(!group_added.includes(d.label)) {
					this.data.transactions.push(d);
				}
			});

			this.filter_permissions();
		}
	},

	filter_permissions: function() {
		// filter out transactions for which the user
		// does not have permission
		var transactions = [];
		(this.data.transactions || []).forEach(function(group) {
			var items = [];
			group.items.forEach(function(doctype) {
				if(frappe.model.can_read(doctype)) {
					items.push(doctype);
				}
			});

			// only add thie group, if there is atleast
			// one item with permission
			if(items.length) {
				group.items = items;
				transactions.push(group);
			}
		});
		this.data.transactions = transactions;
	},
	render_links: function() {
		var me = this;
		this.links_area.removeClass('hidden');
		this.links_area.find('.btn-new').addClass('hidden');
		if(this.data_rendered) {
			return;
		}

		//this.transactions_area.empty();

		this.data.frm = this.frm;

		$(frappe.render_template('form_links', this.data))
			.appendTo(this.transactions_area)

		if (this.data.reports && this.data.reports.length) {
			$(frappe.render_template('report_links', this.data))
				.appendTo(this.transactions_area)
		}

		// bind links
		this.transactions_area.find(".badge-link").on('click', function() {
			me.open_document_list($(this).parent());
		});

		// bind reports
		this.transactions_area.find(".report-link").on('click', function() {
			me.open_report($(this).parent());
		});

		// bind open notifications
		this.transactions_area.find('.open-notification').on('click', function() {
			me.open_document_list($(this).parent(), true);
		});

		// bind new
		this.transactions_area.find('.btn-new').on('click', function() {
			me.frm.make_new($(this).attr('data-doctype'));
		});

		this.data_rendered = true;
	},
	open_report: function($link) {

		let report = $link.attr('data-report');

		let fieldname = this.data.non_standard_fieldnames
			? (this.data.non_standard_fieldnames[report] || this.data.fieldname)
			: this.data.fieldname;

		frappe.route_options[fieldname] = this.frm.doc.name;
		frappe.set_route("query-report", report);
	},
	open_document_list: function($link, show_open) {
		// show document list with filters
		var doctype = $link.attr('data-doctype'),
			names = $link.attr('data-names') || [];

		if(this.data.internal_links[doctype]) {
			if(names.length) {
				frappe.route_options = {'name': ['in', names]};
			} else {
				return false;
			}
		} else if(this.data.fieldname) {
			frappe.route_options = this.get_document_filter(doctype);
			if(show_open) {
				frappe.ui.notifications.show_open_count_list(doctype);
			}
		}

		frappe.set_route("List", doctype, "List");
	},
	get_document_filter: function(doctype) {
		// return the default filter for the given document
		// like {"customer": frm.doc.name}
		var filter = {};
		var fieldname = this.data.non_standard_fieldnames
			? (this.data.non_standard_fieldnames[doctype] || this.data.fieldname)
			: this.data.fieldname;

		if (this.data.dynamic_links && this.data.dynamic_links[fieldname]) {
			let dynamic_fieldname = this.data.dynamic_links[fieldname][1];
			filter[dynamic_fieldname] = this.data.dynamic_links[fieldname][0];
		}

		filter[fieldname] = this.frm.doc.name;
		return filter;
	},
	set_open_count: function() {
		if(!this.data.transactions || !this.data.fieldname) {
			return;
		}

		// list all items from the transaction list
		var items = [],
			me = this;

		this.data.transactions.forEach(function(group) {
			group.items.forEach(function(item) { items.push(item); });
		});

		var method = this.data.method || 'frappe.desk.notifications.get_open_count';
		frappe.call({
			type: "GET",
			method: method,
			args: {
				doctype: this.frm.doctype,
				name: this.frm.doc.name,
				items: items
			},
			callback: function(r) {
				if(r.message.timeline_data) {
					me.update_heatmap(r.message.timeline_data);
				}

				// update badges
				$.each(r.message.count, function(i, d) {
					me.frm.dashboard.set_badge_count(d.name, cint(d.open_count), cint(d.count));
				});

				// update from internal links
				$.each(me.data.internal_links, (doctype, link) => {
					let names = [];
					if (typeof link === 'string' || link instanceof String) {
						// get internal links in parent document
						let value = me.frm.doc[link];
						if (value && !names.includes(value)) {
							names.push(value);
						}
					} else if (Array.isArray(link)) {
						// get internal links in child documents
						let [table_fieldname, link_fieldname] = link;
						(me.frm.doc[table_fieldname] || []).forEach(d => {
							let value = d[link_fieldname];
							if (value && !names.includes(value)) {
								names.push(value);
							}
						});
					}
					me.frm.dashboard.set_badge_count(doctype, 0, names.length, names);
				});

				me.frm.dashboard_data = r.message;
				me.frm.trigger('dashboard_update');
			}
		});

	},
	set_badge_count: function(doctype, open_count, count, names) {
		var $link = $(this.transactions_area)
			.find('.document-link[data-doctype="'+doctype+'"]');

		if(open_count) {
			$link.find('.open-notification')
				.removeClass('hidden')
				.html((open_count > 99) ? '99+' : open_count);
		}

		if(count) {
			$link.find('.count')
				.removeClass('hidden')
				.html((count > 99) ? '99+' : count);
		}

		if(this.data.internal_links[doctype]) {
			if(names && names.length) {
				$link.attr('data-names', names ? names.join(',') : '');
			} else {
				$link.find('a').attr('disabled', true);
			}
		}
	},

	update_heatmap: function(data) {
		if(this.heatmap) {
			this.heatmap.update({dataPoints: data});
		}
	},

	// heatmap
	render_heatmap: function() {
		if(!this.heatmap) {
			this.heatmap = new frappe.Chart("#heatmap-" + frappe.model.scrub(this.frm.doctype), {
				type: 'heatmap',
				start: new Date(moment().subtract(1, 'year').toDate()),
				count_label: "interactions",
				discreteDomains: 0,
				data: {}
			});

			// center the heatmap
			this.heatmap_area.removeClass('hidden').find('svg').css({'margin': 'auto'});

			// message
			var heatmap_message = this.heatmap_area.find('.heatmap-message');
			if(this.data.heatmap_message) {
				heatmap_message.removeClass('hidden').html(this.data.heatmap_message);
			} else {
				heatmap_message.addClass('hidden');
			}
		}
	},

	add_indicator: function(label, color) {
		this.show();
		this.stats_area.removeClass('hidden');


		// set colspan
		var indicators = this.stats_area_row.find('.indicator-column');
		var n_indicators = indicators.length + 1;
		var colspan;
		if(n_indicators > 4) { colspan = 3 }
		else { colspan = 12 / n_indicators; }

		// reset classes in existing indicators
		if(indicators.length) {
			indicators.removeClass().addClass('col-sm-'+colspan).addClass('indicator-column');
		}

		var indicator = $('<div class="col-sm-'+colspan+' indicator-column"><span class="indicator '+color+'">'
			+label+'</span></div>').appendTo(this.stats_area_row);

		return indicator;
	},

	// graphs
	setup_graph: function() {
		var me = this;
		var method = this.data.graph_method;
		var args = {
			doctype: this.frm.doctype,
			docname: this.frm.doc.name,
		};
		$.extend(args, this.data.graph_method_args);

		frappe.call({
			type: "GET",
			method: method,
			args: args,

			callback: function(r) {
				if(r.message) {
					me.render_graph(r.message);
				}
			}
		});
	},

	render_graph: function(args) {
		var me = this;
		this.chart_area.empty().removeClass('hidden');
		$.extend(args, {
			type: 'line',
			colors: ['green'],
			truncateLegends: 1,
			axisOptions: {
				shortenYAxisNumbers: 1
			}
		});
		this.show();

		this.chart = new frappe.Chart('.form-graph', args);
		if(!this.chart) {
			this.hide();
		}
	},

	show: function() {
		this.section.removeClass('hidden');
	},

	hide: function() {
		this.section.addClass('hidden');
	}
});
