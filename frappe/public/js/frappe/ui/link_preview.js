frappe.ui.LinkPreview = class {

	constructor() {
		this.$links = [];
		this.popover_timeout = null;
		this.get_links();
	}

	get_links() {

		$(document.body).on('mouseover', 'a[href*="/"], input[data-fieldname], .popover', (e) => {
			this.link_hovered = true;
			let element = $(e.currentTarget);
			let name, doctype, link;
			let is_link = true;

			if(!element.parents().find('.popover').length) {
				if(element.attr('href')) {
					link = element.attr('href');
					let details = this.get_details(link,element);
					name = details.name;
					doctype = details.doctype;
				} else {
					is_link = false;
					link = element.parents('.control-input-wrapper').find('.control-value').children('a').attr('href');

					if(link) {
						let details = this.get_details(link,element);
						name = details.name;
						doctype = details.doctype;
					} else {
						name = element.parent().next().text();
						doctype = element.attr('data-doctype');
					}
				}

				let popover = element.data("bs.popover");
				if(name && doctype) {
					this.setup_popover_control(e, popover, name, doctype, element, is_link, link);
				}
			}
		});

	}

	get_details(link, element) {
		let details = {};
		let link_arr = link.split('/');

		if(link_arr.length > 2) {
			details.name = decodeURI(link_arr[link_arr.length - 1]);
			details.doctype = decodeURI(link_arr[link_arr.length -2]);
			details.name = details.name.replace(new RegExp('%2F', 'g'), '/');
		}
		let title = element.attr('title');
		if( title && title.includes('/')) {
			details.name = title.trim();
			details.doctype = decodeURI(link_arr[link_arr.length-3]);
		}
		return details;
	}


	setup_popover_control(e, popover, name, doctype, $el, is_link, link) {

		if(!popover || !is_link) {
			let preview_fields = this.get_preview_fields(doctype);
			if(preview_fields.length) {
				this.data_timeout = setTimeout(() => {
					this.get_preview_fields_value(doctype, name, preview_fields).then((preview_data)=> {
						if(preview_data) {
							if(this.popover_timeout) {
								clearTimeout(this.popover_timeout);
							}

							this.popover_timeout = setTimeout(() => {

								if(popover) {
									let new_content = this.get_popover_html(preview_data, doctype, link);
									popover.options.content = new_content;
								} else {
									this.init_preview_popover($el, preview_data, doctype, is_link, link);
								}

								if(!is_link) {
									var left = e.pageX;
									$el.popover('show');
									var width =$('.popover').width();
									$('.control-field-popover').css('left', (left-(width/2)) + 'px');
								} else {
									$el.popover('show');
								}

							}, 1000);
						}
					});
				}, 1000);
			}
		} else {
			this.popover_timeout = setTimeout(() => {
				popover.show();
			}, 1000);
		}

		this.handle_popover_hide();
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

	get_preview_fields(dt) {
		let fields = [];
		frappe.model.with_doctype(dt, () => {
			frappe.get_meta(dt).fields.filter((field) => {
				if(field.in_preview) {
					fields.push({'name':field.fieldname,'type':field.fieldtype});
				}
			});
		});

		if(!fields.length) {
			frappe.model.with_doctype(dt, () => {
				frappe.get_meta(dt).fields.filter((field) => {
					if(field.reqd) {
						fields.push({'name':field.fieldname,'type':field.fieldtype});
					}
				});
			});
		}
		return fields;
	}

	get_preview_fields_value(dt, field_name, field_list) {
		return frappe.xcall('frappe.desk.link_preview.get_preview_data', {
			'doctype': dt,
			'docname': field_name,
			'fields': field_list,
		});
	}

	init_preview_popover($el, preview_data, dt, is_link, link) {

		let popover_content = this.get_popover_html(preview_data, dt, link);
		$el.popover({
			container: 'body',
			html: true,
			content: popover_content,
			trigger: 'manual',
			placement: 'top auto',
			animation: false,
		});

		if(!is_link) {
			$el.data('bs.popover').tip().addClass('control-field-popover');
		}

		this.$links.push($el);

	}

	get_popover_html(preview_data, dt, link) {
		if(!link) {
			link = window.location.href;
		}

		if(link && link.includes(' ')) {
			link = link.replace(new RegExp(' ', 'g'), '%20');
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
			title_html+= `<a class="preview-title small" href=${link}>${preview_data['title']}</a>`;
		}

		Object.keys(preview_data).forEach(key => {
			if(key!='image' && key!='name') {
				let value = this.truncate_value(preview_data[key]);            
				let label = this.truncate_value(frappe.meta.get_label(dt, key));
				content_html += `
				<tr class="preview-field">
					<td class='text-muted small field-name'>${label}</td> 
					<td class="field-value small"> ${value} </td>
				</tr>
				`;
			}
		});
		content_html+=`</table>`;

		let popover_content = `<div class="preview-popover-header">
									${image_html}
									<div class="preview-header">
										<div class="preview-main">
											<a class="preview-name text-bold" href=${link}>${preview_data['name']}</a>
											${title_html}
											<span class="text-muted small">${dt}</span>
										</div>
									</div>
								</div>
								<hr>
								<div class="popover-body">
									${content_html}
								</div>`;

		if(!link) {
			$('.preview-name').removeAttr('href');
			$('.preview-title').removeAttr('href');
		}

		return popover_content;
	}

	truncate_value(value) {
		if (value.length > 100) {
			value = value.slice(0,100) + '...';
		}
		return value;
	}

};
