/**
 * frappe.views.ImageView
 */
frappe.provide("frappe.views");

frappe.views.ImageView = class ImageView extends frappe.views.ListView {
	get view_name() {
		return 'Image';
	}

	setup_defaults() {
		super.setup_defaults();
		this.page_title = this.page_title + ' ' + __('Images');
	}

	setup_view() {
		this.setup_columns();
		this.setup_check_events();
	}

	set_fields() {
		this.fields = [
			'name',
			this.meta.title_field,
			this.meta.image_field
		];
	}

	prepare_data(data) {
		super.prepare_data(data);
		this.items = this.data.map(d => {
			// absolute url if cordova, else relative
			d._image_url = this.get_image_url(d);
			return d;
		});
	}

	render() {
		this.get_attached_images()
			.then(() => {
				this.render_image_view();

				if (!this.gallery) {
					this.setup_gallery();
				} else {
					this.gallery.prepare_pswp_items(this.items, this.images_map);
				}
			});
	}

	render_image_view() {
		var html = this.items.map(this.item_html.bind(this)).join("");

		this.$result.html(`
			${this.get_header_html()}
			<div class="image-view-container small">
				${html}
			</div>
		`);
	}

	item_html(item) {
		item._name = encodeURI(item.name);
		const encoded_name = item._name;
		const title = strip_html(item[this.meta.title_field || 'name']);
		const _class = !item._image_url ? 'no-image' : '';
		const _html = item._image_url ?
			`<img data-name="${encoded_name}" src="${ item._image_url }" alt="${ title }">` :
			`<span class="placeholder-text">
				${ frappe.get_abbr(title) }
			</span>`;

		return `
			<div class="image-view-item">
				<div class="image-view-header">
					<div class="list-row-col list-subject ellipsis level">
						${this.get_subject_html(item)}
					</div>
				</div>
				<div class="image-view-body">
					<a  data-name="${encoded_name}"
						title="${encoded_name}"
						href="${this.get_form_link(item)}"
					>
						<div class="image-field ${_class}"
							data-name="${encoded_name}"
						>
							${_html}
							<button class="btn btn-default zoom-view" data-name="${encoded_name}">
								<i class="fa fa-search-plus"></i>
							</button>
						</div>
					</a>
				</div>
			</div>
		`;
	}

	get_image_url(data) {
		var url;
		url = data.image ? data.image : data[this.meta.image_field];

		// absolute url for mobile
		if (window.cordova && !frappe.utils.is_url(url)) {
			url = frappe.base_url + url;
		}
		if (url) {
			return url;
		}
		return null;
	}

	get_attached_images() {
		return frappe.call({
			method: 'frappe.core.doctype.file.file.get_attached_images',
			args: {
				doctype: this.doctype,
				names: this.items.map(i => i.name)
			}
		}).then(r => {
			this.images_map = Object.assign(this.images_map || {}, r.message);
		});
	}

	get_header_html() {
		return this.get_header_html_skeleton(`
			<div class="list-row-col list-subject level ">
				<input class="level-item list-check-all hidden-xs" type="checkbox" title="Select All">
				<span class="level-item list-liked-by-me">
					<i class="octicon octicon-heart text-extra-muted" title="Likes"></i>
				</span>
				<span class="level-item"></span>
			</div>
		`);
	}

	setup_gallery() {
		var me = this;
		this.gallery = new frappe.views.GalleryView({
			doctype: this.doctype,
			items: this.items,
			wrapper: this.$result,
			images_map: this.images_map
		});
		this.$result.on('click', '.btn.zoom-view', function (e) {
			e.preventDefault();
			e.stopPropagation();
			var name = $(this).data().name;
			name = decodeURIComponent(name);
			me.gallery.show(name);
			return false;
		});
	}
};

frappe.views.GalleryView = Class.extend({
	init: function (opts) {
		$.extend(this, opts);
		var me = this;

		this.lib_ready = this.load_lib();
		this.lib_ready.then(function () {
			me.prepare();
		});
	},
	prepare: function () {
		// keep only one pswp dom element
		this.pswp_root = $('body > .pswp');
		if (this.pswp_root.length === 0) {
			var pswp = frappe.render_template('photoswipe_dom');
			this.pswp_root = $(pswp).appendTo('body');
		}
	},
	prepare_pswp_items: function (_items, _images_map) {
		var me = this;

		if (_items) {
			// passed when more button clicked
			this.items = this.items.concat(_items);
			this.images_map = _images_map;
		}

		return new Promise(resolve => {
			const items = this.items.map(function (i) {
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
					msrc: i._image_url,
					name: i.name,
					w: width,
					h: height,
					el: el
				};
			});
			this.pswp_items = items;
			resolve();
		});
	},
	show: function (docname) {
		this.lib_ready
			.then(() => this.prepare_pswp_items())
			.then(() => this._show(docname));
	},
	_show: function (docname) {
		const me = this;
		const items = this.pswp_items;
		const item_index = items.findIndex(item => item.name === docname);

		var options = {
			index: item_index,
			getThumbBoundsFn: function (index) {
				const query = 'img[data-name="' + items[index]._name + '"]';
				let thumbnail = me.wrapper.find(query).get(0);

				if (!thumbnail) {
					return;
				}

				var pageYScroll = window.pageYOffset || document.documentElement.scrollTop,
					rect = thumbnail.getBoundingClientRect();

				return {
					x: rect.left,
					y: rect.top + pageYScroll,
					w: rect.width
				};
			},
			history: false,
			shareEl: false,
			showHideOpacity: true
		};

		// init
		this.pswp = new PhotoSwipe(
			this.pswp_root.get(0),
			PhotoSwipeUI_Default,
			items,
			options
		);
		this.browse_images();
		this.pswp.init();
	},
	browse_images: function () {
		const $more_items = this.pswp_root.find('.pswp__more-items');
		const images_map = this.images_map;
		let last_hide_timeout = null;

		this.pswp.listen('afterChange', function () {
			const images = images_map[this.currItem.name];
			if (!images || images.length === 1) {
				$more_items.html('');
				return;
			}

			hide_more_items_after_2s();
			const html = images.map(img_html).join("");
			$more_items.html(html);
		});

		this.pswp.listen('beforeChange', hide_more_items);
		this.pswp.listen('initialZoomOut', hide_more_items);
		this.pswp.listen('destroy', () => {
			$(document).off('mousemove', hide_more_items_after_2s);
		});

		// Replace current image on click
		$more_items.on('click', '.pswp__more-item', (e) => {
			const img_el = e.target;
			const index = this.pswp.items.findIndex(i => i.name === this.pswp.currItem.name);

			this.pswp.goTo(index);
			this.pswp.items.splice(index, 1, {
				src: img_el.src,
				w: img_el.naturalWidth,
				h: img_el.naturalHeight,
				name: this.pswp.currItem.name
			});
			this.pswp.invalidateCurrItems();
			this.pswp.updateSize(true);
		});

		// hide more-images 2s after mousemove
		$(document).on('mousemove', hide_more_items_after_2s);

		function hide_more_items_after_2s() {
			clearTimeout(last_hide_timeout);
			show_more_items();
			last_hide_timeout = setTimeout(hide_more_items, 2000);
		}

		function show_more_items() {
			$more_items.show();
		}

		function hide_more_items() {
			$more_items.hide();
		}

		function img_html(src) {
			return `<div class="pswp__more-item">
				<img src="${src}">
			</div>`;
		}
	},
	load_lib: function () {
		return new Promise(resolve => {
			var asset_dir = 'assets/frappe/js/lib/photoswipe/';
			frappe.require([
				asset_dir + 'photoswipe.css',
				asset_dir + 'default-skin.css',
				asset_dir + 'photoswipe.js',
				asset_dir + 'photoswipe-ui-default.js'
			], resolve);
		});
	}
});