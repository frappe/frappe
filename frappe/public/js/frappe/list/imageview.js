frappe.views.ImageView = Class.extend({
	init: function(opts){
		this.docnames = []
		this.doc_images = {}
		this.doctype = opts.doctype;
		this.docname = opts.docname;
		this.container = opts.container;

		this.get_images(this.doctype, this.docname);
	},

	get_images: function(doctype, docname){
		/*	get the list of all the Images associated with doc */
		var me = this;
		if(Object.keys(this.doc_images).length == 0){
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "File",
					order_by: "attached_to_name",
					fields: [
						"'image/*' as type", "ifnull(thumbnail_url, file_url) as thumbnail",
						"concat(attached_to_name, ' - ', file_name) as title", "file_url as href",
						"attached_to_name as name"
					],
					filters: [
						["File", "attached_to_doctype", "=", this.doctype],
						["File", "attached_to_name", "in", this.get_docname_list()],
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
							me.prepare_images(images);
							me.render();
						}
					}
				}
			});
		} else {
			this.render()
		}
	},

	get_docname_list: function(){
		var names = []
		$.each(cur_list.data, function(idx, doc){
			names.push(doc.name);
		});
		return names
	},

	prepare_images: function(images){
		var me = this;
		this.doc_images = {}

		$.each(images, function(idx, image){
			name = image.name;
			delete image.name;

			_images = me.doc_images[name] || [];
			_images.push(image)

			me.doc_images[name] = _images;
			delete _images;
		});

		this.docnames = $.map(cur_list.data, function(doc, idx){
			if(inList(Object.keys(me.doc_images), doc.name)){
				return doc.name;
			}
		});
	},

	render: function(){
		if(this.docname in this.doc_images){
			this.gallery = blueimp.Gallery(this.doc_images[this.docname], this.get_options());
			this.setup_navigation();
		} else {
			msgprint("No Images found for <b>"+ this.doctype +"</b> : "+ this.docname);
		}
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
		var last_idx = this.docnames.length - 1;

		$.each(this.docnames, function(idx, name){
			if(name == me.docname){
				if(idx == last_idx && args.offset == 1){
					index = 0
				} else if(idx == 0 && args.offset == -1) {
					index = last_idx
				} else {
					index = idx + args.offset
				}
				me.docname = me.docnames[index];
				return false;
			}
		});
		this.gallery.close();
		window.setTimeout(function(){
			me.get_images(me.doctype, me.docname)
		}, 300);
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