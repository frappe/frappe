class ImportSection
	render: (label, description, hidden) ->
		@wrapper = $a $('#data_importer .body').get(0), 'div', 'box round'
		@head = $a @wrapper, 'h3', 'head', null, label
		$a @wrapper, 'div', 'comment', null, description 
		@body = $a @wrapper, 'div'
		if hidden
			$dh @wrapper

class Uploader extends ImportSection
	constructor: ->
		@render('Step 1: Upload A File', 'Upload a file in ".csv" format. <ol>
		<li>The first row should be headings.
		<li>Please do not enter blank rows.
		<li>If you using a spreadsheet, select "Save As" CSV to 
		generate the csv file.</ol>')
		
class TableSelector
	
class ColumnSelector
	
class ColumnSelect
	
class Output
	
pscript.onload_import = ->
	new PageHeader($('#data_importer .head').get(0), 'Import Data')
	new Uploader()