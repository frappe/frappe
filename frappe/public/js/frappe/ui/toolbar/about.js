frappe.provide("frappe.ui.misc");
frappe.ui.misc.about = function () {
	if (!frappe.ui.misc.about_dialog) {
		var d = new frappe.ui.Dialog({ title: __("Frappe Framework") });

		$(d.body).html(
			repl(
				`<div>
					<p>${__("Open Source Applications for the Web")}</p>
					<p><i class='fa fa-globe fa-fw'></i>
						${__("Website")}:
						<a href='https://frappeframework.com' target='_blank'>https://frappeframework.com</a></p>
					<p><i class='fa fa-github fa-fw'></i>
						${__("Source")}:
						<a href='https://github.com/frappe' target='_blank'>https://github.com/frappe</a></p>
					<p><i class='fa fa-graduation-cap fa-fw'></i>
						Frappe School: <a href='https://frappe.school' target='_blank'>https://frappe.school</a></p>
					<p><i class='fa fa-linkedin fa-fw'></i>
						Linkedin: <a href='https://linkedin.com/company/frappe-tech' target='_blank'>https://linkedin.com/company/frappe-tech</a></p>
					<p><i class='fa fa-twitter fa-fw'></i>
						Twitter: <a href='https://twitter.com/frappetech' target='_blank'>https://twitter.com/frappetech</a></p>
					<p><i class='fa fa-youtube fa-fw'></i>
						YouTube: <a href='https://www.youtube.com/@frappetech' target='_blank'>https://www.youtube.com/@frappetech</a></p>
					<hr>
					<h4>${__("Installed Apps")}</h4>
					<div id='about-app-versions'>${__("Loading versions...")}</div>
					<p>
						<b>
							<a href="/attribution" target="_blank" class="text-muted">
								${__("Dependencies & Licenses")}
							</a>
						</b>
					</p>
					<hr>
					<p class='text-muted'>${__("&copy; Frappe Technologies Pvt. Ltd. and contributors")} </p>
					</div>`,
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
				let text;
				if (v.branch) {
					text = $.format("<p><b>{0}:</b> v{1} ({2})<br></p>", [
						v.title,
						v.branch_version || v.version,
						v.branch,
					]);
				} else {
					text = $.format("<p><b>{0}:</b> v{1}<br></p>", [v.title, v.version]);
				}
				$(text).appendTo($wrap);
			});

			frappe.versions = versions;
		};
	}

	frappe.ui.misc.about_dialog.show();
};
