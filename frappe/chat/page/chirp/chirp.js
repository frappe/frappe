frappe.pages.chirp.on_page_load = (wrapper) => {
    const $wrapper = $(wrapper)

    const page = new frappe.ui.Page({
        parent: $wrapper,
         title: __(`Chat`)
    })
    const $app = $wrapper.find('.layout-main')
    frappe.pages.chirp.chat = new frappe.Chat()
}

// Globals
frappe.Component = class {
    render ( ) {
        throw new Error('render function has not been implemented.')
    }
}
// end
const _$         = (...args) => {
    var element  = null

    args.forEach((arg) => {
        if ( typeof arg === 'string' ) {

        }
    })

    return element
}

frappe.Chat        = class extends frappe.Component {
    constructor (props) {
        super (props)

        this.state = frappe.Chat.DEFAULT_STATES

        this.make()
    }

    make ( ) {
        
    }

    render ( ) {
        return 
            _$('div#frappe-chat',
                _$('div.col-md-2.col-sm-3.layout-side-section',

                ),
                _$('div.col-md-10.col-sm-9.layout-main-section-wrapper',

                )
            )
    }
}
frappe.Chat.DEFAULT_STATES = {

}