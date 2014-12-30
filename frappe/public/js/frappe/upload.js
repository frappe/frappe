// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// parent, args, callback
frappe.upload = {
	make: function(opts) {
		if(!opts.args) opts.args = {};
		var $upload = $(frappe.render_template("upload", {opts:opts})).appendTo(opts.parent);

		$upload.find(".attach-as-link").click(function() {
			var as_link = $(this).prop("checked");

			$upload.find(".input-link").toggleClass("hide", !as_link);
			$upload.find(".input-upload").toggleClass("hide", as_link);
		});

		if(!opts.btn) {
			opts.btn = $('<button class="btn btn-default btn-sm">' + __("Attach")
				+ '</div>').appendTo($upload);
		}

		// get the first file
		opts.btn.click(function() {
			// convert functions to values
			for(key in opts.args) {
				if(typeof val==="function")
					opt.args[key] = opts.args[key]();
			}

			// add other inputs in the div as arguments
			opts.args.params = {};
			$upload.find("input[name]").each(function() {
				var key = $(this).attr("name");
				var type = $(this).attr("type");
				if(key!="filedata" && key!="file_url") {
					if(type === "checkbox") {
						opts.args.params[key] = $(this).is(":checked");
					} else {
						opts.args.params[key] = $(this).val();
					}
				}
			})

			opts.args.file_url = $upload.find('[name="file_url"]').val();

			var fileobj = $upload.find(":file").get(0).files[0];
			frappe.upload.upload_file(fileobj, opts.args, opts);
		})
	},
	upload_file: function(fileobj, args, opts) {
		if(!fileobj && !args.file_url) {
			msgprint(__("Please attach a file or set a URL"));
			return;
		}

		var dataurl = null;
		var _upload_file = function() {
			if(opts.on_attach) {
				opts.on_attach(args, dataurl)
			} else {
				var msgbox = msgprint(__("Uploading..."));
				return frappe.call({
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
					}
				});
			}
		}

		if(args.file_url) {
			_upload_file();
		} else {
			var freader = new FileReader();

			freader.onload = function() {
				args.filename = fileobj.name;
				if((opts.max_width || opts.max_height) && (/\.(gif|jpg|jpeg|tiff|png)$/i).test(args.filename)) {
					frappe.utils.resize_image(freader, function(_dataurl) {
						dataurl = _dataurl;
						args.filedata = _dataurl.split(",")[1];
						console.log("resized!")
						_upload_file();
					})
				} else {
					dataurl = freader.result;
					args.filedata = freader.result.split(",")[1];
					_upload_file();
				}
			};

			freader.readAsDataURL(fileobj);
		}
	}
}
