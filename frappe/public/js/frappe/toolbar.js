// Copyright (c) 2015, Frappe Technologies Pvt. Ltd.
// For license information, please see license.txt

$(document).on("toolbar_setup", function() {
	var help_links = [];
	var limits = frappe.boot.limits;

	if(frappe.boot.expiry_message) {
		var expiry_message_shown = localStorage.expiry_message_shown;

		// if message is more than a day old, show message again
		if (!(expiry_message_shown
				&& (new Date() - new Date(expiry_message_shown) < 86400000))) {

			localStorage.expiry_message_shown = new Date();
			frappe.msgprint(frappe.boot.expiry_message);
		}
	}

	if(limits.support_email || limits.support_chat) {
		help_links.push('<li class="divider"></li>');
	}

	if(limits.support_email) {
		var support_link = 'mailto:'+frappe.boot.limits.support_email;
		help_links.push('<li><a href="'+support_link+'">' + frappe._('Email Support') + '</a></li>');
	}

	if(limits.support_chat) {
		help_links.push('<li><a href="'+limits.support_chat+'" target="_blank">' + frappe._('Chat Support') + '</a></li>');
	}

	$(help_links.join("\n")).insertBefore($("#toolbar-user").find(".divider:last"));

	if(limits.space || limits.users || limits.expiry || limits.emails) {
		help_links = [];
		help_links.push('<li><a href="#usage-info">' + frappe._('Usage Info') + '</a></li>');
		help_links.push('<li class="divider"></li>');
		$(help_links.join("\n")).insertBefore($("#toolbar-user").find("li:first"));
	}

});

frappe.get_form_sidebar_extension = function() {
	var limits = frappe.boot.limits;
	var usage = limits.space_usage;
	if (!usage) {
		return '';
	}

	if(!usage.sidebar_usage_html) {
		if (limits.space) {
			usage.total_used_percent = cint(usage.total / flt(limits.space * 1024) * 100);

			var template = '<ul class="list-unstyled sidebar-menu">\
				<li class="usage-stats">\
					<a href="#usage-info" class="text-muted">{{ usage.total }}MB ({{ usage.total_used_percent }}%) used</a></li>\
				</ul>';
			usage.sidebar_usage_html = frappe.render(template, { 'usage': usage }, "form_sidebar_usage");

		} else {
			usage.sidebar_usage_html = '';
		}
	}

	return usage.sidebar_usage_html;
}
