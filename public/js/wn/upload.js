// parent, args, callback
wn.upload = {
	make: function(opts) {
		var id = wn.dom.set_unique_id();
		$(opts.parent).append(repl('<iframe id="%(id)s" name="%(id)s" src="blank.html" \
				style="width:0px; height:0px; border:0px"></iframe>\
			<form method="POST" enctype="multipart/form-data" \
				action="%(action)s" target="%(id)s">\
				<input type="file" name="filedata" /><br><br>\
				<input type="submit" class="btn btn-small" value="Upload" />\
			</form>', {
				id: id,
				action: wn.request.url
			}));
	
		opts.args.cmd = 'uploadfile';
		opts.args._id = id;
			
		// add request parameters
		for(key in opts.args) {
			if(opts.args[key]) {
				$('<input type="hidden">')
					.attr('name', key)
					.attr('value', opts.args[key])
					.appendTo($(opts.parent).find('form'));				
			}
		}
		
		$('#' + id).get(0).callback = opts.callback
		
	},
	callback: function(id, file_id, args) {
		$('#' + id).get(0).callback(file_id, args);
	}
}