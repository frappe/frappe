wn.pages['data-import-tool'].onload = function(wrapper) { 
	wrapper.app_page = wn.ui.make_app_page({
		parent: wrapper,
		title: "Data Import Tool"
	});
	
	$(wrapper).find('.layout-main-section').append('<h3>1. Download Template</h3>\
		<div style="min-height: 150px">\
			<p class="help">Download a template for importing a table.</p>\
			<p class="float-column">\
				<select style="width: 200px" name="dit-doctype">\
				</select><br><br>\
				<input type="checkbox" name="dit-with-data">\
				<span> Download with data</span>\
			</p>\
			<p class="float-column" id="dit-download"></p>\
		</div>\
		<hr>\
		<h3>2. Import Data</h3>\
		<p class="help">Attach .csv file to import data</p>\
		<div id="dit-upload-area"></div><br>\
		<p id="dit-output"></p>\
		');
		
	$(wrapper).find('.layout-side-section').append('<h4>Help</h4><br>\
		<p><b>Date Format:</b></p>\
		<p>Dates must be in format "YYYY-MM-DD", for example, \
			31st Jan 2012 must be "2012-01-31"</p>\
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
	
	// load doctypes
	wn.call({
		method:'core.page.data_import_tool.data_import_tool.get_doctypes',
		callback: function(r) {
			$select.add_options(['Select...'].concat(r.message));
		}
	});
	
	// load options
	$select.change(function() {
		var val = $(this).val()
		if(val!='Select...') {
			$('#dit-download').empty();
			
			// get options
			wn.call({
				method:'core.page.data_import_tool.data_import_tool.get_doctype_options',
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
						$('<a style="cursor: pointer">')
							.html(v)
							.data('doctype', v)
							.click(function() {
								window.location.href = repl(wn.request.url 
									+ '?cmd=%(cmd)s&doctype=%(doctype)s'
									+ '&parent_doctype=%(parent_doctype)s&with_data=%(with_data)s',
									{ 
										cmd: 'core.page.data_import_tool.data_import_tool.get_template',
										doctype: $(this).data('doctype'),
										parent_doctype: $('[name="dit-doctype"]').val(),
										with_data: $('[name="dit-with-data"]:checked').length ? 'Yes' : 'No'
									});
							})
							.appendTo('#dit-download');
						$('#dit-download').append('<br>');
					})
				}
			})
		}
	});
	
	// upload
	wn.upload.make({
		parent: $('#dit-upload-area'),
		args: {
			method: 'core.page.data_import_tool.data_import_tool.upload'
		},
		callback: function(r) {
			$('#dit-output').empty();
			
			$.each(r, function(i, v) {
				var $p = $('<p>').html(v).appendTo('#dit-output');
				if(v.substr(0,5)=='Error') {
					$p.css('color', 'red');
				}
				if(v.substr(0,8)=='Inserted') {
					$p.css('color', 'green');
				}
				if(v.substr(0,7)=='Updated') {
					$p.css('color', 'green');
				}
			});
			
		}
	});
	
	// add overwrite option
	$('<input type="checkbox" name="overwrite"><span> Overwrite</span><br><br>')
		.insertBefore('#dit-upload-area form input[type="submit"]')

	// add ignore option
	$('<input type="checkbox" name="ignore_encoding_errors"><span> Ignore Encoding Errors</span><br><br>')
		.insertBefore('#dit-upload-area form input[type="submit"]')


	// add overwrite option
	$('<span>Date Format: </span><select name="date_format"></select><br><br>')
		.insertBefore('#dit-upload-area form input[type="submit"]')
	
	$('#dit-upload-area select').add_options(['dd/mm/yyyy', 'mm/dd/yyyy', 'yyyy-mm-dd'])

	
	// rename button
	$('#dit-upload-area form input[type="submit"]')
		.attr('value', 'Upload and Import')
		.click(function() {
			$('#dit-output').html('Performing hardcore import process....')
		});
}