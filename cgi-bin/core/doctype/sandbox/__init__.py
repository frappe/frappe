# configuration file for multiple controllers and view

# controller
controller_key = 'test_select'
controllers = {
	'A': 'core.doctype.sandbox.sandbox.SandboxController',
	'B': 'core.doctype.sandbox.alt.SandboxController2'
}

# view
view_key = 'test_select'
views = {
	'A': 'sandbox.js',
	'B': 'alternate.js'
}