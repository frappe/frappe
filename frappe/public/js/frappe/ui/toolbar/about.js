frappe.provide("frappe.ui.misc");
frappe.ui.misc.about = function () {
	if (frappe.ui.misc.about_dialog) {
		frappe.ui.misc.about_dialog.show();
		return;
	}

	const dialog = new frappe.ui.Dialog({ title: __("About") });
	$(dialog.wrapper).addClass("about-dialog");

	$(dialog.body).html(
		`<div class="about-body">
			<div class="about-frappe-section">
			<img src="/assets/frappe/images/frappe-comp-logo.svg" alt="Frappe" class="about-frappe-wordmark">
				<p class="about-tagline">${__("Open Source applications for the web.")}</p>
				<div class="about-social-btns">
					<a href="https://frappe.io/" target="_blank" class="about-icon-btn"
						title="${__("Website")}">
						${frappe.utils.icon("globe", "sm")}
					</a>
					<a href="https://github.com/frappe" target="_blank" class="about-icon-btn"
						title="${__("Source Code")}">
						${frappe.utils.icon("github", "sm")}
					</a>
					<a href="https://discuss.frappe.io" target="_blank" class="about-icon-btn"
						title="${__("Forum")}">
						${frappe.utils.icon("message-circle", "sm")}
					</a>
				</div>
			</div>

			<div class="about-info-rows">
				<div class="about-info-row">
					<div class="about-info-content">
						<div class="about-info-title">${__("Frappe Framework Version")}</div>
						<div class="about-info-sub" id="about-framework-version">
							${__("Loading...")}
						</div>
					</div>
				</div>
				${
					frappe.boot.is_fc_site
						? `<div class="about-info-row">
					<div class="about-info-content">
						<a href="https://frappecloud.com/support" target="_blank" class="about-info-title about-info-title-link">
							${__("Frappe Support")}
							${frappe.utils.icon("external-link", "xs")}
						</a>
						<div class="about-info-sub">
							${__("Visit Frappe Support Portal")}
						</div>
					</div>
				</div>`
						: ""
				}
			</div>

			<div class="about-section-label">${__("Installed Apps")}</div>

			<div id="about-app-versions" class="about-app-list"></div>
		</div>`
	);

	$(dialog.footer)
		.removeClass("hide")
		.prepend(
			`<div class="about-footer">
			${__("&copy; Frappe Technologies Pvt. Ltd. and contributors")}
		</div>`
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

	const get_version_text = function (app) {
		const is_pr_branch = app.branch && /^pr-\d+/i.test(app.branch);
		if (app.branch && !is_pr_branch) {
			return `${app.version} (${app.branch})`;
		}
		return app.version;
	};

	const render_app_icon = function (app_name, app) {
		const first_letter = (app.title || app_name).charAt(0).toUpperCase();
		if (app.logo) {
			return `<img src="${app.logo}" class="about-app-logo" alt="${first_letter}">`;
		}
		if (app.color) {
			return `<div class="about-app-icon" style="background-color: ${app.color};">${first_letter}</div>`;
		}
		const palette = frappe.get_palette(app_name);
		return `<div class="about-app-icon" style="background-color: var(${palette[0]}); color: var(${palette[1]});">${first_letter}</div>`;
	};

	const show_versions = function (versions) {
		if (versions.frappe) {
			$("#about-framework-version").text(`frappe: ${get_version_text(versions.frappe)}`);
		}

		// Show update button on Frappe Cloud sites when updates are available
		const $version_row = $("#about-framework-version").closest(".about-info-row");
		$version_row.find(".about-update-indicator").remove();
		if (frappe.boot.has_app_updates && frappe.boot.is_fc_site) {
			$(`<a href="https://frappecloud.com/dashboard/sites/${window.location.hostname}"
					target="_blank"
					class="btn btn-default btn-sm about-update-indicator">
					${__("Update Available")}
				</a>`).appendTo($version_row);
		}

		const $wrap = $("#about-app-versions").empty();

		for (const app_name in versions) {
			if (app_name === "frappe") continue;
			const app = versions[app_name];
			const version_text = get_version_text(app);
			const title = `${app_name}: ${app.version}`;

			$(`<div class="about-app-row" title="${title}">
					${render_app_icon(app_name, app)}
					<div class="about-app-info">
						<div class="about-app-name">${__(app.title)}</div>
						<div class="about-app-version">${app_name}: ${version_text}</div>
					</div>
				</div>`).appendTo($wrap);
		}

		frappe.versions = versions;
	};

	frappe.ui.misc.about_dialog.show();
};
