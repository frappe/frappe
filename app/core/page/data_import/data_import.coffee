# File importer
class DataImport
	constructor: ->
		new PageHeader $('#data_importer .head').get(0), 'Import Data'
		new Uploader $('#upload_form').get(0),  {cmd: 'core.page.data_import.data_import.upload'}, 
			pscript.check_upload

	upload_done: (@first_row) =>
		@show_table_select
		
	show_table_select: () ->
		# show the table selector
		$ds $('#data_importer .box').get(1)
		
		# set select options
		s = $i 'import_table_select'
		add_sel_options s, add_lists([''], session.can_read)
		$(s).change ->
			@load_doctype sel_val(s)
	
	# load doctype and make column selectors
	load_doctype: () ->
		
		

# Uploader Object
class ColumnSelect
	
pscript['onload_data-import'] = ->
	pscript.data_import = new DataImport()
	
pscript.upload_done = (first_row) ->
	$ds $('#data_importer .box').get(1)
	
	# load table slect
	s = $i 'import_table_select'
	add_sel_options s, add_lists([''], session.can_read)
	$(s).change ->
		
	
	msgprint first_row
	