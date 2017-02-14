/**
 * frappe.views.ImageView
 */
frappe.provide("frappe.views");

frappe.views.ImageView = Class.extend({
	init: function (opts) {
		$.extend(this, opts);
		this.prepare();
		this.render();
		this.setup_gallery();
	},
	prepare: function () {
		var me = this;
		this.meta = frappe.get_meta(this.doctype);
		this.setup_additional_columns();

		this.items = this.items.map(function(item) {
			var i = me.listview.prepare_data(item);
			if (i._title.length > 20) {
				i._title = i._title.slice(0, 20) + "...";
			}
			return i;
		});
	},
	setup_additional_columns: function () {
		this.additional_columns = this.listview.columns.filter(function (col) {
			return col.fieldtype && in_list([
				"Check", "Currency", "Data", "Date",
				"Datetime", "Float", "Int", "Link",
				"Percent", "Select", "Read Only", "Time"
			], col.fieldtype);
		});
	},
	render: function () {
		var html = this.items.map(this.render_item.bind(this)).join("");
		this.container = $('<div>')
			.addClass('image-view-container')
			.appendTo(this.wrapper);
		this.container.append(html);
	},
	render_item: function (item) {
		var image_url = this.get_image_url(item);
		var indicator = this.listview.get_indicator_html(item);
		return frappe.render_template("image_view_item_row", {
			data: item,
			indicator: indicator,
			additional_columns: this.additional_columns,
			item_image: image_url,
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
		// 	return "url('" + url + "')";
		}
		return null;
	},
	setup_gallery: function() {
		var me = this;
		var gallery = new frappe.views.GalleryView({
			doctype: this.doctype,
			items: this.items,
			wrapper: this.container
		});
		this.container.on('click', '.btn.zoom-view', function(e) {
			e.preventDefault();
			e.stopPropagation();
			var name = $(this).data().name;
			gallery.show(name);
			return false;
		});
	},
	refresh: function (data) {
		this.items = data;
		this.prepare();
		this.render();
		this.setup_gallery();
	}
});

frappe.views.GalleryView = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		var me = this;

		this.ready = false;
		this.load_lib(function() {
			me.prepare();
			me.ready = true;
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
	show: function(docname) {
		var me = this;
		if(!this.ready) {
			setTimeout(this.show.bind(this), 200);
			return;
		}
		var items = this.items.map(function(i) {
			var query = 'img[data-name="'+i.name+'"]';
			var el = me.wrapper.find(query).get(0);
			return {
				src: i.image,
				msrc: i.image,
				name: i.name,
				w: el.naturalWidth,
				h: el.naturalHeight,
				el: el
			}
		});

		var index;
		items.map(function(item, i) {
			if(item.name === docname)
				index = i;
		});

		var options = {
			index: index,
			getThumbBoundsFn: function(index) {
				var thumbnail = items[index].el, // find thumbnail
					pageYScroll = window.pageYOffset || document.documentElement.scrollTop,
					rect = thumbnail.getBoundingClientRect(); 

				return {x:rect.left, y:rect.top + pageYScroll, w:rect.width};
			},
			history: false,
			shareEl: false,
		}
		var pswp = new PhotoSwipe(
			this.pswp_root.get(0),
			PhotoSwipeUI_Default,
			items,
			options
		);
		pswp.init();
	},
	get_image_urls: function() {
		// not implemented yet
		return frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "File",
				order_by: "attached_to_name",
				fields: [
					"'image/*' as type", "ifnull(thumbnail_url, file_url) as thumbnail",
					"concat(attached_to_name, ' - ', file_name) as title", "file_url as src",
					"attached_to_name as name"
				],
				filters: [
					["File", "attached_to_doctype", "=", this.doctype],
					["File", "attached_to_name", "in", this.docnames],
					["File", "is_folder", "!=", 1]
				]
			},
			freeze: true,
			freeze_message: "Fetching Images.."
		}).then(function(r) {
			if (!r.message) {
				msgprint("No Images found")
			} else {
				// filter image files from other
				var images = r.message.filter(function(image) {
					return frappe.utils.is_image_file(image.title || image.href);
				});
			}
		});
	},
	load_lib: function(callback) {
		var asset_dir = 'assets/frappe/js/lib/photoswipe/';
		frappe.require([
			asset_dir + 'photoswipe.css',
			asset_dir + 'default-skin.css',
			asset_dir + 'photoswipe.js',
			asset_dir + 'photoswipe-ui-default.js'
		], callback);
	}
});