frappe.ui.form.ControlAttachmentGallery = class ControlAttachmentGallery extends (
	frappe.ui.form.ControlInput
) {
	static horizontal = false;

	make() {
		super.make();
		this.$gallery = $(this.input_area);
		if (this.frm) {
			$(this.frm.wrapper).on("attachments_change", () => this.refresh());
		}
	}

	async refresh_input() {
		this.set_label();
		this.set_description();

		const refresh_id = (this.refresh_id || 0) + 1;
		this.refresh_id = refresh_id;

		if (!this.frm) {
			this.$gallery.empty();
			this.image_thumbnails = new Map();
			return;
		}

		if (this.frm.doc.__islocal) {
			this.$gallery.empty();
			this.image_thumbnails = new Map();
			this.render_empty_state(__("Save the document to attach files."));
			return;
		}

		let attachments;
		try {
			attachments = await this.get_attachments();
		} catch (error) {
			if (refresh_id !== this.refresh_id) {
				return;
			}
			this.$gallery.empty();
			this.image_thumbnails = new Map();
			this.render_empty_state(__("Unable to load attachments."));
			return;
		}
		if (refresh_id !== this.refresh_id) {
			return;
		}
		this.$gallery.empty();
		this.image_thumbnails = new Map();
		this.attachments = attachments;
		const can_add = this.can_add_attachment();

		if (!attachments.length && !can_add) {
			this.render_empty_state(__("No attachments"));
			return;
		}

		const $grid = $('<div class="attachment-gallery"></div>').appendTo(this.$gallery);
		const can_delete =
			this.disp_status === "Write" && this.frm.attachments?.can_delete_attachment();

		attachments.forEach((attachment) => {
			this.render_attachment($grid, attachment, can_delete);
		});

		if (can_add) {
			this.render_upload_button($grid);
		}
	}

	render_empty_state(message) {
		$('<div class="attachment-gallery-empty"></div>').text(message).appendTo(this.$gallery);
	}

	async get_attachments() {
		let attachments = this.frm.get_files();
		const filters = this.get_filters();
		if (filters.length) {
			const response = await frappe.call({
				method: "frappe.desk.form.load.get_filtered_attachments",
				args: {
					dt: this.frm.doctype,
					dn: this.frm.docname,
					filters: JSON.stringify(filters),
				},
			});
			if (!Array.isArray(response.message)) {
				throw new Error("Invalid filtered attachments response");
			}
			attachments = response.message;
		}

		return frappe.utils.sort(attachments, "file_name", "string").map((attachment) => ({
			...attachment,
			file_name: attachment.file_name || attachment.file_url,
			file_url: this.frm.attachments.get_file_url(attachment),
			is_image: frappe.utils.is_image_file(attachment.file_url || attachment.file_name),
		}));
	}

	get_filters() {
		if (!this.df.link_filters) {
			return [];
		}

		try {
			return JSON.parse(this.df.link_filters).map((filter) => {
				if (filter[3]?.startsWith?.("eval:")) {
					filter[3] = frappe.utils.eval(filter[3].slice(5), {
						doc: this.get_doc(),
						parent: this.get_doc().parenttype ? this.frm.doc : null,
						frappe,
					});
				}
				return filter;
			});
		} catch (error) {
			console.error("Invalid Attachment Gallery filters:", this.df.link_filters, error);
			return [];
		}
	}

	can_add_attachment() {
		return (
			this.disp_status === "Write" &&
			!this.frm.doc.__islocal &&
			this.frm.has_perm("write") &&
			this.frm.attachments &&
			!this.frm.attachments.max_reached()
		);
	}

	render_attachment($grid, attachment, can_delete) {
		const $item_wrapper = $('<div class="attachment-gallery-item-wrapper"></div>').appendTo(
			$grid
		);

		if (attachment.is_image) {
			const $button = $(
				'<button type="button" class="attachment-gallery-item attachment-gallery-image"></button>'
			)
				.attr("title", attachment.file_name)
				.attr("aria-label", attachment.file_name)
				.appendTo($item_wrapper);
			const $image = $("<img>")
				.attr({
					src: attachment.file_url,
					alt: attachment.file_name,
					loading: "lazy",
				})
				.appendTo($button);

			$button.on("click", () => {
				const images = this.get_image_attachments();
				const image_index = images.findIndex((image) => image.name === attachment.name);
				if (image_index !== -1) {
					this.open_lightbox(images, image_index);
				}
			});

			this.image_thumbnails.set(attachment.name, $image.get(0));
		} else {
			const $link = $(
				'<a class="attachment-gallery-item attachment-gallery-file" target="_blank" rel="noopener noreferrer"></a>'
			)
				.attr({
					href: attachment.file_url,
					title: attachment.file_name,
					"aria-label": attachment.file_name,
				})
				.appendTo($item_wrapper);
			const $placeholder = $('<div class="attachment-gallery-placeholder"></div>').appendTo(
				$link
			);
			$placeholder.append(frappe.utils.icon("file", "lg"));
			$("<span></span>")
				.addClass("attachment-gallery-filename")
				.text(attachment.file_name)
				.appendTo($placeholder);
		}

		if (can_delete) {
			this.render_delete_button($item_wrapper, attachment);
		}
	}

	render_delete_button($item_wrapper, attachment) {
		const label = __("Delete attachment");
		const $button = $('<button type="button" class="attachment-gallery-delete"></button>')
			.html(frappe.utils.icon("delete", "xs"))
			.attr({ title: label, "aria-label": label })
			.appendTo($item_wrapper)
			.tooltip({ delay: { show: 100, hide: 100 }, trigger: "hover" });

		$button.on("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			$button.tooltip("hide");
			this.delete_attachment(attachment);
		});
	}

	render_upload_button($grid) {
		const label = __("Add attachment");
		const $button = $(
			'<button type="button" class="attachment-gallery-item attachment-gallery-upload"></button>'
		)
			.html(frappe.utils.icon("upload", "lg"))
			.attr({ title: label, "aria-label": label })
			.appendTo($grid)
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		$button.on("click", () => {
			$button.tooltip("hide");
			this.frm.attachments.new_attachment(this.df.fieldname);
		});
	}

	delete_attachment(attachment) {
		frappe.confirm(__("Are you sure you want to delete the attachment?"), () => {
			this.frm.attachments.remove_attachment(attachment.name);
		});
	}

	get_image_attachments() {
		return this.attachments
			.filter((attachment) => attachment.is_image)
			.map((attachment) => ({
				...attachment,
				thumbnail: this.image_thumbnails.get(attachment.name),
			}));
	}

	open_lightbox(images, index) {
		this.load_photoswipe().then(() => {
			const data_source = images.map((image) => ({
				src: image.file_url,
				width: image.thumbnail?.naturalWidth || 1600,
				height: image.thumbnail?.naturalHeight || 1200,
				thumbEl: image.thumbnail,
			}));
			const photoswipe = new frappe.PhotoSwipe({
				dataSource: data_source,
				index,
				showHideAnimationType: "zoom",
			});
			photoswipe.init();
		});
	}

	load_photoswipe() {
		if (!frappe.ui.form.ControlAttachmentGallery.photoswipe_ready) {
			frappe.ui.form.ControlAttachmentGallery.photoswipe_ready = new Promise((resolve) => {
				frappe.require(
					[
						"assets/frappe/node_modules/photoswipe/src/photoswipe.css",
						"photoswipe.bundle.js",
					],
					resolve
				);
			});
		}

		return frappe.ui.form.ControlAttachmentGallery.photoswipe_ready;
	}
};
