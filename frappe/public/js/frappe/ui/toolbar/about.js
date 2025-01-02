frappe.provide("frappe.ui.misc");
frappe.ui.misc.about = function () {
	if (frappe.ui.misc.about_dialog) {
		frappe.ui.misc.about_dialog.show();
		return;
	}

	const dialog = new frappe.ui.Dialog({ title: __("Frappe Framework") });

	$(dialog.body).html(
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
				<p><i class='fa fa-users fa-fw'></i>
					${__(
						"Forum"
					)}: <a href='https://discuss.frappe.io' target='_blank'>https://discuss.frappe.io</a></p>
				<p><i class='fa fa-linkedin fa-fw'></i>
					Linkedin: <a href='https://linkedin.com/company/frappe-tech' target='_blank'>https://linkedin.com/company/frappe-tech</a></p>
				<p><i class='fa fa-twitter fa-fw'></i>
					Twitter: <a href='https://twitter.com/frappetech' target='_blank'>https://twitter.com/frappetech</a></p>
				<p><i class='fa fa-youtube-play fa-fw'></i>
					YouTube: <a href='https://www.youtube.com/@frappetech' target='_blank'>https://www.youtube.com/@frappetech</a></p>
				<p><i class='fa fa-instagram fa-fw'></i>
					Instagram: <a href='https://www.instagram.com/frappetech' target='_blank'>https://www.instagram.com/frappetech</a></p>
				<hr>
				<div class="d-flex align-items-center justify-content-between">
					<h4>${__("Installed Apps")}</h4>
					<button class="btn action-btn hidden" id="copy-apps-info"
					title="${__("Copy Apps Info")}"
					style="margin-bottom: var(--margin-md); padding-bottom:0;">
						${frappe.utils.icon("clipboard")}
					</button>
				</div>
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

	frappe.ui.misc.about_dialog = dialog;

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

	const show_versions = function (versions) {
		const $wrap = $("#about-app-versions").empty();
		let app = {};
		let text = "";

		$.each(Object.keys(versions).sort(), function (i, key) {
			app = versions[key];
			if (app.branch) {
				text = $.format(
					"<p class='app-version' role='button' title='{0}'><b>{1}:</b> v{2} ({3})<br></p>",
					[
						`${app.title}: v${app.branch_version || app.version} (${app.branch})`,
						app.title,
						app.branch_version || app.version,
						app.branch,
					]
				);
			} else {
				text = $.format(
					"<p class='app-version' role='button' title='{0}'><b>{1}:</b> v{2}<br></p>",
					[`${app.title}: v${app.version}`, app.title, app.version]
				);
			}
			$(text).appendTo($wrap);
		});

		frappe.versions = versions;

		if (frappe.versions) {
			$(dialog.body).find("#copy-apps-info").removeClass("hidden");
		}
	};

	const code_block = (snippet, lang = "") => "```" + lang + "\n" + snippet + "\n```";

	// Listener for copy installed apps info
	$(dialog.body).on("click", "#copy-apps-info", function () {
		const apps_info = [
			"### App Versions",
			code_block(JSON.stringify(frappe.versions, null, "\t"), "json"),
		].join("\n");

		frappe.utils.copy_to_clipboard(apps_info);
	});

	// Listener for copy app version
	$(dialog.body).on("click", ".app-version", function () {
		const title = $(this).attr("title");
		if (title) {
			frappe.utils.copy_to_clipboard(title);
		}
	});

	frappe.ui.misc.about_dialog.show();
};
