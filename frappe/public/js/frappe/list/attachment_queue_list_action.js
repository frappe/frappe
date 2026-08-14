/**
 * Extends the Attachment Queue list-view integration.
 *
 * list_view.js calls frappe.attachment_queue_review.setup_list_banner(listview)
 * inside after_render() for upload-first doctypes.
 * We hook into that to prepend a "N documents ready for review" banner above the
 * list, which opens the split-screen review modal when clicked.
 *
 * Loaded inside list.bundle.js — runs before attachment_queue_review.js is lazy-loaded.
 */
frappe.provide("frappe.attachment_queue_list_action");

frappe.attachment_queue_list_action = {
	/**
	 * Called after attachment_queue_review.js is loaded and setup_list_banner fires.
	 * @param {frappe.views.ListView} listview
	 */
	setup: async function (listview) {
		if (!listview?.doctype || !listview?.$page) return;

		const count = await frappe.attachment_queue_review.get_ready_for_review_count(
			listview.doctype
		);
		if (!count) return;

		// Remove any existing banner to avoid duplicates
		listview.$page.find(".attachment-queue-ready-banner").remove();

		if (frappe.attachment_queue_review && frappe.attachment_queue_review.add_styles) {
			frappe.attachment_queue_review.add_styles();
		}

		const message =
			count === 1
				? __("{0} document ready for review", [count])
				: __("{0} documents ready for review", [count]);
		const $banner = $(`
			<div class="attachment-queue-ready-banner" style="cursor: pointer;">
				<span>${frappe.utils.escape_html(message)}</span>
				<button class="btn btn-xs btn-default" type="button">${__("View")}</button>
			</div>
		`);

		// Open modal when the banner is clicked
		$banner.on("click", (e) => {
			e.stopPropagation();
			frappe.require("/assets/frappe/js/frappe/attachment_queue_review_modal.js", () => {
				if (!listview.attachment_queue_modal) {
					listview.attachment_queue_modal = new frappe.ui.AttachmentQueueModal({
						doctype: listview.doctype,
					});
				}
				listview.attachment_queue_modal.show();
			});
		});

		// Insert the banner
		listview.$page.find(".layout-main-section").first().prepend($banner);
	},
};
