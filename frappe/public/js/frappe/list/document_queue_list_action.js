/**
 * Extends the Document Queue list-view integration.
 *
 * list_view.js calls frappe.document_queue_review.setup_list_banner(listview)
 * inside after_render() for upload-first doctypes.
 * We hook into that to add a "Review Pending (N)" button using the native
 * frappe.ui.Page.add_inner_button API (which uses the Espresso button system).
 *
 * Loaded inside list.bundle.js — runs before document_queue_review.js is lazy-loaded.
 */
frappe.provide("frappe.document_queue_list_action");

frappe.document_queue_list_action = {
	/**
	 * Called after document_queue_review.js is loaded and setup_list_banner fires.
	 * @param {frappe.views.ListView} listview
	 */
	setup: async function (listview) {
		if (!listview?.doctype || !listview?.page) return;

		const count = await frappe.document_queue_review.get_ready_for_review_count(
			listview.doctype
		);
		if (!count) return;

		// Remove any stale button from a previous render.
		listview.page.remove_inner_button(__("Review Pending ({0})", [count]));
		
		// Remove any existing banner to avoid duplicates
		listview.$page.find('.document-queue-ready-banner').remove();

		if (frappe.document_queue_review && frappe.document_queue_review.add_styles) {
			frappe.document_queue_review.add_styles();
		}

		const message = __("{0} Documents ready for review", [count]);
		const $banner = $(`
			<div class="document-queue-ready-banner" style="cursor: pointer;">
				<span>${frappe.utils.escape_html(message)}</span>
				<button class="btn btn-xs btn-default" type="button">${__("View")}</button>
			</div>
		`);

		// Open modal when the banner is clicked
		$banner.on("click", (e) => {
			e.stopPropagation();
			frappe.require(
				"/assets/frappe/js/frappe/document_queue_review_modal.js",
				() => new frappe.ui.DocumentQueueModal({ doctype: listview.doctype }).show()
			);
		});

		// Insert the banner
		listview.$page.find(".layout-main-section").first().prepend($banner);
	},
};
