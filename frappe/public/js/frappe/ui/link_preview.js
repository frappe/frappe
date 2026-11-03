class LinkPreviewCard extends frappe.ui.HoverCard {
	open() {
		if (this.trigger_el === document.activeElement) return;
		this.waiting_for_data = !this.opts.get_data();
		if (!this.waiting_for_data) super.open();
	}

	close() {
		this.waiting_for_data = false;
		super.close();
	}

	data_ready() {
		if (this.waiting_for_data && this.trigger_el.matches(":hover")) this.open();
	}
}

frappe.ui.LinkPreview = class {
	constructor() {
		// tree labels carry their own hover card (frappe.ui.Tree)
		this.LINK_CLASSES = 'a[data-doctype]:not(.tree-label), input[data-fieldtype="Link"]';
		this.setup_events();
	}

	setup_events() {
		$(document.body).on("mouseover", this.LINK_CLASSES, (e) => {
			const element = e.currentTarget;
			if (element.closest(".es-hover-card")) return;
			const key = this.get_doc_key(element);
			if (!this.name || !(frappe.boot.link_preview_doctypes || []).includes(this.doctype)) {
				return;
			}

			if ($(element).data("link-preview")?.key !== key) {
				clearTimeout(this.data_timeout);
				const { doctype, name } = this;
				this.data_timeout = setTimeout(() => {
					this.get_preview_data(doctype, name).then((data) => {
						if (!data) return;
						$(element).data("link-preview", { key, data });
						$(element).data("es-hover-card")?.data_ready();
					});
				}, 100);
			}
			if (!$(element).data("es-hover-card")) {
				this.make_card(element);
				element.dispatchEvent(new PointerEvent("pointerenter"));
			}
		});

		$(document.body).on("mouseout", this.LINK_CLASSES, () => clearTimeout(this.data_timeout));

		frappe.router.on("change", () => this.open_card?.close());
	}

	make_card(element) {
		const get_data = () => {
			const cached = $(element).data("link-preview");
			return cached?.key === this.get_doc_key(element) ? cached.data : null;
		};
		const card = new LinkPreviewCard(element, {
			side: "top",
			open_delay: 1000,
			css_class: "link-preview-popover",
			get_data,
			content: () => $("<div>").html(this.get_popover_html(get_data()))[0],
			on_open: () => (this.open_card = card),
			on_close: () => (this.open_card = null),
		});
		$(element).data("es-hover-card", card);
	}

	identify_doc() {
		if (this.is_link) {
			this.doctype = this.element.attr("data-doctype");
			this.name = frappe.utils.unescape_html(this.element.attr("data-name"));
			this.href = this.element.attr("href");
		} else {
			this.href = this.element
				.parents(".control-input-wrapper")
				.find(".control-value a")
				.attr("href");
			// input
			this.doctype = this.element.attr("data-target");
			this.name = this.element.val();
		}
	}

	get_doc_key(element) {
		this.element = $(element);
		this.is_link = element.tagName.toLowerCase() === "a";
		this.identify_doc();
		return `${this.doctype}::${this.name}`;
	}

	get_preview_data(doctype, docname) {
		return frappe.xcall(
			"frappe.desk.link_preview.get_preview_data",
			{ doctype, docname },
			"GET",
			{ cache: true }
		);
	}

	get_popover_html(preview_data) {
		if (!this.href) {
			this.href = window.location.href;
		}

		if (this.href && this.href.includes(" ")) {
			this.href = this.href.replace(new RegExp(" ", "g"), "%20");
		}

		const div = document.createElement("div");
		div.innerHTML = `
			<div class="preview-popover-header">
				<div class="preview-header">
					${this.get_image_html(preview_data)}
					<div class="preview-name">
						<a></a>
					</div>
					<div class="text-muted preview-title">${this.get_id_html(preview_data)}</div>
				</div>
			</div>
			<hr>
			<div class="popover-body">
				${this.get_content_html(preview_data)}
			</div>
		`;

		const a = div.querySelector(".preview-name > a");
		a.href = this.href;
		a.innerText = __(preview_data.preview_title);

		return div.innerHTML;
	}

	get_id_html(preview_data) {
		if (preview_data.preview_title !== preview_data.name) {
			const a = document.createElement("a");
			a.href = this.href;
			a.className = "text-muted";
			a.innerText = preview_data.name;
			return a.outerHTML;
		}
		return "";
	}

	get_image_html(preview_data) {
		let avatar_html = frappe.get_avatar(
			"avatar-medium",
			preview_data.preview_title,
			preview_data.preview_image
		);

		return `<div class="preview-image">
			${avatar_html}
		</div>`;
	}

	get_content_html(preview_data) {
		let content_html = "";

		Object.keys(preview_data).forEach((key) => {
			if (!["preview_image", "preview_title", "name"].includes(key)) {
				let value = frappe.ellipsis(preview_data[key], 280);
				let label = key;
				content_html += `
					<div class="preview-field">
						<div class="preview-label text-muted">${__(label)}</div>
						<div class="preview-value">${value}</div>
					</div>
				`;
			}
		});

		return `<div class="preview-table">${content_html}</div>`;
	}
};
