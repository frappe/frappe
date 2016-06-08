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
					"'image/*' as type", "ifnull(thumbnail_url, file_url) as thumbnail"
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
					// filter image files from other
					images = r.message.filter(function(image){
						return frappe.utils.is_image_file(image.title);
					});

					if(images){
						me.render(images);
					}
				}
			}
		});
	},

	render: function(image_list){
		var gallery = blueimp.Gallery(image_list, this.get_options());
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