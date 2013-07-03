wn.ui.form.Dashboard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.wrapper = $('<div class="row form-dashboard">')
			.prependTo(this.frm.layout.wrapper);
		
	},
	reset: function(doc) {
		this.wrapper.empty().toggle(doc.__islocal ? false : true);
		this.headline = null;
	},
	set_headline: function(html) {
		if(!this.headline)
			this.headline = 
				$('<div class="form-headline col col-lg-12">').prependTo(this.wrapper);
		this.headline.html(html);
	},
	set_headline_alert: function(text, alert_class, icon) {
		this.set_headline(repl('<div class="alert %(alert_class)s">%(icon)s%(text)s</div>', {
			"alert_class": alert_class || "",
			"icon": icon ? '<i class="'+icon+'" /> ' : "",
			"text": text 
		}));
	},
	add_doctype_badge: function(doctype, fieldname) {
		if(wn.model.can_read(doctype)) {
			this.add_badge(wn._(doctype), function() {
				wn.route_options = {};
				wn.route_options[fieldname] = cur_frm.doc.name;
				wn.set_route("List", doctype);
			}).attr("data-doctype", doctype);
		}
	},
	add_badge: function(label, onclick) {
		var badge = $(repl('<div class="col col-lg-4">\
			<div class="alert alert-badge">\
				<a class="badge-link">%(label)s</a>\
				<span class="badge pull-right">-</span>\
			</div></div>', {label:label}))
				.appendTo(this.wrapper)
				
		badge.find(".badge-link").click(onclick);
				
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
	
})