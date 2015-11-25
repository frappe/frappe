// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// parent, args, callback
frappe.upload = {
	make: function(opts) {
		if(!opts.args) opts.args = {};
		var $upload = $(frappe.render_template("upload", {opts:opts})).appendTo(opts.parent);
		var $file_input = $upload.find(".input-upload-file");

		// bind pseudo browse button
		$upload.find(".btn-browse").on("click",
			function() { $file_input.click(); });

		$file_input.on("change", function() {
			if (this.files.length > 0) {
				$upload.find(".web-link-wrapper").addClass("hidden");

				var $uploaded_file_display = $(repl('<div class="btn-group" role="group">\
					<button type="button" class="btn btn-default btn-sm \
						text-ellipsis uploaded-filename-display">%(filename)s\
					</button>\
					<button type="button" class="btn btn-default btn-sm uploaded-file-remove">\
						&times;</button>\
				</div>', {filename: this.files[0].name}))
				.appendTo($upload.find(".uploaded-filename").removeClass("hidden").empty());

				$uploaded_file_display.find(".uploaded-filename-display").on("click", function() {
					$file_input.click();
				});

				$uploaded_file_display.find(".uploaded-file-remove").on("click", function() {
					$file_input.val("");
					$file_input.trigger("change");
				});

				if(opts.on_select) {
					opts.on_select();
				}

			} else {
				$upload.find(".uploaded-filename").addClass("hidden")
				$upload.find(".web-link-wrapper").removeClass("hidden");
			}
		});


		if(!opts.btn) {
			opts.btn = $('<button class="btn btn-default btn-sm">' + __("Attach")
				+ '</div>').appendTo($upload);
		} else {
			$(opts.btn).unbind("click");
		}

		// get the first file
		opts.btn.click(function() {
			// convert functions to values

			if(opts.get_params) {
				opts.args.params = opts.get_params();
			}

			opts.args.file_url = $upload.find('[name="file_url"]').val();

			var fileobj = $upload.find(":file").get(0).files[0];
			frappe.upload.upload_file(fileobj, opts.args, opts);
		});
	},
	upload_file: function(fileobj, args, opts) {
		if(!fileobj && !args.file_url) {
			if(opts.on_no_attach) {
				opts.on_no_attach();
			} else {
				msgprint(__("Please attach a file or set a URL"));
			}
			return;
		}

		var dataurl = null;
		var _upload_file = function() {
			if (args.file_size) {
				frappe.upload.validate_max_file_size(args.file_size);
			}

			if(opts.on_attach) {
				opts.on_attach(args, dataurl)
			} else {
				var msgbox = msgprint(__("Uploading..."));
				if(opts.start) {
					opts.start();
				}
				ajax_args = {
					"method": "uploadfile",
					args: args,
					callback: function(r) {
						if(!r._server_messages)
							msgbox.hide();
						if(r.exc) {
							// if no onerror, assume callback will handle errors
							opts.onerror ? opts.onerror(r) : opts.callback(null, null, r);
							return;
						}
						var attachment = r.message;
						opts.callback(attachment, r);
						$(document).trigger("upload_complete", attachment);
					},
					error: function(r) {
						// if no onerror, assume callback will handle errors
						opts.onerror ? opts.onerror(r) : opts.callback(null, null, r);
						return;
					}
				}

				// copy handlers etc from opts
				$.each(['queued', 'running', "progress", "always", "btn"], function(i, key) {
					if(opts[key]) ajax_args[key] = opts[key];
				});
				return frappe.call(ajax_args);
			}
		}

		if(args.file_url) {
			_upload_file();
		} else {
			var freader = new FileReader();

			freader.onload = function() {
				args.filename = fileobj.name;
				if(opts.options && opts.options.toLowerCase()=="image") {
					if(!frappe.utils.is_image_file(args.filename)) {
						msgprint(__("Only image extensions (.gif, .jpg, .jpeg, .tiff, .png, .svg) allowed"));
						return;
					}
				}

				if((opts.max_width || opts.max_height) && frappe.utils.is_image_file(args.filename)) {
					frappe.utils.resize_image(freader, function(_dataurl) {
						dataurl = _dataurl;
						args.filedata = _dataurl.split(",")[1];
						args.file_size = Math.round(args.filedata.length * 3 / 4);
						console.log("resized!")
						_upload_file();
					})
				} else {
					dataurl = freader.result;
					args.filedata = freader.result.split(",")[1];
					args.file_size = fileobj.size;
					_upload_file();
				}
			};

			freader.readAsDataURL(fileobj);
		}
	},
	get_string: function(dataURI) {
		// remove filename
		var parts = dataURI.split(',');
		if(parts[0].indexOf(":")===-1) {
			var a = parts[2];
		} else {
			var a = parts[1];
		}

		return decodeURIComponent(escape(atob(a)));

	},

	validate_max_file_size: function(file_size) {
		var max_file_size = frappe.boot.max_file_size || 5242880;

		if (file_size > max_file_size) {
			// validate max file size
			frappe.throw(__("File size exceeded the maximum allowed size of {0} MB", [max_file_size / 1048576]));
		}
	}
}

