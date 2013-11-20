// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.ui.form.Dashboard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.wrapper = $('<div class="form-dashboard row"></div>')
			.css({"margin-bottom":"20px", "padding-bottom":"10px"})
			.prependTo(this.frm.layout.wrapper);
		this.body = $('<div></div>').appendTo(this.wrapper).css("margin-bottom", "20px");
		
	},
	reset: function() {
		this.wrapper.toggle(false);
		this.body.empty();
		this.headline = null;
	},
	set_headline: function(html) {
		if(!this.headline)
			this.headline = 
				$('<div class="form-headline col-md-12">').prependTo(this.body);
		this.headline.html(html);
		this.wrapper.toggle(true);
	},
	set_headline_alert: function(text, alert_class, icon) {
		this.set_headline(repl('<div class="alert %(alert_class)s">%(icon)s%(text)s</div>', {
			"alert_class": alert_class || "alert-info",
			"icon": icon ? '<i class="'+icon+'" /> ' : "",
			"text": text 
		}));
	},
	add_doctype_badge: function(doctype, fieldname) {
		if(wn.model.can_read(doctype)) {
			this.add_badge(wn._(doctype), doctype, function() {
				wn.route_options = {};
				wn.route_options[fieldname] = cur_frm.doc.name;
				wn.set_route("List", doctype);
			}).attr("data-doctype", doctype);
		}
	},
	add_badge: function(label, doctype, onclick) {
		var badge = $(repl('<div class="col-md-4">\
			<div class="alert alert-info alert-badge">\
				<i class="icon-fixed-width %(icon)s"></i> \
				<a class="badge-link">%(label)s</a>\
				<span class="badge pull-right">-</span>\
			</div></div>', {label:label, icon: wn.boot.doctype_icons[doctype]}))
				.appendTo(this.body)
				
		badge.find(".badge-link").click(onclick);
		this.wrapper.toggle(true);
				
		return badge.find(".alert-badge");
	},
	set_badge_count: function(data) {
		var me = this;
		$.each(data, function(doctype, count) {
			$(me.wrapper)
				.find(".alert-badge[data-doctype='"+doctype+"'] .badge")
				.html(cint(count));
		});
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
			progress_area = $('<div class="progress-area">').appendTo(this.body);
		}
		var progress_chart = $('<div class="progress-chart"><h5>'+title+'</h5></div>')
			.appendTo(progress_area);
		
		var n_charts = progress_area.find(".progress-chart").length,
			cols = Math.floor(12 / n_charts);
	
		progress_area.find(".progress-chart")
			.removeClass().addClass("progress-chart col-md-" + cols);
		
		return progress_chart;
	}
});