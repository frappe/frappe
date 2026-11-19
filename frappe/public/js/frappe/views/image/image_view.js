/**
 * frappe.views.ImageView
 */
frappe.provide("frappe.views");

frappe.views.ImageView = class ImageView extends frappe.views.ListView {
	get view_name() {
		return "Image";
	}

	get show_saved_layout_menu() {
		return false;
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			this.page_title = this.page_title + " " + __("Images");
		});
	}

	async setup_view() {
		await this.setup_columns();
		this.setup_check_events();
		this.setup_like();
		this.setup_filterable();
	}

	set_fields() {
		this.link_field_title_fields = {};
		this.fields = [
			"name",
			...this.get_fields_in_list_view().map((el) => el.fieldname),
			this.meta.title_field,
			this.meta.image_field,
			"_liked_by",
		];
	}

	prepare_data(data) {
		super.prepare_data(data);
		this.items = this.data.map((d) => {
			d._image_url = this.get_image_url(d);
			return d;
		});
	}

	render() {
		this.load_lib.then(() => {
			this.get_attached_images().then(() => {
				this.render_image_view();

				if (!this.gallery) {
					this.setup_gallery();
				} else {
					this.gallery.prepare_pswp_items(this.items, this.images_map);
				}
			});
		});
	}

	render_image_view() {
		var html = this.items.map(this.item_html.bind(this)).join("");

		this.$page.find(".layout-main-section-wrapper").addClass("image-view");

		this.$result.html(`
			<div class="image-view-container">
				${html}
			</div>
		`);

		this.render_count();
		this.prune_checked_docnames();
		this.set_rows_as_checked();
	}

	item_details_html(item) {
		const title_field = this.meta.title_field || "name";
		let info_html = `<div><ul class="list-unstyled image-view-info">`;
		this.columns
			.filter((col) => ["Field", "Status"].includes(col.type))
			.filter((col) => col.df?.fieldname !== title_field)
			.forEach((col) => {
				if (col.type === "Status" && !frappe.get_indicator(item, this.doctype)) return;
				if (col.type === "Field" && !item[col.df.fieldname]) return;
				info_html += `<li>${this.get_column_html(col, item)}</li>`;
			});
		info_html += `</ul></div>`;
		return info_html;
	}

	item_html(item) {
		item._name = encodeURI(item.name);
		const encoded_name = item._name;
		const title = strip_html(item[this.meta.title_field || "name"]);
		const escaped_title = frappe.utils.escape_html(title);
		const escaped_name = frappe.utils.escape_html(item.name);
		const _class = !item._image_url ? "no-image" : "";
		const _html = item._image_url
			? `<img data-name="${encoded_name}" src="${frappe.utils.escape_html(
					item._image_url
			  )}" alt="${escaped_title}">`
			: `<span class="placeholder-text">
				${frappe.get_abbr(title)}
			</span>`;

		let details = this.item_details_html(item);

		const expand_button_html = item._image_url
			? `<div class="zoom-view" data-name="${encoded_name}">
				${frappe.utils.icon("expand", "xs")}
			</div>`
			: "";

		return `
			<div class="image-view-item ellipsis">
				<div class="image-view-header">
					<div>
						<input class="level-item list-row-checkbox hidden-xs"
							type="checkbox" data-name="${escape(item.name)}">
						${this.get_like_html(item)}
					</div>
				</span>
				</div>
				<div class="image-view-body ${_class}">
					<a data-name="${encoded_name}"
						title="${encoded_name}"
						href="${this.get_form_link(item)}"
					>
						<div class="image-field"
							data-name="${encoded_name}"
						>
							${_html}
						</div>
					</a>
					${expand_button_html}
				</div>
				<div class="image-view-footer">
					<div class="image-title">
						<span class="ellipsis" title="${escaped_title}">
							<a class="ellipsis" href="${this.get_form_link(item)}"
								title="${escaped_title}" data-doctype="${this.doctype}" data-name="${escaped_name}">
								${title}
							</a>
						</span>
					</div>
					${details}
				</div>
			</div>
		`;
	}

	get_attached_images() {
		return frappe
			.call({
				method: "frappe.core.api.file.get_attached_images",
				args: {
					doctype: this.doctype,
					names: this.items.map((i) => i.name),
				},
			})
			.then((r) => {
				this.images_map = Object.assign(this.images_map || {}, r.message);
			});
	}

	setup_gallery() {
		var me = this;
		this.gallery = new frappe.views.GalleryView({
			doctype: this.doctype,
			items: this.items,
			wrapper: this.$result,
			images_map: this.images_map,
		});
		this.$result.on("click", ".zoom-view", function (e) {
			e.preventDefault();
			e.stopPropagation();
			var name = $(this).data().name;
			name = decodeURIComponent(name);
			me.gallery.show(name);
			return false;
		});
	}

	get required_libs() {
		return [
			"assets/frappe/node_modules/photoswipe/src/photoswipe.css",
			"photoswipe.bundle.js",
		];
	}
};

frappe.views.GalleryView = class GalleryView {
	constructor(opts) {
		$.extend(this, opts);
		var me = this;
		me.prepare();
	}
	prepare() {
		// keep only one pswp dom element
		this.pswp_root = $("body > .pswp");
		if (this.pswp_root.length === 0) {
			var pswp = frappe.render_template("photoswipe_dom");
			this.pswp_root = $(pswp).appendTo("body");
		}
	}
	prepare_pswp_items(_items, _images_map) {
		var me = this;

		if (_items) {
			// passed when more button clicked
			this.items = this.items.concat(_items);
			this.images_map = _images_map;
		}

		return new Promise((resolve) => {
			const items = this.items
				.filter((i) => i.image !== null)
				.map(function (i) {
					const query = 'img[data-name="' + i._name + '"]';
					let el = me.wrapper.find(query).get(0);

					let width, height;
					if (el) {
						width = el.naturalWidth;
						height = el.naturalHeight;
					}

					if (!el) {
						el = me.wrapper.find('.image-field[data-name="' + i._name + '"]').get(0);
						width = el.getBoundingClientRect().width;
						height = el.getBoundingClientRect().height;
					}

					return {
						src: i._image_url,
						name: i.name,
						width: width,
						height: height,
					};
				});
			this.pswp_items = items;
			resolve();
		});
	}
	show(docname) {
		this.prepare_pswp_items().then(() => this._show(docname));
	}
	_show(docname) {
		const items = this.pswp_items;
		const item_index = items.findIndex((item) => item.name === docname);

		var options = {
			index: item_index,
			history: false,
			shareEl: false,
			dataSource: items,
		};

		// init
		this.pswp = new frappe.PhotoSwipe(options);
		this.pswp.init();
	}
};
