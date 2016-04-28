// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Dashboard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.wrapper = $(frappe.render_template('form_dashboard',
			{frm: this.frm})).prependTo(this.frm.layout.wrapper);

		this.headline = this.wrapper.find('.form-headline');
		this.progress_area = this.wrapper.find(".progress-area");
		this.heatmap_area = this.wrapper.find('.form-heatmap');
		this.graph_area = this.wrapper.find('.form-graph');
		this.stats_area = this.wrapper.find('.form-stats');
		this.links_area = this.wrapper.find('.form-links');
		this.transactions_area = this.links_area.find('.transactions');

	},
	reset: function() {
		this.wrapper.addClass('hidden');
		this.clear_headline();

		// clear progress
		this.progress_area.empty().addClass('hidden');

		// clear links
		this.links_area.addClass('hidden');
		this.transactions_area.empty();
		
		//clear graphs
		this.graph_area.empty().addClass('hidden');

		// clear stats
		this.stats_area.empty().addClass('hidden');

		// clear custom
		this.wrapper.find('.custom').remove();
	},
	set_headline: function(html) {
		this.headline.html(html).removeClass('hidden');
		this.show();
	},
	clear_headline: function() {
		if(this.headline) {
			this.headline.empty().addClass('hidden');
		}
	},
	set_headline_alert: function(text, alert_class) {
		if(text) {
			if(!alert_class) alert_class = "alert-warning";
			this.set_headline(repl('<div class="alert %(alert_class)s">%(text)s</div>', {
				"alert_class": alert_class || "",
				"text": text
			}));
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

		if(message) {
			$('<p class="text-muted small">' + message + '</p>').appendTo(this.progress_area);
		}

		this.show();
	},
	format_percent: function(title, percent) {
		var width = cint(percent) < 1 ? 1 : cint(percent);
		var progress_class = "";
		if(width < 10)
			progress_class = "progress-bar-danger";
		if(width > 99.9)
			progress_class = "progress-bar-success";

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

	//
	show_dashboard: function() {
		this.reset();
		if(this.frm.doc.__islocal)
			return;

		if(!this.links) {
			this.links = this.frm.doc.__onload.links;
			this.filter_permissions();
		}
		this.render_links();
		this.set_open_count();
		this.render_heatmap();
	},
	filter_permissions: function() {
		// filter out transactions for which the user
		// does not have permission
		var transactions = [];
		this.links.transactions.forEach(function(group) {
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
		this.links.transactions = transactions;
	},
	render_links: function() {
		var me = this;
		$(frappe.render_template('form_links',
			{transactions: this.links.transactions}))
			.appendTo(this.transactions_area)

		// bind links
		this.transactions_area.find(".badge-link").on('click', function() {
			me.open_document_list($(this).parent().attr('data-doctype'));
		});

		// bind open notifications
		this.transactions_area.find('.open-notification').on('click', function() {
			me.open_document_list($(this).parent().attr('data-doctype'), true);
		});

		this.show();
		this.links_area.removeClass('hidden');
	},
	open_document_list: function(doctype, show_open) {
		// show document list with filters
		frappe.route_options = this.get_document_filter(doctype);
		if(show_open) {
			$.extend(frappe.route_options, frappe.ui.notifications.get_filters(doctype));
		}

		frappe.set_route("List", doctype);
	},
	get_document_filter: function(doctype) {
		// return the default filter for the given document
		// like {"customer": frm.doc.name}
		var filter = {};
		var fieldname = this.links.non_standard_fieldnames
			? (this.links.non_standard_fieldnames[doctype] || this.links.fieldname)
			: this.links.fieldname;
		filter[fieldname] = this.frm.doc.name;
		return filter;
	},
	set_open_count: function() {
		// list all items from the transaction list
		var items = [],
			me = this;

		this.links.transactions.forEach(function(group) {
			group.items.forEach(function(item) { items.push(item); });
		});

		frappe.call({
			type: "GET",
			method: frappe.model.get_server_module_name(this.frm.doctype) + ".get_dashboard_data",
			args: {
				name: this.frm.doc.name,
			},
			callback: function(r) {
				me.heatmap && me.heatmap.update(r.message.timeline_data);
				$.each(r.message.count, function(i, d) {
					me.frm.dashboard.set_badge_count(d.name, cint(d.open_count), cint(d.count));
				});
				me.frm.dashboard_data = r.message;
				me.frm.trigger('dashboard_update');
			}
		});

	},
	set_badge_count: function(doctype, open_count, count) {
		var $link = $(this.transactions_area)
			.find('.document-link[data-doctype="'+doctype+'"]');

		if(open_count) {
			$link.find('.open-notification')
				.removeClass('hidden')
				.html((open_count > 5) ? '5+' : open_count);
		}

		if(count) {
			$link.find('.count')
				.html((count > 9) ? '9+' : count);
		}

	},

	// heatmap
	render_heatmap: function() {
		if(this.show_heatmap && !this.heatmap) {
			this.heatmap = new CalHeatMap();
			this.heatmap.init({
				itemSelector: "#heatmap-" + this.frm.doctype,
				domain: "month",
				subDomain: "day",
				start: moment().subtract(1, 'year').add(1, 'month').toDate(),
				cellSize: 9,
				cellPadding: 2,
				domainGutter: 2,
				range: 12,
				domainLabelFormat: function(date) {
					return moment(date).format("MMM").toUpperCase();
				},
				displayLegend: false,
				legend: [5, 10, 15, 20]
				// subDomainTextFormat: "%d",
			});

			// center the heatmap
			this.heatmap_area.removeClass('hidden').find('svg').css({'margin': 'auto'});

			// message
			var heatmap_message = this.heatmap_area.find('.heatmap-message');
			if(this.heatmap_message) {
				heatmap_message.removeClass('hidden').html(this.heatmap_message);
			} else {
				heatmap_message.addClass('hidden');
			}
 		}
	},

	// stats
	add_stats: function(html) {
		this.stats_area.html(html).removeClass('hidden');
		this.show();
	},
	
	//graphs
	add_graph: function(data) {
		if(!data) data = {};
		var chart = c3.generate({
			bindto: '.form-graph',
		    data: data,
			axis: {
				x: {
					type: 'timeseries',
					tick: {
						format: '%d-%m-%Y'
					}
				},
				y: {
					min: 0,
					padding: {bottom: 10}
				}
			},
			legend: {
				show: false
			},
			padding: {
				right: 30,
				bottom: 30
			}
			
		});

		this.chart = chart;
		this.graph_area.removeClass('hidden');
		this.show();
		this.set_chart_size();		
	},
	
	show: function() {
		this.wrapper.removeClass('hidden');
	},
	
	set_chart_size: function() {
		var width = this.wrapper.width() - 80;
		this.chart.resize({ width: width });
	}
});
