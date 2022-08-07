frappe.provide("frappe.ui.misc");
frappe.ui.misc.about = function () {
	if (!frappe.ui.misc.about_dialog) {
		var d = new frappe.ui.Dialog({ title: __("Frappe Framework") });

		$(d.body).html(
			repl(
				"<div>\
		<p>" +
					__("Open Source Applications for the Web") +
					"</p>  \
		<p><i class='fa fa-globe fa-fw'></i>\
			Website: <a href='https://frappeframework.com' target='_blank'>https://frappeframework.com</a></p>\
		<p><i class='fa fa-github fa-fw'></i>\
			Source: <a href='https://github.com/frappe' target='_blank'>https://github.com/frappe</a></p>\
		<p><i class='fa fa-linkedin fa-fw'></i>\
			Linkedin: <a href='https://linkedin.com/company/frappe-tech' target='_blank'>https://linkedin.com/company/frappe-tech</a></p>\
		<p><i class='fa fa-facebook fa-fw'></i>\
			Facebook: <a href='https://facebook.com/erpnext' target='_blank'>https://facebook.com/erpnext</a></p>\
		<p><i class='fa fa-twitter fa-fw'></i>\
			Twitter: <a href='https://twitter.com/erpnext' target='_blank'>https://twitter.com/erpnext</a></p>\
		<hr>\
		<h4>Installed Apps</h4>\
		<div id='about-app-versions'>Loading versions...</div>\
		<hr>\
		<p class='text-muted'>&copy; Frappe Technologies Pvt. Ltd. and contributors </p> \
		</div>",
				frappe.app
			)
		);

		frappe.ui.misc.about_dialog = d;

		frappe.ui.misc.about_dialog.on_page_show = function () {
			if (!frappe.versions) {
				frappe.call({
					method: "frappe.utils.change_log.get_versions",
					callback: function (r) {
						show_versions(r.message);
					},
				});
			} else {
				show_versions(frappe.versions);
			}
		};

		var show_versions = function (versions) {
			var $wrap = $("#about-app-versions").empty();
			$.each(Object.keys(versions).sort(), function (i, key) {
				var v = versions[key];
				if (v.branch) {
					var text = $.format("<p><b>{0}:</b> v{1} ({2})<br></p>", [
						v.title,
						v.branch_version || v.version,
						v.branch,
					]);
				} else {
					var text = $.format("<p><b>{0}:</b> v{1}<br></p>", [v.title, v.version]);
				}
				$(text).appendTo($wrap);
			});

			frappe.versions = versions;
		};
	}

	frappe.ui.misc.about_dialog.show();
};
