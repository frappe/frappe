// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// parent, args, callback
wn.upload = {
	make: function(opts) {
		if(!opts.args) opts.args = {};
		var $upload = $('<div class="file-upload">\
			<p class="small"><a class="action-attach disabled" href="#"><i class="icon-upload"></i> ' 
				+ wn._('Upload a file') + '</a> | <a class="action-link" href="#"><i class="icon-link"></i> '
				 + wn._('Attach as web link') + '</a></p>\
			<div class="action-attach-input">\
				<input class="alert alert-info" style="padding: 7px; margin: 7px 0px;" type="file" name="filedata" />\
			</div>\
			<div class="action-link-input" style="display: none; margin-top: 7px;">\
				<input class="form-control" style="max-width: 300px;" type="text" name="file_url" />\
				<p class="text-muted">' 
					+ (opts.sample_url || 'e.g. http://example.com/somefile.png') + 
				'</p>\
			</div>\
			<button class="btn btn-info btn-upload"><i class="icon-upload"></i> ' +wn._('Upload')
				+'</button></div>').appendTo(opts.parent);
	

		$upload.find(".action-link").click(function() {
			$upload.find(".action-attach").removeClass("disabled");
			$upload.find(".action-link").addClass("disabled");
			$upload.find(".action-attach-input").toggle(false);
			$upload.find(".action-link-input").toggle(true);
			$upload.find(".btn-upload").html('<i class="icon-link"></i> ' +wn._('Set Link'))
			return false;
		})

		$upload.find(".action-attach").click(function() {
			$upload.find(".action-link").removeClass("disabled");
			$upload.find(".action-attach").addClass("disabled");
			$upload.find(".action-link-input").toggle(false);
			$upload.find(".action-attach-input").toggle(true);
			$upload.find(".btn-upload").html('<i class="icon-upload"></i> ' +wn._('Upload'))
			return false;
		})

		// get the first file
		$upload.find(".btn-upload").click(function() {
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
			wn.upload.upload_file(fileobj, opts.args, opts);
		})
	},
	upload_file: function(fileobj, args, opts) {
		if(!fileobj && !args.file_url) {
			msgprint(wn._("Please attach a file or set a URL"));
			return;
		}
		
		var dataurl = null;
		var _upload_file = function() {
			if(opts.on_attach) {
				opts.on_attach(args, dataurl)
			} else {
				var msgbox = msgprint(wn._("Uploading..."));
				return wn.call({
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
						opts.callback(r.message.fid, r.message.filename, r);
						$(document).trigger("upload_complete", 
							[r.message.fid, r.message.filename]);
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
					wn.utils.resize_image(freader, function(_dataurl) {
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