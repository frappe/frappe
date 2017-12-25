/**
 * frappe.views.ImageView
 */
frappe.provide("frappe.views");

frappe.views.ImageView = frappe.views.ListRenderer.extend({
	name: 'Image',
	render_view: function (values) {
		this.items = values;

		this.get_attached_images()
			.then(() => {
				this.render_image_view();

				if (!this.gallery) {
					this.setup_gallery();
				} else {
					this.gallery.prepare_pswp_items(this.items, this.images_map);
				}
			});
	},
	set_defaults: function() {
		this._super();
		this.page_title = this.page_title + ' ' + __('Images');
	},
	prepare_data: function(data) {
		data = this._super(data);
		// absolute url if cordova, else relative
		data._image_url = this.get_image_url(data);
		return data;
	},
	render_image_view: function () {
		var html = this.items.map(this.render_item.bind(this)).join("");

		this.container = this.wrapper.find('.image-view-container');
		if (this.container.length === 0) {
			this.container = $('<div>')
				.addClass('image-view-container')
				.appendTo(this.wrapper);
		}

		this.container.append(html);
	},
	render_item: function (item) {
		var indicator = this.get_indicator_html(item);
		return frappe.render_template("image_view_item_row", {
			data: item,
			indicator: indicator,
			subject: this.get_subject_html(item, true),
			additional_columns: this.additional_columns,
			color: frappe.get_palette(item.item_name)
		});
	},
	get_image_url: function (item) {
		var url;
		url = item.image ? item.image : item[this.meta.image_field];

		// absolute url for mobile
		if (window.cordova && !frappe.utils.is_url(url)) {
			url = frappe.base_url + url;
		}
		if (url) {
			return url
		}
		return null;
	},
	get_attached_images: function () {
		return frappe.call({
			method: 'frappe.core.doctype.file.file.get_attached_images',
			args: { doctype: this.doctype, names: this.items.map(i => i.name) }
		}).then(r => {
			this.images_map = Object.assign(this.images_map || {}, r.message);
		});
	},
	get_header_html: function () {
		var main = frappe.render_template('list_item_main_head', {
			col: { type: "Subject" },
			_checkbox: ((frappe.model.can_delete(this.doctype) || this.settings.selectable)
				&& !this.no_delete)
		});
		return frappe.render_template('list_item_row_head', { main: main, list: this });
	},
	setup_gallery: function() {
		var me = this;
		this.gallery = new frappe.views.GalleryView({
			doctype: this.doctype,
			items: this.items,
			wrapper: this.container,
			images_map: this.images_map
		});
		this.container.on('click', '.btn.zoom-view', function(e) {
			e.preventDefault();
			e.stopPropagation();
			var name = $(this).data().name;
			me.gallery.show(name);
			return false;
		});
	}
});

frappe.views.GalleryView = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		var me = this;

		this.lib_ready = this.load_lib();
		this.lib_ready.then(function() {
			me.prepare();
		});
	},
	prepare: function() {
		// keep only one pswp dom element
		this.pswp_root = $('body > .pswp');
		if(this.pswp_root.length === 0) {
			var pswp = frappe.render_template('photoswipe_dom');
			this.pswp_root = $(pswp).appendTo('body');
		}
	},
	prepare_pswp_items: function(_items, _images_map) {
		var me = this;

		if (_items) {
			// passed when more button clicked
			this.items = this.items.concat(_items);
			this.images_map = _images_map;
		}

		return new Promise(resolve => {
			const items = this.items.map(function(i) {
				const query = 'img[data-name="'+i.name+'"]';
				let el = me.wrapper.find(query).get(0);

				let width, height;
				if(el) {
					width = el.naturalWidth;
					height = el.naturalHeight;
				}

				if(!el) {
					el = me.wrapper.find('.image-field[data-name="'+i.name+'"]').get(0);
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
				}
			});
			this.pswp_items = items;
			resolve();
		});
	},
	show: function(docname) {
		this.lib_ready
			.then(() => this.prepare_pswp_items())
			.then(() => this._show(docname));
	},
	_show: function(docname) {
		const me = this;
		const items = this.pswp_items;
		const item_index = items.findIndex(item => item.name === docname);

		var options = {
			index: item_index,
			getThumbBoundsFn: function(index) {
				const query = 'img[data-name="' + items[index].name + '"]';
				let thumbnail = me.wrapper.find(query).get(0);

				if (!thumbnail) {
					return;
				}

				var pageYScroll = window.pageYOffset || document.documentElement.scrollTop,
					rect = thumbnail.getBoundingClientRect();

				return {x:rect.left, y:rect.top + pageYScroll, w:rect.width};
			},
			history: false,
			shareEl: false,
			showHideOpacity: true
		}

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
	browse_images: function() {
		const $more_items = this.pswp_root.find('.pswp__more-items');
		const images_map = this.images_map;
		let last_hide_timeout = null;

		this.pswp.listen('afterChange', function() {
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
		this.pswp.listen('destroy', $(document).off('mousemove', hide_more_items_after_2s));

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
	load_lib: function() {
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
