wn.pages['data-import-tool'].onload = function(wrapper) { 
	wrapper.app_page = wn.ui.make_app_page({
		parent: wrapper,
		title: "Data Import Tool"
	});
	
	$(wrapper).find('.layout-main-section').append('<h3>1. Download Template</h3>\
		<div style="min-height: 150px">\
			<p class="help">Download a template for importing a table</p>\
			<p class="float-column"><select style="width: 200px" name="dit-doctype">\
				</select></p>\
			<p class="float-column dit-download"></p>\
		</div>\
		<hr>\
		<h3>2. Import Data</h3>\
		<p class="help">Attach file to import data</p>\
		<div id="dit-upload-area"></div><br>\
		<p id="dit-output"></p>\
		');
	
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
			$('.dit-download').empty();
			
			// get options
			wn.call({
				method:'core.page.data_import_tool.data_import_tool.get_doctype_options',
				args: {doctype: val},
				callback: function(r) {
					$('<h4>Select Template:</h4>').appendTo('.dit-download');

					// download link
					$.each(r.message, function(i, v) {
						$('<a href="index.cgi?cmd=core.page.data_import_tool.data_import_tool.get_template&doctype='
							+v+'&parent_doctype='+val+'">'+v+'</a><br>')
							.appendTo('.dit-download');
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
			});
			
		}
	});
}