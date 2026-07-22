frappe.provide("frappe.ui.misc");
frappe.ui.misc.about = function () {
	if (frappe.ui.misc.about_dialog) {
		frappe.ui.misc.about_dialog.show();
		return;
	}

	const dialog = new frappe.ui.Dialog({ title: __("About") });
	$(dialog.wrapper).addClass("about-dialog");

	$(dialog.body).html(
		`<div class="about-body flex flex-col gap-5 items-start">
			<div class="about-frappe-section flex flex-col items-center gap-3 py-3 w-full">
				<div class="about-frappe-header flex flex-col justify-center items-center gap-1.5">
					<img src="/assets/frappe/images/frappe-comp-logo.svg" alt="Frappe" class="about-frappe-wordmark">
					<p class="about-tagline text-p-sm text-ink-gray-5 m-0">${__(
						"Open Source applications for the web."
					)}</p>
				</div>
				<div class="about-social-btns flex gap-1">
					<a href="https://frappe.io/" target="_blank" class="es-button" data-variant="ghost"
						data-icon-button="true" title="${__("Website")}" aria-label="${__("Website")}">
						${frappe.utils.icon("globe", "sm", "", "", "", true)}
					</a>
					<a href="https://github.com/frappe" target="_blank" class="es-button" data-variant="ghost"
						data-icon-button="true" title="${__("Source Code")}" aria-label="${__("Source Code")}">
						${frappe.utils.icon("github", "sm", "", "", "", true)}
					</a>
					<a href="https://discuss.frappe.io" target="_blank" class="es-button" data-variant="ghost"
						data-icon-button="true" title="${__("Forum")}" aria-label="${__("Forum")}">
						${frappe.utils.icon("message-circle", "sm", "", "", "", true)}
					</a>
				</div>
			</div>

			<div class="about-info-rows flex flex-col gap-3 w-full">
				<div class="about-info-row flex items-center justify-between">
					<div class="about-info-content flex flex-col gap-1">
						<div class="about-info-title inline-flex items-center gap-1 text-base-semibold text-ink-gray-8">${__(
							"Frappe Framework Version"
						)}</div>
						<div class="about-info-sub text-p-sm text-ink-gray-5" id="about-framework-version">
							${__("Loading...")}
						</div>
					</div>
				</div>
				${
					frappe.boot.is_fc_site
						? `<div class="about-info-row flex items-center justify-between">
					<div class="about-info-content flex flex-col gap-1">
						<a href="https://frappecloud.com/support" target="_blank" class="about-info-title inline-flex items-center gap-1 about-info-title-link text-base-semibold text-ink-gray-8 no-underline">
							${__("Frappe Support")}
							${frappe.utils.icon("external-link", "xs")}
						</a>
						<div class="about-info-sub text-p-sm text-ink-gray-5">
							${__("Visit Frappe Support Portal")}
						</div>
					</div>
				</div>`
						: ""
				}
			</div>

			<div class="about-section-header flex items-center justify-between w-full">
				<div class="about-section-label text-2xs text-ink-gray-6 text-uppercase">${__(
					"Installed Apps"
				)}</div>
				<button class="es-button hidden" data-variant="ghost" data-icon-button="true"
					id="copy-apps-info" title="${__("Copy Apps Version")}" aria-label="${__("Copy Apps Version")}">
					${frappe.utils.icon("clipboard", "sm", "", "", "", true)}
				</button>
			</div>

			<div id="about-app-versions" class="about-app-list flex flex-col gap-3 w-full"></div>
		</div>`
	);

	$(dialog.footer)
		.removeClass("hide")
		.prepend(
			`<div class="about-footer text-p-sm text-ink-gray-4 text-center">
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
			return `<img src="${app.logo}" class="about-app-logo size-8 rounded shrink-0" alt="${first_letter}">`;
		}
		if (app.color) {
			return `<div class="about-app-icon text-sm-semibold flex items-center justify-center size-8 rounded shrink-0" style="background-color: ${app.color};">${first_letter}</div>`;
		}
		const palette = frappe.get_palette(app_name);
		return `<div class="about-app-icon text-sm-semibold flex items-center justify-center size-8 rounded shrink-0" style="background-color: var(${palette[0]}); color: var(${palette[1]});">${first_letter}</div>`;
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
					class="es-button no-underline about-update-indicator">
					${__("Update Available")}
				</a>`).appendTo($version_row);
		}

		const $wrap = $("#about-app-versions").empty();

		for (const app_name in versions) {
			if (app_name === "frappe") continue;
			const app = versions[app_name];
			const version_text = get_version_text(app);
			const title = `${app_name}: ${app.version}`;

			$(`<div class="about-app-row flex items-center gap-3 cursor-pointer" role="button" tabindex="0" title="${title}">
					${render_app_icon(app_name, app)}
					<div class="about-app-info flex-1 min-w-0">
						<div class="about-app-name text-base-semibold text-ink-gray-8">${__(app.title)}</div>
						<div class="about-app-version text-sm text-ink-gray-5">${app_name}: ${version_text}</div>
					</div>
				</div>`).appendTo($wrap);
		}

		frappe.versions = versions;

		if (frappe.versions) {
			$(dialog.body).find("#copy-apps-info").removeClass("hidden");
		}
	};

	const code_block = (snippet, lang = "") => "```" + lang + "\n" + snippet + "\n```";

	// Listener for copying installed apps info
	$(dialog.body).on("click", "#copy-apps-info", function () {
		if (!frappe.versions) return;

		const versions = Object.entries(frappe.versions).reduce((acc, [key, app]) => {
			acc[key] = app.branch_version || app.version;
			return acc;
		}, {});

		frappe.utils.copy_to_clipboard(code_block(JSON.stringify(versions, null, "\t"), "json"));
	});

	// Listener for copy app version
	$(dialog.body).on("click", ".about-app-row", function () {
		const title = $(this).attr("title");
		if (title) {
			frappe.utils.copy_to_clipboard(title);
		}
	});

	// Keyboard support for copy app version (Enter / Space)
	$(dialog.body).on("keydown", ".about-app-row", function (e) {
		if (e.key === "Enter" || e.key === " ") {
			e.preventDefault();
			$(this).trigger("click");
		}
	});

	frappe.ui.misc.about_dialog.show();
};
