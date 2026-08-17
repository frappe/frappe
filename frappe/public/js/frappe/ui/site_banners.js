frappe.provide("frappe.ui");

/**
 * Site-state banners — read-only mode and impersonation — shown ONCE above
 * the page header, at the top of the scrollable content column (so they sit
 * beside the sidebar, not across the whole viewport).
 *
 * Deliberately not part of frappe.ui.Page: pages come and go SPA-style while
 * the site state doesn't, so rendering these in every page header meant every
 * page duplicated them. The shell mounts this once at startup.
 *
 * Composed from utility classes only (the Gameplan ReadOnlyBanner pattern).
 */
frappe.ui.setup_site_banners = function () {
	const banners = [];

	if (frappe.boot.read_only) {
		banners.push({
			css_class: "bg-surface-gray-2 text-ink-gray-6",
			message: __(
				"This site is in read-only mode - it is undergoing maintenance or being updated."
			),
		});
	}

	if (frappe.boot.user.impersonated_by) {
		banners.push({
			css_class: "bg-surface-red-1 text-ink-red-7",
			message: __("You are impersonating {0}.", [frappe.boot.user.name]),
		});
	}

	if (!banners.length) return;

	const $wrapper = $('<div class="site-banners"></div>');
	banners.forEach((banner) => {
		const $banner = $(
			`<div class="${banner.css_class} py-2.5 text-p-sm"><div class="container"></div></div>`
		);
		// .container so the text lines up with the page header's content
		$banner.find(".container").text(banner.message);
		$wrapper.append($banner);
	});
	$wrapper.insertBefore("#body");
};
