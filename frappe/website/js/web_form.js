import WebForm from './webform';

frappe.ready(function() {
	if(web_form_settings.is_list) return;

	frappe.form_dirty = false;
	$.extend(frappe, web_form_settings);
	moment.defaultFormat = frappe.moment_date_format;
	$('[data-toggle="tooltip"]').tooltip();

	const { web_form_doctype: doctype, doc_name: docname, web_form_name } = web_form_settings;
	const wrapper = $(`.webform-wrapper`);
	var $form = $("div[data-web-form='"+frappe.web_form_name+"']");

	// :( Needed by core model, meta and perm, all now included in th website js
	// One of the few non-touchy options
	frappe.boot.user = {
		can_read: '', can_write: '', can_create: ''
	};

	frappe.web_form = new WebForm({
		wrapper: wrapper,
		doctype: doctype,
		docname: docname,
		web_form_name: web_form_name,
		allow_incomplete: frappe.allow_incomplete
	});

	// allow payment only if
	$('.btn-payment').on('click', function() {
		save(frappe.web_form.get_values(), true);
		return false;
	});

	// submit
	$(".btn-form-submit").on("click", function() {
		let data = frappe.web_form.get_values();
		save(data);
		return false;
	});

	// change section
	$('.btn-change-section, .slide-progress .fa-fw').on('click', function() {
		var idx = $(this).attr('data-idx');
		if(!frappe.form_dirty || frappe.is_read_only) {
			show_slide(idx);
		} else {
			let data = frappe.web_form.get_values();
			if(save(data)!==false) {
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

	function save(data, for_payment) {
		if(!data) return;
		if(window.saving)
			return false;
		window.saving = true;
		frappe.form_dirty = false;

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

					if(frappe.is_new) {
						show_success_message();
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


