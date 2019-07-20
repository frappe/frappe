frappe.ui.LinkPreview = class {

	constructor() {
		this.popovers_list = [];
		this.LINK_CLASSES = 'a[data-doctype], input[data-fieldtype="Link"], .popover';
		this.popover_timeout = null;
		this.setup_events();
	}

	setup_events() {
		$(document.body).on('mouseover', this.LINK_CLASSES, (e) => {
			this.link_hovered = true;
			this.element = $(e.currentTarget);
			this.is_link = this.element.get(0).tagName.toLowerCase() === 'a';

			if(!this.element.parents().find('.popover').length) {
				this.identify_doc();
				this.popover = this.element.data("bs.popover");
				if(this.name && this.doctype) {
					this.setup_popover_control(e);
				}
			}
		});
		this.handle_popover_hide();

	}

	identify_doc() {
		if (this.is_link) {
			this.doctype = this.element.attr('data-doctype');
			this.name = this.element.attr('data-name');
			this.href = this.element.attr('href');
		} else {
			this.href = this.element.parents('.control-input-wrapper').find('.control-value a').attr('href');
			// input
			this.doctype = this.element.attr('data-target');
			this.name = this.element.val();
		}
	}

	setup_popover_control(e) {
		//If control field value is changed, new popover has to be created
		this.element.on('change',()=> {
			this.new_popover = true;
		});
		if(!this.popover || this.new_popover) {
			this.get_preview_fields().then(preview_fields => {
				if(preview_fields.length) {
					this.data_timeout = setTimeout(() => {
						this.create_popover(e, preview_fields);
					}, 100);
				}
			});
		} else {
			this.popover_timeout = setTimeout(() => {
				if (this.element.is(':focus')) {
					return;
				}
				this.show_popover(e);
			}, 1000);
		}
	}

	create_popover(e, preview_fields) {
		this.new_popover = false;
		if (this.element.is(':focus')) {
			return;
		}

		this.get_preview_fields_value(preview_fields).then((preview_data)=> {
			if(preview_data) {
				if(this.popover_timeout) {
					clearTimeout(this.popover_timeout);
				}

				this.popover_timeout = setTimeout(() => {
					if(this.popover) {
						let new_content = this.get_popover_html(preview_data);
						this.popover.options.content = new_content;
					} else {
						this.init_preview_popover(preview_data);
					}
					this.show_popover(e);

				}, 1000);
			}
		});
	}

	show_popover(e) {

		this.default_timeout = setTimeout(()=> {
			this.clear_all_popovers();
		}, 10000);

		if(!this.is_link) {
			var left = e.pageX;
			this.element.popover('show');
			var width = $('.popover').width();
			$('.control-field-popover').css('left', (left-(width/2)) + 'px');
		} else {
			this.element.popover('show');
		}
	}

	handle_popover_hide() {
		$(document).on('mouseout', this.LINK_CLASSES, () => {
			// To allow popover to be hovered on
			if (!$('.popover:hover').length) {
				this.link_hovered = false;
			}
			if(!this.link_hovered) {
				if(this.data_timeout) {
					clearTimeout(this.data_timeout);
				}
				if (this.popover_timeout) {
					clearTimeout(this.popover_timeout);
				}
				if(this.default_timeout) {
					clearTimeout(this.default_timeout);
				}
				this.clear_all_popovers();
			}
		});

		$(window).on('hashchange', () => {
			this.clear_all_popovers();
		});
	}

	clear_all_popovers() {
		this.popovers_list.forEach($el => $el.hide());
	}

	get_preview_fields() {
		return new Promise((resolve) => {
			let dt = this.doctype;
			let fields = [];
			frappe.model.with_doctype(dt, () => {
				let meta = frappe.get_meta(dt);
				let meta_fields = meta.fields;

				if (!meta.show_preview_popup) {
					// no preview
					resolve([]);
					return;
				}

				meta_fields.filter((field) => {
					// build list of fields to fetch
					if(field.in_preview) {
						fields.push({'name':field.fieldname,'type':field.fieldtype});
					}
				});

				// no preview fields defined, build list from mandatory fields
				if(!fields.length) {
					meta_fields.filter((field) => {
						if(field.reqd) {
							fields.push({'name':field.fieldname,'type':field.fieldtype});
						}
					});
				}
				resolve(fields);
			});
		});
	}

	get_preview_fields_value(field_list) {
		return frappe.xcall('frappe.desk.link_preview.get_preview_data', {
			'doctype': this.doctype,
			'docname': this.name,
			'fields': field_list,
		});
	}

	init_preview_popover(preview_data) {
		let popover_content = this.get_popover_html(preview_data);
		this.element.popover({
			container: 'body',
			html: true,
			content: popover_content,
			trigger: 'manual',
			placement: 'top auto',
			animation: false,
		});

		const $popover = this.element.data('bs.popover').tip();

		$popover.addClass('link-preview-popover');
		$popover.toggleClass('control-field-popover', this.is_link);

		this.popovers_list.push(this.element.data('bs.popover'));

	}

	get_popover_html(preview_data) {
		if(!this.href) {
			this.href = window.location.href;
		}

		if(this.href && this.href.includes(' ')) {
			this.href = this.href.replace(new RegExp(' ', 'g'), '%20');
		}

		let image_html = '';
		let id_html = '';
		let content_html = '';
		let meta = frappe.get_meta(this.doctype);
		let title = preview_data.title;

		if(preview_data[meta.image_field]) {
			let image_url = encodeURI(preview_data[meta.image_field]);
			image_html += `
			<div class="preview-header">
				<img src=${image_url} class="preview-image"></img>
			</div>`;
		}


		if(title && title != preview_data.name) {
			id_html+= `<a class="text-muted" href=${this.href}>${preview_data.name}</a>`;
		}
		if(!title) {
			title = preview_data.name;
		}

		Object.keys(preview_data).forEach(key => {
			if(key!=meta.image_field && key!='name' && key!=meta.title_field) {
				let value = this.truncate_value(preview_data[key]);
				let label = this.truncate_value(frappe.meta.get_label(this.doctype, key));
				content_html += `
				<div class="preview-field">
					<div class='small preview-label text-muted bold'>${label}</div>
					<div class="small preview-value"> ${value} </div>
				</div>
				`;
			}
		});

		content_html = `<div class="preview-table">${content_html}</div>`;

		let popover_content =
			`<div class="preview-popover-header">${image_html}
				<div class="preview-header">
					<div class="preview-main">
						<a class="preview-name bold" href=${this.href}>${title}</a>
						<span class="text-muted small">${this.doctype} ${id_html}</span>
					</div>
				</div>
			</div>
			<hr>
			<div class="popover-body">
				${content_html}
			</div>`;

		return popover_content;
	}

	truncate_value(value) {
		if (value.length > 280) {
			value = value.slice(0,280) + '...';
		}
		return value;
	}

};
