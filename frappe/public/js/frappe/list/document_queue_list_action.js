/**
 * Extends the Document Queue list-view integration.
 *
 * frappe.document_queue_review.setup_list_banner(listview) calls
 * frappe.document_queue_list_action.setup(listview) after confirming the
 * doctype has upload-first enabled. setup() fetches the pending count and,
 * if non-zero, prepends a "N Documents ready for review" banner to
 * .layout-main-section. Clicking the banner lazy-loads and opens
 * frappe.ui.DocumentQueueModal.
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

		const message = __("{0} Documents ready for review", [count]);
		const $banner = $(`
			<div class="document-queue-ready-banner">
				<span>${frappe.utils.escape_html(message)}</span>
				<button class="btn btn-xs btn-default" type="button">${__("View")}</button>
			</div>
		`);

		// Open modal when the banner is clicked. Promise form of frappe.require,
		// matching the feature's other call sites (the callback form is legacy).
		$banner.on("click", (e) => {
			e.stopPropagation();
			frappe.require("/assets/frappe/js/frappe/document_queue_review_modal.js").then(() => {
				if (!listview.document_queue_modal) {
					listview.document_queue_modal = new frappe.ui.DocumentQueueModal({
						doctype: listview.doctype,
					});
				}
				listview.document_queue_modal.show();
			});
		});

		// Insert the banner
		listview.$page.find(".layout-main-section").first().prepend($banner);
	},
};
