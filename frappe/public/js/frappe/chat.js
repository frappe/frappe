// frappe.Chat
// Author - Achilles Rasquinha <achilles@frappe.io>
frappe.Chat
=
class
{
	constructor (selector, options)
	{
		if ( typeof selector !== 'string' )
		{
			options  = selector
			selector = null
		}

		this.selector   = selector ? selector : 'body'
		this.container  = $(this.selector)
		this.options    = Object.assign({ }, frappe.Chat.OPTIONS, options)

		this.state      = frappe.Chat.STATE

		this.widget     = new frappe.Chat.Widget(this.container, {
			layout: this.options.layout, ...this.state
		})
	}
}
frappe.Chat.STATE
=
{
	profile: { },
	  rooms: [ ],
	   room: { }
}
frappe.Chat.Layout
=
{
	PAEG: 'page', POPPER: 'popper'
}
frappe.Chat.OPTIONS
=
{
	layout: frappe.Chat.POPPER
}

frappe.Chat.Widget
=
class
{
	constructor (container, options) {
		this.$container = $(container)
		this.options    = Object.assign({ }, frappe.Chat.Widget.OPTIONS, options)

		this.make()
	}

	make ( )
	{
		this.render()
	}

	render ( )
	{
		const $template = $(frappe.Chat.Widget.TEMPLATE)
		this.$container.append($template)
	}
}
frappe.Chat.Widget.TEMPLATE = 
`
<div class="frappe-chat">
	
</div>
`
frappe.Chat.Widget.OPTIONS  = { layout: frappe.Chat.POPPER }