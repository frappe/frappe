wn.pages['data-import-tool'].onload = function(wrapper) { 
	wrapper.app_page = wn.ui.make_app_page({
		parent: wrapper,
		title: "Data Import Tool",
		icon: "data-import-tool"
	});
	
	$(wrapper).find('.layout-main-section').append('<h3>1. Download Template</h3>\
		<div style="min-height: 150px">\
			<p class="help">Download a template for importing a table.</p>\
			<p class="float-column">\
				<select class="form-control" style="width: 200px" name="dit-doctype">\
				</select><br><br>\
				<input type="checkbox" name="dit-with-data" style="margin-top: -3px">\
				<span> Download with data</span>\
			</p>\
			<p class="float-column" id="dit-download"></p>\
		</div>\
		<hr>\
		<h3>2. Import Data</h3>\
		<p class="help">Attach .csv file to import data</p>\
		<div id="dit-upload-area"></div><br>\
		<div class="dit-progress-area" style="display: None"></div>\
		<p id="dit-output"></p>\
		');
		
	$(wrapper).find('.layout-side-section').append('<h4>Help</h4>\
		<p><b>Importing non-English data:</b></p>\
		<p>While uploading non English files ensure that the encoding is UTF-8.</p>\
		<p>Microsoft Excel Users:\
		<ol>\
			<li>In Excel, save the file in CSV (Comma Delimited) format</li>\
			<li>Open this saved file in Notepad</li>\
			<li>Click on File -&gt; Save As</li>\
			<li>File Name: &lt;your filename&gt;.csv<br />\
				Save as type: Text Documents (*.txt)<br />\
				Encoding: UTF-8\
			</li>\
			<li>Click on Save</li>\
		</ol>\
		</p>')
	
	$select = $(wrapper).find('[name="dit-doctype"]');
	
	wn.messages.waiting($(wrapper).find(".dit-progress-area").toggle(false), 
		"Performing hardcore import process....", 100);
	
	// load doctypes
	wn.call({
		method: 'webnotes.core.page.data_import_tool.data_import_tool.get_doctypes',
		callback: function(r) {
			$select.add_options(['Select...'].concat(r.message));
			wrapper.doctypes = r.message;
			wrapper.set_route_options();
		}
	});
	
	wrapper.set_route_options = function() {
		if(wn.route_options
			&& wn.route_options.doctype
			&& in_list(wrapper.doctypes, wn.route_options.doctype)) {
				$select.val(wn.route_options.doctype).change();
				wn.route_options = null;
		}
	}
	
	wrapper.add_template_download_link = function(doctype) {
		return $('<a style="cursor: pointer">')
			.html(doctype)
			.data('doctype', doctype)
			.data('all_doctypes', "No")
			.click(function() {
				window.location.href = repl(wn.request.url 
					+ '?cmd=%(cmd)s&doctype=%(doctype)s'
					+ '&parent_doctype=%(parent_doctype)s'
					+ '&with_data=%(with_data)s'
					+ '&all_doctypes=%(all_doctypes)s',
					{ 
						cmd: 'webnotes.core.page.data_import_tool.data_import_tool.get_template',
						doctype: $(this).data('doctype'),
						parent_doctype: $('[name="dit-doctype"]').val(),
						with_data: $('[name="dit-with-data"]:checked').length ? 'Yes' : 'No',
						all_doctypes: $(this).data('all_doctypes')
					});
			})
			.appendTo('#dit-download');
	}
	
	// load options
	$select.change(function() {
		var val = $(this).val()
		if(val!='Select...') {
			$('#dit-download').empty();
			
			// get options
			return wn.call({
				method: 'webnotes.core.page.data_import_tool.data_import_tool.get_doctype_options',
				args: {doctype: val},
				callback: function(r) {
					$('<h4>Select Template:</h4>').appendTo('#dit-download');
					var with_data = $('[name="dit-with-data"]:checked').length ? 'Yes' : 'No';
					// download link
					$.each(r.message, function(i, v) {
						if(i==0)
							$('<span>Main Table:</span><br>').appendTo('#dit-download');
						if(i==1)
							$('<br><span>Child Tables:</span><br>').appendTo('#dit-download');
							
						wrapper.add_template_download_link(v);
						$('#dit-download').append('<br>');
					});
					
					if(r.message.length > 1) {
						$('<br><span>All Tables (Main + Child Tables):</span><br>').appendTo('#dit-download');
						var link = wrapper
							.add_template_download_link(r.message[0])
							.data('all_doctypes', "Yes")
					}
				}
			})
		}
	});
	
	write_messages = function(r) {
		$(wrapper).find(".dit-progress-area").toggle(false);
		$("#dit-output").empty();

		$.each(r.messages, function(i, v) {
			var $p = $('<p>').html(v).appendTo('#dit-output');
			if(v.substr(0,5)=='Error') {
				$p.css('color', 'red');
			} else if(v.substr(0,8)=='Inserted') {
				$p.css('color', 'green');
			} else if(v.substr(0,7)=='Updated') {
				$p.css('color', 'green');
			} else if(v.substr(0,5)=='Valid') {
				$p.css('color', '#777');
			}
		});
	}
	
	// upload
	wn.upload.make({
		parent: $('#dit-upload-area'),
		args: {
			method: 'webnotes.core.page.data_import_tool.data_import_tool.upload'
		},
		onerror: function(r) {
			r.messages = $.map(r.message.messages, function(v) {
				var msg = v.replace("Inserted", "Valid")
					.replace("Updated", "Valid").split("<");
				if (msg.length > 1) {
					v = msg[0] + (msg[1].split(">").slice(-1)[0]);
				} else {
					v = msg[0];
				}
				return v;
			});
			
			r.messages = ["<h4 style='color:red'>Import Failed!</h4>"]
				.concat(r.messages);
				
			write_messages(r);
		},
		callback: function(fid, filename, r) {
			// replace links if error has occured
			r.messages = ["<h4 style='color:green'>Import Successful!</h4>"].
				concat(r.message.messages)
			
			write_messages(r);
		}
	});
		
	// add overwrite option
	var $submit_btn = $('#dit-upload-area button.btn-upload')
		.html('<i class="icon-upload"></i> ' + wn._("Upload and Import"));
		
	$('<input type="checkbox" name="overwrite" style="margin-top: -3px">\
		<span> Overwrite</span>\
		<p class="help">If you are uploading a child table (for example Item Price), the all the entries of that table will be deleted (for that parent record) and new entries will be made.</p><br>')
		.insertBefore($submit_btn);
	
	// add submit option
	$('<input type="checkbox" name="_submit" style="margin-top: -3px">\
		<span> Submit</span>\
		<p class="help">If you are inserting new records (overwrite not checked) \
			and if you have submit permission, the record will be submitted.</p><br>')
		.insertBefore($submit_btn);

	// add ignore option
	$('<input type="checkbox" name="ignore_encoding_errors" style="margin-top: -3px">\
		<span> Ignore Encoding Errors</span><br><br>')
		.insertBefore($submit_btn);
	
	// rename button
	$('#dit-upload-area button.btn-upload')
		.click(function() {
			$('#dit-output').empty();
			$(wrapper).find(".dit-progress-area").toggle(true);
		});
}

wn.pages['data-import-tool'].onshow = function(wrapper) { 
	wrapper.set_route_options && wrapper.set_route_options();
}