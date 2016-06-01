frappe.views.ImageView = Class.extend({
	init: function(opts){
		this.doctype = opts.doctype;
		this.docname = opts.docname;
		this.container = opts.container;

		this.get_images(this.doctype, this.docname);
	},

	get_images: function(doctype, docname){
		/*	get the list of all the Images associated with doc */
		var me = this;

		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "File",
				fields: [
					"file_name as title", "file_url as href",
					"'image/*' as type", "ifnull(thumbnail_url, '') as thumbnail"
				],
				filters: [
					["File", "attached_to_doctype", "=", this.doctype],
					["File", "attached_to_name", "=", this.docname],
					["File", "is_folder", "!=", 1]
				]
			},
			freeze: true,
			freeze_message: "Fetching Images ..",
			callback: function(r){
				if(!r.message){
					msgprint("No Images found")
				} else{
					me.render(r.message);
				}
			}
		});
	},

	render: function(image_list){
		var me = this;

		frappe.require(["assets/frappe/js/lib/gallery/js/blueimp-gallery.js",
			"assets/frappe/js/lib/gallery/js/blueimp-gallery-indicator.js"], function(){
			var gallery = blueimp.Gallery(image_list, me.get_options());
		})
	},

	get_options: function(){
		/* options for the gallery plugin */
		return {
			indicatorContainer: 'ol',
			thumbnailIndicators: true,
			thumbnailProperty: 'thumbnail',
			activeIndicatorClass: 'active',
			container: this.container.find(".blueimp-gallery")
		}
	}
});