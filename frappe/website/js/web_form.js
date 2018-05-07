import moment from 'moment';

function render_form() {
	const { web_form_doctype: doctype, doc_name: name, web_form_name } = web_form_settings;

	const wrapper = $(`.page-container[data-path="${web_form_name}"] .webform-wrapper`);

	frappe.call({
		method: 'frappe.website.doctype.web_form.web_form.get_form_data',
		args: { doctype, name, web_form_name }
	}).then(r => {
		const { doc, web_form } = r.message;
		// console.log(web_form);
		render_form(doc, web_form);
	});

	function render_form(doc, web_form) {

		const fields = web_form.web_form_fields.map(df => {
			if (df.fieldtype === 'Link') {
				df.fieldtype = 'Select';
			}

			delete df.parent;
			delete df.parentfield;
			delete df.parenttype;
			delete df.doctype;

			return df;
		});

		const fieldGroup = new frappe.ui.FieldGroup({
			parent: wrapper,
			fields: web_form.web_form_fields
		});

		fieldGroup.make();

		fieldGroup.set_values(doc);

		// submit
		$(".btn-form-submit").on("click", function() {
			// let values = fieldGroup.get_values();
			// save(values);
			return false;
		});
	}
}

frappe.ready(function() {
	if (web_form_settings.is_list) {
		render_list();
	} else {
		render_form();
	}

	frappe.file_reading = false;
	frappe.form_dirty = false;

	$.extend(frappe, web_form_settings);
	moment.defaultFormat = frappe.moment_date_format;

	$('[data-toggle="tooltip"]').tooltip();

	var $form = $("form[data-web-form='"+frappe.web_form_name+"']");

	// var d = new frappe.ui.Dialog ({
	// 	title: __("Relink"),
	// 	fields: [{
	// 		"fieldtype": "MultiSelect",
	// 		"options": ["DocType"],
	// 		"reqd": 1,
	// 		"label": __("Reference Doctype"),
	// 		"fieldname": "reference_doctype",
	// 	},
	// 	{
	// 		"fieldtype": "Link",
	// 		"options": "reference_doctype",
	// 		"label": __("Reference Name"),
	// 		"fieldname": "reference_name"
	// 	}]
	// });
	// d.set_primary_action(__("Relink"), function () {});
	// d.show();

	// read file attachment
	$form.on("change", "[type='file']", function() {
		var $input = $(this);
		if($input.attr("type")==="file") {
			var input = $input.get(0);
			var reader = new FileReader();

			if(input.files.length) {
				var file = input.files[0];
				frappe.file_reading = true;
				reader.onload = function() {
					input.filedata = {
						"__file_attachment": 1,
						"filename": file.name,
						"dataurl": reader.result
					};

					if(input.filedata.dataurl.length >
						(frappe.max_attachment_size * 1024 * 1024)) {
						frappe.msgprint(__('Max file size allowed is {0}MB',
							[frappe.max_attachment_size]));
						input.filedata = null;

						// clear attachment
						$(input).val('');
						$(input).attr('data-value', '');
					}
					frappe.file_reading = false;
				};

				reader.readAsDataURL(file);
			}
		}
	});

	// show mandatory fields as red
	$('.form-group input, .form-group textarea, .form-group select').on('keypress', function() {
		// validate maxlength
		var maxlength = parseInt($(this).attr('maxlength'));
		if(maxlength && (($(this).val() || '') + '').length > maxlength-1) {
			$(this).val($(this).val().substr(0, maxlength-1));
		}
	});

	// if changed, set dirty flag
	$form.on('change', function() {
		frappe.form_dirty = true;
	});

	$form.on('submit', function() {
		return false;
	});

	// allow payment only if
	$('.btn-payment').on('click', function() {
		save(true);
		return false;
	});

	// change attach
	$form.on("click", ".change-attach", function() {
		var input_wrapper = $(this).parent().addClass("hide")
			.parent().find(".attach-input-wrap").removeClass("hide");

		input_wrapper.find('input').val('').attr('data-value', '');

		frappe.form_dirty = true;

		return false;
	});

	// change section
	$('.btn-change-section, .slide-progress .fa-fw').on('click', function() {
		var idx = $(this).attr('data-idx');
		if(!frappe.form_dirty || frappe.is_read_only) {
			show_slide(idx);
		} else {
			if(save()!==false) {
				show_slide(idx);
			}
		}
		return false;
	});

	var show_slide = function(idx) {
		// hide all sections
		$('.web-form-page').addClass('hidden');

		// slide-progress
		$('.slide-progress .fa-circle')
			.removeClass('fa-circle').addClass('fa-circle-o');
		$('.slide-progress .fa-fw[data-idx="'+idx+'"]')
			.removeClass('fa-circle-o').addClass('fa-circle');

		// un hide target section
		$('.web-form-page[data-idx="'+idx+'"]')
			.removeClass('hidden')
			.find(':input:first').focus();

	};

	// add row
	$('.btn-add-row').on('click', function() {
		var fieldname = $(this).attr('data-fieldname');
		var grid = $('.web-form-grid[data-fieldname="'+fieldname+'"]');
		var new_row = grid.find('.web-form-grid-row.hidden').clone()
			.appendTo(grid.find('tbody'))
			.attr('data-name', '')
			.removeClass('hidden');
		new_row.find('input').each(function() {
			$(this)
				.val($(this).attr('data-default') || "")
				.removeClass('hasDatepicker')
				.attr('id', '');
		});
		setup_date_picker(new_row);
		return false;
	});

	// remove row
	$('.web-form-grid').on('click', '.btn-remove', function() {
		$(this).parents('.web-form-grid-row:first').addClass('hidden').remove();
		frappe.form_dirty = true;
		return false;
	});

	// get document data
	var get_data = function() {
		frappe.mandatory_missing_in_last_doc = [];

		var doc = get_data_for_doctype($form, frappe.web_form_doctype);
		doc.doctype = frappe.web_form_doctype;
		if(frappe.doc_name) {
			doc.name = frappe.doc_name;
		}
		frappe.mandatory_missing = frappe.mandatory_missing_in_last_doc;

		// get data from child tables
		$('.web-form-grid').each(function() {
			var fieldname = $(this).attr('data-fieldname');
			var doctype = $(this).attr('data-doctype');
			doc[fieldname] = [];

			// get data from each row
			$(this).find('[data-child-row=1]').each(function() {
				if(!$(this).hasClass('hidden')) {
					frappe.mandatory_missing_in_last_doc = [];
					var d = get_data_for_doctype($(this), doctype);

					// set name of child record (if set)
					var name = $(this).attr('data-name');
					if(name) {
						d.name = name;
					}

					// check if child table has value
					var has_value = false;
					for(var key in d) {
						if(typeof d[key]==='string') {
							d[key] = d[key].trim();
						}
						if(d[key] !== null && d[key] !== undefined && d[key] !== '') {
							has_value = true;
							break;
						}
					}

					// only add if any value is set
					if(has_value) {
						doc[fieldname].push(d);
						frappe.mandatory_missing =
							frappe.mandatory_missing.concat(frappe.mandatory_missing_in_last_doc);
					}
				}
			});
		});

		return doc;
	};

	// get data from input elements
	// for the given doctype
	var get_data_for_doctype = function(parent, doctype) {
		var out = {};
		parent.find("[name][data-doctype='"+ doctype +"']").each(function() {
			var $input = $(this);
			var input_type = $input.attr("data-fieldtype");
			var no_attachment = false;
			var val;
			if(input_type==="Attach") {
				// save filedata dict as value
				if($input.get(0).filedata) {
					val = $input.get(0).filedata;
				} else {
					// original value
					val = $input.attr('data-value');
					if (!val) {
						val = {'__no_attachment': 1};
						no_attachment = true;
					}
				}
			} else if(input_type==='Text Editor') {
				val = $input.parent().find('.note-editable').html();
			} else if(input_type==="Check") {
				val = $input.prop("checked") ? 1 : 0;
			} else if(input_type==="Date") {
				// convert from user format to YYYY-MM-DD
				if($input.val()) {
					val = moment($input.val(), moment.defaultFormat).format('YYYY-MM-DD');
				} else {
					val = null;
				}
			} else {
				val = $input.val();
			}

			if(typeof val==='string') {
				val = val.trim();
			}

			if($input.attr("data-reqd")
				&& (val===undefined || val===null || val==='' || no_attachment)) {
				frappe.mandatory_missing_in_last_doc.push([$input.attr("data-label"),
					$input.parents('.web-form-page:first').attr('data-label')]);
			}

			out[$input.attr("name")] = val;
		});
		return out;
	};

	function save(for_payment) {
		if(window.saving)
			return false;
		window.saving = true;
		frappe.form_dirty = false;

		if(frappe.file_reading) {
			window.saving = false;
			frappe.msgprint(__("Uploading files please wait for a few seconds."));
			return false;
		}

		var data = get_data();
		if((!frappe.allow_incomplete || for_payment) && frappe.mandatory_missing.length) {
			window.saving = false;
			show_mandatory_missing();
			return false;
		}

		frappe.call({
			type: "POST",
			method: "frappe.website.doctype.web_form.web_form.accept",
			args: {
				data: data,
				web_form: frappe.web_form_name,
				for_payment: for_payment
			},
			freeze: true,
			btn: $form.find("[type='submit']"),
			callback: function(data) {
				if(!data.exc) {
					frappe.doc_name = data.message;
					if(!frappe.login_required) {
						show_success_message();
					}

					if(frappe.is_new && frappe.login_required) {
						// reload page (with ID)
						window.location.href = window.location.pathname + "?name=" + frappe.doc_name;
					}

					if(for_payment && data.message) {
						// redirect to payment
						window.location.href = data.message;
					}
				} else {
					frappe.msgprint(__('There were errors. Please report this.'));
				}
			},
			always: function() {
				window.saving = false;
			}
		});
		return true;
	}

	function show_success_message() {
		$form.addClass("hide");
		$(".comments, .introduction, .page-head").addClass("hide");
		scroll(0, 0);
		set_message(frappe.success_link, true);
	}

	function show_mandatory_missing() {
		var text = [], last_section = null;
		frappe.mandatory_missing.forEach(function(d) {
			if(last_section != d[1]) {
				text.push('');
				text.push(d[1].bold());
				last_section = d[1];
			}
			text.push(d[0]);
		});
		frappe.msgprint(__('The following mandatory fields must be filled:<br>')
			+ text.join('<br>'));
	}

	function set_message(msg, permanent) {
		$(".form-message")
			.html(msg)
			.removeClass("hide");

		if(!permanent) {
			setTimeout(function() {
				$(".form-message").addClass('hide');
			}, 5000);
		}
	}

	// close button
	$(".close").on("click", function() {
		var name = $(this).attr("data-name");
		if(name) {
			frappe.call({
				type:"POST",
				method: "frappe.website.doctype.web_form.web_form.delete",
				args: {
					"web_form": frappe.web_form_name,
					"name": name
				},
				callback: function(r) {
					if(!r.exc) {
						location.reload();
					}
				}
			});
		}
	});
});

function render_list() {
	const { web_form_doctype, web_form_name } = web_form_settings;

	const wrapper = $(`.page-container[data-path="${web_form_name}"] .page-content`);

	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: web_form_doctype,
			fields: ['name'],
			filters: { 'owner': frappe.session.user }
		}
	}).then(r => {
		const list = r.message || [];
		render_list_view(list);
	});

	function render_list_view(list) {
		const html = list.map(get_list_row_html).join('');
		wrapper.html(`
			<div class="page-head">
				<h1>${web_form_doctype}</h1>
			</div>
			<div class="page_content">${html}</div>
		`);
	}

	function get_list_row_html(row) {
		return `
			<a href="${web_form_name}?name=${row.name}">
			<div class="row padding border-bottom">
				<div class="col-sm-4">${row.name}</div>
			</div>
			</a>
		`;
	}
}
