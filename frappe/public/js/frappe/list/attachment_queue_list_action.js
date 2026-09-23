/**
 * Attachment Queue review banner for List View.
 *
 * list_view.js calls frappe.attachment_queue_list_action.setup(listview) from
 * after_render(). This file owns the whole list-view side: the doctype gate, the
 * count, the banner and lazy-loading the modal.
 *
 * It deliberately does not depend on attachment_queue_review.js, so showing a
 * banner does not pull in the review module. Ships in list.bundle.js; the loader
 * it calls ships in form.bundle.js, and both are in app_include_js.
 */
frappe.provide("frappe.attachment_queue_list_action");

frappe.attachment_queue_list_action.get_ready_for_review_count = function (doctype) {
	return frappe
		.call({
			method: "frappe.core.doctype.attachment_queue.attachment_queue.get_ready_for_review_count",
			args: { document_type: doctype },
		})
		.then((r) => cint(r.message) || 0)
		.catch(() => 0);
};

/**
 * Add the review banner to a List View.
 * @param {frappe.views.ListView} listview
 */
frappe.attachment_queue_list_action.setup = async function (listview) {
	if (!listview?.doctype || !listview?.$page) {
		return;
	}

	// after_render() runs on every refresh - filter, sort, load-more, realtime update
	// and this guard stops two overlapping runs from both drawing a banner.
	if (listview.attachment_queue_banner_pending) {
		return;
	}
	listview.attachment_queue_banner_pending = true;

	try {
		const enabled = await frappe.attachment_queue_review_loader.is_upload_first_enabled(
			listview.doctype
		);
		if (!enabled) {
			return;
		}

		const count = await frappe.attachment_queue_list_action.get_ready_for_review_count(
			listview.doctype
		);

		// Remove before the count check, so a list that drops to zero loses its banner.
		listview.$page.find(".attachment-queue-ready-banner").remove();
		if (!count) {
			return;
		}

		const message =
			count === 1
				? __("{0} document ready for review", [count])
				: __("{0} documents ready for review", [count]);
		const $banner = $(`
			<div class="attachment-queue-ready-banner">
				<span>${frappe.utils.escape_html(message)}</span>
				<button class="btn btn-xs btn-default" type="button">${frappe.utils.escape_html(
					__("View")
				)}</button>
			</div>
		`);

		$banner.on("click", (e) => {
			e.stopPropagation();
			frappe.require("/assets/frappe/js/frappe/attachment_queue_review_modal.js", () => {
				if (!frappe.ui.AttachmentQueueModal) {
					frappe.msgprint(
						__("Could not open the review screen. Please reload and try again.")
					);
					return;
				}

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
	} finally {
		listview.attachment_queue_banner_pending = false;
	}
};
