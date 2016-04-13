// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Dashboard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.wrapper = $('<div class="form-dashboard shaded-section"></div>')
		.prependTo(this.frm.layout.wrapper);
		this.body = $('<div class="row"></div>').appendTo(this.wrapper)
			.css("padding", "15px 30px");

	},
	reset: function() {
		this.wrapper.toggle(false);
		this.body.empty();
		this.badge_area = $('<div class="hidden" \
			style="padding-left: 15px; padding-right: 15px;">\
			<p class="text-muted small" style="margin-bottom: 0px;">'
			+ __("Documents related to {0}", [this.frm.doc.name]) +'</p></div>').appendTo(this.body);
		this.clear_headline();
	},
	set_headline: function(html) {
		if(!this.headline)
			this.headline =
				$('<h4 class="form-headline col-md-12 hidden"></h4>').prependTo(this.body);
		this.headline.html(html).removeClass('hidden');
		this.wrapper.toggle(true);
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

	add_progress: function(title, percent) {
		var progress_chart = this.make_progress_chart(title);

		if(!$.isArray(percent)) {
			var width = cint(percent) < 1 ? 1 : percent;
			var progress_class = "";
			if(width < 10)
				progress_class = "progress-bar-danger";
			if(width > 99.9)
				progress_class = "progress-bar-success";

			percent = [{
				title: title,
				width: width,
				progress_class: progress_class
			}];
		}

		var progress = $('<div class="progress"></div>').appendTo(progress_chart);
		$.each(percent, function(i, opts) {
			$(repl('<div class="progress-bar %(progress_class)s" style="width: %(width)s%" \
				title="%(title)s"></div>', opts)).appendTo(progress);
		});

		this.wrapper.toggle(true);
	},
	make_progress_chart: function(title) {
		var progress_area = this.body.find(".progress-area");
		if(!progress_area.length) {
			progress_area = $('<div class="progress-area" style="margin-top: 10px">').appendTo(this.body);
		}
		var progress_chart = $('<div class="progress-chart" title="'+(title || '')+'"></div>')
			.appendTo(progress_area);

		var n_charts = progress_area.find(".progress-chart").length,
			cols = Math.floor(12 / n_charts);

		progress_area.find(".progress-chart")
			.removeClass().addClass("progress-chart col-md-" + cols);

		return progress_chart;
	},
	show_links: function() {
		this.reset();
		if(this.frm.doc.__islocal)
			return;

		if(!this.links) {
			this.links = this.frm.doc.__onload.links;
			this.filter_permissions();
		}
		this.render_links();
		this.set_open_count();

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
			.appendTo(this.badge_area)

		// bind links
		this.badge_area.find(".badge-link").on('click', function() {
			me.open_document_list($(this).attr('data-doctype'));
		});

		// bind open notifications
		this.badge_area.find('.open-notification').on('click', function() {
			me.open_document_list($(this).attr('data-doctype'), true);
		});

		this.wrapper.toggle(true);
		this.badge_area.removeClass('hidden');
	},
	open_document_list: function(doctype, show_open) {
		// show document list with filters
		frappe.route_options = this.get_document_filter();
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
			method: "frappe.desk.notifications.get_open_count",
			args: {
				doctype: this.frm.doc.doctype,
				name: this.frm.doc.name,
			},
			callback: function(r) {
				$.each(r.message, function(i, d) {
					if(d.count) {
						me.frm.dashboard.set_badge_count(d.name, (d.count > 5) ? '5+' : d.count)
					}
				})
			}
		});

	},
	set_badge_count: function(doctype, count) {
		$(this.wrapper)
			.find('.open-notification[data-doctype="'+doctype+'"]')
			.removeClass('hidden')
			.html(count);
	}
});
