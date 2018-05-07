import moment from 'moment';
import WebForm from './WebForm';

// frappe.ready(function() {
// 	if (!web_form_settings.is_list) {
// 		frappe.form_dirty = false;
// 		$.extend(frappe, web_form_settings);
// 		moment.defaultFormat = frappe.moment_date_format;

// 		frappe.webform = new WebForm();
// 	}
// })


function render_form() {
	const { web_form_doctype: doctype, doc_name: name, web_form_name } = web_form_settings;

	const wrapper = $(`.page-container[data-path="${web_form_name}"] .webform-wrapper`);

	frappe.call({
		method: 'frappe.website.doctype.web_form.web_form.get_form_data',
		args: { doctype, name, web_form_name }
	}).then(r => {
		const { doc, web_form } = r.message;
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
	if (!web_form_settings.is_list) {
		render_form();
	}

	$('[data-toggle="tooltip"]').tooltip();

	var $form = $("form[data-web-form='"+frappe.web_form_name+"']");

	// allow payment only if
	$('.btn-payment').on('click', function() {
		save(true);
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

	function save(for_payment) {
		if(window.saving)
			return false;
		window.saving = true;
		frappe.form_dirty = false;

		// Data
		// var data = get_data();
		if((!frappe.allow_incomplete || for_payment) && frappe.mandatory_missing.length) {
			window.saving = false;
			// TODO:
			// show_mandatory_missing();
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


