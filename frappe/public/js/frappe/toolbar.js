// Copyright (c) 2015, Frappe Technologies Pvt. Ltd.
// For license information, please see license.txt

$(document).on("toolbar_setup", function() {
	var help_links = [];
	var support_link = "#upgrade";
	var chat_link = "#upgrade";
	frappe_limits = frappe.boot.frappe_limits

	if(frappe.boot.expiry_message) {
		frappe.msgprint(frappe.boot.expiry_message)
	}

	if(frappe_limits.support_email || frappe_limits.support_chat) {
		help_links.push('<li class="divider"></li>');
	}

	if(frappe_limits.support_email) {
		support_link = 'mailto:'+frappe.boot.frappe_limits.support_email;
		help_links.push('<li><a href="'+support_link+'">' + frappe._('Email Support') + '</a></li>');
	}	

	if(frappe_limits.support_chat) {
		chat_link = frappe_limits.support_chat;
		help_links.push('<li><a href="'+chat_link+'" target="_blank">' + frappe._('Chat Support') + '</a></li>');
	}


	$(help_links.join("\n")).insertBefore($("#toolbar-user").find(".divider:last"));

	if(frappe_limits.space_limit || frappe_limits.user_limit || frappe_limits.expiry || frappe_limits.email_limit)
	{		
	help_links = [];
	help_links.push('<li><a href="#usage-info">' + frappe._('Usage Info') + '</a></li>');
	help_links.push('<li class="divider"></li>');
	}

	$(help_links.join("\n")).insertBefore($("#toolbar-user").find("li:first"));
});

frappe.get_form_sidebar_extension = function() {
	var fs = frappe.boot.frappe_limits;
	if(!fs.sidebar_usage_html) {
		fs.total_used = flt(fs.database_size + fs.backup_size + fs.files_size);
		fs.total_used_percent = cint(fs.total_used / flt(fs.max_space * 1024) * 100);

		var template = '<ul class="list-unstyled sidebar-menu">\
			<li class="usage-stats">\
		        <a href="#usage-info" class="text-muted">{{ fs.total_used }}MB ({{ fs.total_used_percent }}%) used</a></li>\
		</ul>';
		fs.sidebar_usage_html = frappe.render(template, {fs:fs}, "form_sidebar_usage");
	}

	return fs.sidebar_usage_html;
}
