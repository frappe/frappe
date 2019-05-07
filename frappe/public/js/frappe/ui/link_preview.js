frappe.ui.LinkPreview = class {

	constructor() {
		this.$links = [];
		this.popover_timeout = null;
		this.setup_events();
	}

	setup_events() {
		$(document.body).on('mouseover', 'a[data-doctype], input[data-fieldtype="Link"], .popover', (e) => {
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

	}

	identify_doc() {
		if (this.is_link) {
			this.doctype = this.element.attr('data-doctype');
			this.name = this.element.attr('data-name');
		} else {
			// input
			this.doctype = this.element.attr('data-target');
			this.name = this.element.val();
		}
	}

	setup_popover_control(e) {
		if(!this.popover) {
			this.get_preview_fields().then(preview_fields => {
				if(preview_fields.length) {
					this.data_timeout = setTimeout(() => {
						this.create_popover(e, preview_fields);
					}, 100);
				}
			});
		} else {
			this.popover_timeout = setTimeout(() => {
				this.popover.show();
			}, 1000);
		}
		this.handle_popover_hide();
	}

	create_popover(e, preview_fields) {
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

					if(!this.is_link) {
						var left = e.pageX;
						this.element.popover('show');
						var width = $('.popover').width();
						$('.control-field-popover').css('left', (left-(width/2)) + 'px');
					} else {
						this.element.popover('show');
					}

				}, 1000);
			}
		});
	}

	handle_popover_hide() {
		$(document.body).on('mouseout', 'a[href*="/"], input[data-fieldname], .popover', () => {
			this.link_hovered = false;
			if(this.data_timeout) {
				clearTimeout(this.data_timeout);
			}
			if (this.popover_timeout) {
				clearTimeout(this.popover_timeout);
			}
		});

		$(document.body).on('mousemove', () => {
			if (!this.link_hovered) {
				this.$links.forEach($el => $el.popover('hide'));
			}
		});
	}

	get_preview_fields() {
		return new Promise((resolve) => {
			let dt = this.doctype;
			let fields = [];
			frappe.model.with_doctype(dt, () => {
				let meta_fields = frappe.get_meta(dt).fields;
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

		if(!this.is_link) {
			this.element.data('bs.popover').tip().addClass('control-field-popover');
		}

		this.$links.push(this.element);

	}

	get_popover_html(preview_data) {
		if(!this.href) {
			this.href = window.location.href;
		}

		if(this.href && this.href.includes(' ')) {
			this.href = this.href.replace(new RegExp(' ', 'g'), '%20');
		}

		let image_html = '';
		let title_html = '';
		let content_html = `<table class="preview-table">`;

		if(preview_data['image']) {
			let image_url = encodeURI(preview_data['image']);
			image_html += `
			<div class="preview-header">
				<img src=${image_url} class="preview-image"></img>
			</div>`;
		}
		if(preview_data['title']) {
			title_html+= `<a class="preview-title small" href=${this.href}>${preview_data['title']}</a>`;
		}

		Object.keys(preview_data).forEach(key => {
			if(key!='image' && key!='name') {
				let value = this.truncate_value(preview_data[key]);
				let label = this.truncate_value(frappe.meta.get_label(this.doctype, key));
				content_html += `
				<tr class="preview-field">
					<td class='text-muted small field-name'>${label}</td>
					<td class="field-value small"> ${value} </td>
				</tr>
				`;
			}
		});
		content_html+=`</table>`;

		let popover_content =
			`<div class="preview-popover-header">${image_html}
				<div class="preview-header">
					<div class="preview-main">
						<a class="preview-name text-bold" href=${this.href}>${preview_data['name']}</a>
						${title_html}
						<span class="text-muted small">${this.doctype}</span>
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
		if (value.length > 100) {
			value = value.slice(0,100) + '...';
		}
		return value;
	}

};
