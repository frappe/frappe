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
		this.gallery = null;
		this.gallery = blueimp.Gallery(image_list, this.get_options());
		this.setup_navigation();
	},

	setup_navigation: function(){
		// extend gallery library to enable document navigation using UP / Down arrow key
		var me = this;
		var args = {}
	
		$.extend(me.gallery, {
			nextSlides:function(){
				args.offset = 1;
				me.navigate(args)
			},

			prevSlides:function(){
				args.offset = -1;
				me.navigate(args)
			}
		});
	},

	navigate: function(args){
		var index = 0;
		var me = this;
		var last_idx = cur_list.data.length - 1;

		$.each(cur_list.data, function(idx, doc){
			if(doc.name == me.docname){
				if(idx == last_idx && args.offset == 1){
					index = 0
				} else if(idx == 0 && args.offset == -1) {
					index = last_idx
				} else {
					index = idx + args.offset
				}
				me.docname = cur_list.data[index].name;
				return false;
			}
		});
		this.gallery.close();
		window.setTimeout(function(){
			me.get_images(this.doctype, this.docname)
		}, 500);
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