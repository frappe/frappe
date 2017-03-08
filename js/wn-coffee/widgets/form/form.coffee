class wn.widgets.Form
	constructor: (@modeltype) ->
		@view = wn.app.models['DocType'][modeltype].__view
		@sections = []
		
	render: (@parent) ->
		# wrapper
		@wrapper = $a @parent 'div' 'form_wrapper'
		
		# render sections
		for s in @view.sections
			@sections.push new wn.widgets.FormSection @wrapper, section

class wn.widgets.FormSection
	constructor: (@parent, @section) ->
		@columns = []
		@fields = []
		@render()
	
	render: ->
		@wrapper = $a @parent 'div'
		for f in section.fields
			@render_field f, section
		
	render_section: (section) ->
		# render fields
		
		
	render_field: (field, section) ->
		# call the field factory
		make_field field, 