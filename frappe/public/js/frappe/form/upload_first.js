frappe.provide("frappe.ui.form");

const QUEUE_DOCTYPE = "Attachment Queue";
const SUPPORTED_FILE_TYPES = [".pdf", ".jpg", ".jpeg", ".png"];

/**
 * Upload a file for a DocType that allows the upload-first workflow, then open a new document
 * of that DocType next to the file.
 */
frappe.ui.form.upload_first = function (document_type) {
	new frappe.ui.FileUploader({
		dialog_title: __("Upload a file for {0}", [__(document_type)]),
		upload_notes: __("PDFs and images only."),
		folder: "Home/Attachments",
		allow_toggle_private: false,
		disable_file_browser: true,
		restrictions: { allowed_file_types: SUPPORTED_FILE_TYPES, max_number_of_files: 1 },
		on_success: (file_doc) => {
			frappe.db
				.insert({
					doctype: QUEUE_DOCTYPE,
					document_type: document_type,
					source_file: file_doc.file_url,
				})
				.then((queue_doc) => frappe.ui.form.review_upload(document_type, queue_doc.name));
		},
	});
};

/**
 * Open a document of `document_type` with the queued file alongside it: the document the
 * entry already produced, or a new one to write from the file.
 *
 * @param {string} document_type
 * @param {string} queue_name Attachment Queue entry holding the file
 * @param {string} [document_name] an existing document; omit to start a new one
 */
frappe.ui.form.review_upload = function (document_type, queue_name, document_name) {
	frappe.route_hooks.after_load = (frm) => {
		if (frm.doctype === document_type) {
			new frappe.ui.form.UploadFirstReview({ frm, queue_name });
		}
	};

	frappe.model.with_doctype(document_type, () => {
		frappe.set_route(
			"Form",
			document_type,
			document_name || frappe.model.make_new_doc_and_get_name(document_type, true)
		);
	});
};

/**
 * The uploaded file beside the document being written from it: the file on the right, the
 * form on the left, and the queue entry filed against the document once it is saved.
 *
 * The panel is the form's own attachment preview, so it resizes, closes and remembers its
 * width like any other. What this adds is whether the entry reached its document.
 */
frappe.ui.form.UploadFirstReview = class UploadFirstReview {
	constructor({ frm, queue_name }) {
		frm.upload_first_review?.destroy();

		this.frm = frm;
		this.queue_name = queue_name;
		this.docname = frm.docname;
		frm.upload_first_review = this;

		$(frm.wrapper).on("render_complete.upload_first_review", () => this.on_form_render());
		this.load();
	}

	/**
	 * A form object outlives the document on screen, so each render has to say which document
	 * it is for: the one still being written, the one it just became on save, or an unrelated
	 * one, which ends the review.
	 */
	on_form_render() {
		if (this.destroyed) return;
        // the document on screen is the one this review was built for, so update the panel
		if (this.frm.docname === this.docname) {
			this.render();
		} // the document on screen is the one this review just filed against, so update the panel
		else if (frappe.model.new_names[this.docname] === this.frm.docname) {
			this.docname = this.frm.docname;
			this.link();
		} else {
			this.destroy();
		}
	}

	/** File the entry against the saved document. Safe to reach twice: the entry is claimed once. */
	link() {
		if (this.linking || this.queue_doc?.created_document) {
			this.render();
			return;
		}

		this.linking = true;
		frappe
			.xcall("run_doc_method", {
				dt: QUEUE_DOCTYPE,
				dn: this.queue_name,
				method: "link_to_document",
				args: { document_name: this.frm.docname },
			})
			.then(
				() => this.frm.sidebar?.reload_docinfo(),
				() => {} // the server has already said why
			)
			.finally(() => {
				this.linking = false;
				this.load();
			});
	}

	load() {
		return frappe.db.get_doc(QUEUE_DOCTYPE, this.queue_name).then(
			(queue_doc) => {
				if (this.destroyed) return;

				this.queue_doc = queue_doc;
				this.render();
			},
			() => this.destroy()
		);
	}

	/** Whether the form's preview panel is still the one this review built. */
	has_panel() {
		const panel = this.frm.attachments?.attachment_preview;
		return Boolean(
			this.$panel &&
				panel &&
				this.$panel[0] === panel[0] &&
				this.$panel.find(".upload-first-status").length
		);
	}

	render() {
		// The preview lives in the form sidebar, and a site can turn that off.
		if (!this.queue_doc || !this.frm.attachments) return;

		// A route change clears the preview and the sidebar builds a new one, so the panel
		// this review wrote into is not necessarily the one on screen.
		if (!this.has_panel()) {
			this.build_panel();
		}

		this.$panel.find(".upload-first-status").html(this.get_status_html());
	}

	build_panel() {
		const source_file = this.queue_doc.source_file;
		const file_url = this.frm.attachments.get_file_url({ file_url: source_file });
		const file_name = source_file.split("?")[0].split("/").pop();

		this.frm.attachments.show_attachment_preview({ file_name }, file_url);
		this.$panel = this.frm.attachments.attachment_preview.addClass("upload-first-review");

		$(`<div class="upload-first-status"></div>`).appendTo(this.$panel);
	}

	/**
	 * Whether the entry reached the document. Only reported once there is a saved document
	 * to reach.
	 */
	get_filing_html() {
		if (this.frm.is_new() || this.linking) return "";
		if (this.queue_doc.created_document === this.frm.docname) return "";

		return frappe.ui.badge.html({
			label: __("Not filed"),
			theme: "red",
			size: "sm",
			title: __("This file is not attached to {0}.", [this.frm.docname]),
		});
	}

	get_status_html() {
		return `
			${this.get_filing_html()}
			<a class="upload-first-entry-link" href="${frappe.utils.get_form_link(
				QUEUE_DOCTYPE,
				this.queue_name
			)}">${__("Queue entry")}</a>`;
	}

	destroy() {
		this.destroyed = true;
		$(this.frm.wrapper).off("render_complete.upload_first_review");

		if (this.frm.upload_first_review === this) {
			delete this.frm.upload_first_review;
		}

		if (this.has_panel()) {
			this.$panel.removeClass("upload-first-review");
			this.frm.attachments?.hide_attachment_preview();
		}
	}
};
