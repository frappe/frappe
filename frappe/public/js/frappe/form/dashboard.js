// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Dashboard = class FormDashboard {
	constructor(opts) {
		$.extend(this, opts);
		this.setup_dashboard_sections();
		this.set_open_count = frappe.utils.throttle(this.set_open_count, 500);
	}

	setup_dashboard_sections() {
		this.progress_area = new Section(this.parent, {
			css_class: 'progress-area',
			hidden: 1,
			collapsible: 1
		});

		this.heatmap_area = new Section(this.parent, {
			title: __("Overview"),
			css_class: 'form-heatmap',
			hidden: 1,
			collapsible: 1,
			body_html: `
				<div id="heatmap-${frappe.model.scrub(this.frm.doctype)}" class="heatmap"></div>
				<div class="text-muted small heatmap-message hidden"></div>
			`
		});

		this.chart_area = new Section(this.parent, {
			title: __("Graph"),
			css_class: 'form-graph',
			hidden: 1,
			collapsible: 1
		});

		this.stats_area_row = $(`<div class="row"></div>`);
		this.stats_area = new Section(this.parent, {
			title: __("Stats"),
			css_class: 'form-stats',
			hidden: 1,
			collapsible: 1,
			body_html: this.stats_area_row
		});

		this.transactions_area = $(`<div class="transactions"></div`);
		this.links_area = new Section(this.parent, {
			title: __("Connections"),
			css_class: 'form-links',
			hidden: 1,
			collapsible: 1,
			body_html: this.transactions_area
		});


	}

	reset() {
		this.hide();

		// clear progress
		this.progress_area.body.empty();
		this.progress_area.hide();

		// clear links
		this.links_area.body.find('.count, .open-notification').addClass('hidden');
		this.links_area.hide();

		// clear stats
		this.stats_area_row.empty();
		this.stats_area.hide();

		// clear custom
		this.parent.find('.custom').remove();
		this.hide();
	}

	add_section(body_html, title=null, css_class="custom", hidden=false) {
		let options = {
			title,
			css_class,
			hidden,
			body_html,
			make_card: true,
			collapsible: 1
		};
		return new Section(this.parent, options).body;
	}

	add_progress(title, percent, message) {
		let progress_chart = this.make_progress_chart(title);

		if (!$.isArray(percent)) {
			percent = this.format_percent(title, percent);
		}

		let progress = $('<div class="progress"></div>').appendTo(progress_chart);

		$.each(percent, function(i, opts) {
			$(`<div class="progress-bar ${opts.progress_class}" style="width: ${opts.width}" title="${opts.title}"></div>`).appendTo(progress);
		});

		if (!message) message = '';
		$(`<p class="progress-message text-muted small">${message}</p>`).appendTo(progress_chart);

		this.show();

		return progress_chart;
	}

	show_progress(title, percent, message) {
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
	}

	hide_progress(title) {
		if (title) {
			this._progress_map[title].remove();
			delete this._progress_map[title];
		} else {
			this._progress_map = {};
			this.progress_area.hide();
		}
	}

	format_percent(title, percent) {
		const percentage = cint(percent);
		const width = percentage < 0 ? 100 : percentage;
		const progress_class = percentage < 0 ? "progress-bar-danger" : "progress-bar-success";

		return [{
			title: title,
			width: width + '%',
			progress_class: progress_class
		}];
	}

	make_progress_chart(title) {
		this.progress_area.show();
		var progress_chart = $('<div class="progress-chart" title="'+(title || '')+'"></div>')
			.appendTo(this.progress_area.body);
		return progress_chart;
	}

	refresh() {
		this.reset();
		if (this.frm.doc.__islocal || !frappe.boot.desk_settings.dashboard) {
			return;
		}

		if (!this.data) {
			this.init_data();
		}

		var show = false;

		if (this.data && ((this.data.transactions || []).length
			|| (this.data.reports || []).length)) {
			if (this.data.docstatus && this.frm.doc.docstatus !== this.data.docstatus) {
				// limited docstatus
				return;
			}
			this.render_links();
			this.set_open_count();
			show = true;
		}

		if (this.data.heatmap) {
			this.render_heatmap();
			show = true;
		}

		if (this.data.graph) {
			this.setup_graph();
			// show = true;
		}

		if (show) {
			this.show();
		}
	}

	after_refresh() {
		var me = this;
		// show / hide new buttons (if allowed)
		this.links_area.body.find('.btn-new').each(function() {
			if (me.frm.can_create($(this).attr('data-doctype'))) {
				$(this).removeClass('hidden');
			}
		});
	}

	init_data() {
		this.data = this.frm.meta.__dashboard || {};
		if (!this.data.transactions) this.data.transactions = [];
		if (!this.data.internal_links) this.data.internal_links = {};
		this.filter_permissions();
	}

	add_transactions(opts) {
		// add additional data on dashboard
		let group_added = [];

		if (!Array.isArray(opts)) opts=[opts];

		if (!this.data) {
			this.init_data();
		}

		if (this.data && (this.data.transactions || []).length) {
			// check if label already exists, add items to it
			this.data.transactions.map(group => {
				opts.map(d => {
					if (d.label == group.label) {
						group_added.push(d.label);
						group.items.push(...d.items);
					}
				});
			});

			// if label not already present, add new label and items under it
			opts.map(d => {
				if (!group_added.includes(d.label)) {
					this.data.transactions.push(d);
				}
			});

			this.filter_permissions();
		}
	}

	filter_permissions() {
		// filter out transactions for which the user
		// does not have permission
		let transactions = [];
		(this.data.transactions || []).forEach(function(group) {
			let items = [];
			group.items.forEach(function(doctype) {
				if (frappe.model.can_read(doctype)) {
					items.push(doctype);
				}
			});

			// only add this group, if there is at-least
			// one item with permission
			if (items.length) {
				group.items = items;
				transactions.push(group);
			}
		});
		this.data.transactions = transactions;
	}

	render_links() {
		var me = this;
		this.links_area.show();
		this.links_area.body.find('.btn-new').addClass('hidden');
		if (this.data_rendered) {
			return;
		}

		this.data.frm = this.frm;

		let transactions_area_body = this.transactions_area;

		$(frappe.render_template('form_links', this.data))
			.appendTo(transactions_area_body);

		if (this.data.reports && this.data.reports.length) {
			$(frappe.render_template('report_links', this.data))
				.appendTo(transactions_area_body);
		}

		// bind links
		transactions_area_body.find(".badge-link").on('click', function() {
			me.open_document_list($(this).closest('.document-link'));
		});

		// bind reports
		transactions_area_body.find(".report-link").on('click', function() {
			me.open_report($(this).parent());
		});

		// bind open notifications
		transactions_area_body.find('.open-notification').on('click', function() {
			me.open_document_list($(this).parent(), true);
		});

		// bind new
		transactions_area_body.find('.btn-new').on('click', function() {
			me.frm.make_new($(this).attr('data-doctype'));
		});

		this.data_rendered = true;
	}

	open_report($link) {
		let report = $link.attr('data-report');

		let fieldname = this.data.non_standard_fieldnames
			? (this.data.non_standard_fieldnames[report] || this.data.fieldname)
			: this.data.fieldname;

		frappe.route_options[fieldname] = this.frm.doc.name;
		frappe.set_route("query-report", report);
	}

	open_document_list($link, show_open) {
		// show document list with filters
		var doctype = $link.attr('data-doctype'),
			names = $link.attr('data-names') || [];

		if (this.data.internal_links[doctype]) {
			if (names.length) {
				frappe.route_options = {'name': ['in', names]};
			} else {
				return false;
			}
		} else if (this.data.fieldname) {
			frappe.route_options = this.get_document_filter(doctype);
			if (show_open && frappe.ui.notifications) {
				frappe.ui.notifications.show_open_count_list(doctype);
			}
		}

		frappe.set_route("List", doctype, "List");
	}

	get_document_filter(doctype) {
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
	}

	set_open_count() {
		if (!this.data.transactions || !this.data.fieldname) {
			return;
		}

		// list all items from the transaction list
		var items = [],
			me = this;

		this.data.transactions.forEach(function(group) {
			group.items.forEach(function(item) {
				items.push(item);
			});
		});

		var method = this.data.method || 'frappe.desk.notifications.get_open_count';
		frappe.call({
			type: "GET",
			method: method,
			args: {
				doctype: this.frm.doctype,
				name: this.frm.docname,
				items: items
			},
			callback: function(r) {
				if (r.message.timeline_data) {
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

	}

	set_badge_count(doctype, open_count, count, names) {
		var $link = $(this.transactions_area)
			.find('.document-link[data-doctype="'+doctype+'"]');

		if (open_count) {
			$link.find('.open-notification')
				.removeClass('hidden')
				.html((open_count > 99) ? '99+' : open_count);
		}

		if (count) {
			$link.find('.count')
				.removeClass('hidden')
				.text((count > 99) ? '99+' : count);
		}

		if (this.data.internal_links[doctype]) {
			if (names && names.length) {
				$link.attr('data-names', names ? names.join(',') : '');
			} else {
				$link.find('a').attr('disabled', true);
			}
		}
	}

	update_heatmap(data) {
		if (this.heatmap) {
			this.heatmap.update({dataPoints: data});
		}
	}

	// heatmap
	render_heatmap() {
		if (!this.heatmap) {
			this.heatmap = new frappe.Chart("#heatmap-" + frappe.model.scrub(this.frm.doctype), {
				type: 'heatmap',
				start: new Date(moment().subtract(1, 'year').toDate()),
				count_label: "interactions",
				discreteDomains: 1,
				radius: 3,
				data: {},
			});

			// center the heatmap
			this.heatmap_area.show();
			this.heatmap_area.body.find('svg').css({'margin': 'auto'});

			// message
			var heatmap_message = this.heatmap_area.body.find('.heatmap-message');
			if (this.data.heatmap_message) {
				heatmap_message.removeClass('hidden').html(this.data.heatmap_message);
			} else {
				heatmap_message.addClass('hidden');
			}
		}
	}

	add_indicator(label, color) {
		this.show();
		this.stats_area.show();


		// set colspan
		var indicators = this.stats_area_row.find('.indicator-column');
		var n_indicators = indicators.length + 1;
		var colspan;
		if (n_indicators > 4) {
			colspan = 3;
		} else {
			colspan = 12 / n_indicators;
		}

		// reset classes in existing indicators
		if (indicators.length) {
			indicators.removeClass().addClass('col-sm-'+colspan).addClass('indicator-column');
		}

		var indicator = $('<div class="col-sm-'+colspan+' indicator-column"><span class="indicator '+color+'">'
			+label+'</span></div>').appendTo(this.stats_area_row);

		return indicator;
	}

	// graphs
	setup_graph() {
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
				if (r.message) {
					me.render_graph(r.message);
					me.show();
				} else {
					me.hide();
				}
			}
		});
	}

	render_graph(args) {
		this.chart_area.show();
		this.chart_area.body.empty();
		$.extend({
			type: 'line',
			colors: ['green'],
			truncateLegends: 1,
			axisOptions: {
				shortenYAxisNumbers: 1
			}
		}, args);
		this.show();

		this.chart = new frappe.Chart('.form-graph', args);
		if (!this.chart) {
			this.hide();
		}
	}

	show() {
		this.toggle_visibility(true);
	}

	hide() {
		this.toggle_visibility(false);
	}

	toggle_visibility(show) {
		this.parent.toggleClass('visible-section', show);
		this.parent.toggleClass('empty-section', !show);
	}

	// TODO: Review! code related to headline should be the part of layout/form
	set_headline(html, color) {
		this.frm.layout.show_message(html, color);
	}

	clear_headline() {
		this.frm.layout.show_message();
	}

	add_comment(text, alert_class, permanent) {
		var me = this;
		this.set_headline_alert(text, alert_class);
		if (!permanent) {
			setTimeout(function() {
				me.clear_headline();
			}, 10000);
		}
	}

	clear_comment() {
		this.clear_headline();
	}

	set_headline_alert(text, color) {
		if (text) {
			this.set_headline(`<div>${text}</div>`, color);
		} else {
			this.clear_headline();
		}
	}
};

class Section {
	constructor(parent, options) {
		this.parent = parent;
		this.df = options || {};
		this.make();

		if (this.df.title && this.df.collapsible && localStorage.getItem(options.css_class + '-closed')) {
			this.collapse();
		}
		this.refresh();
	}

	make() {
		this.wrapper = $(`<div class="form-dashboard-section ${ this.df.make_card ? "card-section" : "" }">`)
			.appendTo(this.parent);

		if (this.df) {
			if (this.df.title) {
				this.make_head();
			}
			if (this.df.description) {
				this.description_wrapper = $(
					`<div class="col-sm-12 form-section-description">
						${__(this.df.description)}
					</div>`
				);

				this.wrapper.append(this.description_wrapper);
			}
			if (this.df.css_class) {
				this.wrapper.addClass(this.df.css_class);
			}
			if (this.df.hide_border) {
				this.wrapper.toggleClass("hide-border", true);
			}
		}

		this.body = $('<div class="section-body">').appendTo(this.wrapper);

		if (this.df.body_html) {
			this.body.append(this.df.body_html);
		}
	}

	make_head() {
		this.head = $(`
			<div class="section-head">
				${__(this.df.title)}
				<span class="ml-2 collapse-indicator mb-1"></span>
			</div>
		`);

		this.head.appendTo(this.wrapper);
		this.indicator = this.head.find('.collapse-indicator');
		this.indicator.hide();

		if (this.df.collapsible) {
			// show / hide based on status
			this.collapse_link = this.head.on("click", () => {
				this.collapse();
			});
			this.set_icon();
			this.indicator.show();
		}
	}

	refresh() {
		if (!this.df) return;

		// hide if explicitly hidden
		let hide = this.df.hidden;
		this.wrapper.toggle(!hide);
	}

	collapse(hide) {
		if (hide === undefined) {
			hide = !this.body.hasClass("hide");
		}

		this.body.toggleClass("hide", hide);
		this.head && this.head.toggleClass("collapsed", hide);

		this.set_icon(hide);

		// save state for next reload ('' is falsy)
		localStorage.setItem(this.df.css_class + '-closed', hide ? '1' : '');
	}

	set_icon(hide) {
		let indicator_icon = hide ? 'down' : 'up-line';
		this.indicator && this.indicator.html(frappe.utils.icon(indicator_icon, 'sm', 'mb-1'));
	}

	is_collapsed() {
		return this.body.hasClass('hide');
	}

	hide() {
		this.wrapper.hide();
	}

	show() {
		this.wrapper.show();
	}
}
