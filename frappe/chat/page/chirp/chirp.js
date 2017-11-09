frappe.pages.chirp.on_page_load = (parent) => {
    const page = new frappe.ui.Page({
        parent: parent,
         title: 'Chat'
    })

    frappe.pages.chirp.chirp = new frappe.Chirp(parent)
}

frappe.Component = class {
    constructor (parent, props) {
        this.parent  = $(parent)
        this.props   = Object.assign({ }, props)
    }

    set_state (state) {
        this.state   = Object.assign({ }, this.state, state)
        this.render()
    }
}

frappe.Component.on_click  = (strdom, callback) => {
    const unique_id = frappe.dom.get_unique_id()
    const $element  = $(strdom).attr('id', unique_id)

    $(document).on('click', `#${unique_id}`, callback)

    return $element.prop('outerHTML')
}
frappe.Component.on_change = (strdom, callback) => {
    const unique_id = frappe.dom.get_unique_id()
    const $element  = $(strdom).attr('id', unique_id)

    $(document).on('change', `#${unique_id}`, callback)

    return $element.prop('outerHTML')
}
frappe.Component.on_submit = (strdom, callback) => {
    const unique_id = frappe.dom.get_unique_id()
    const $element  = $(strdom).attr('id', unique_id)

    $(document).on('submit', `#${unique_id}`, callback)

    return $element.prop('outerHTML')
}

frappe.Chirp = class extends frappe.Component {
    constructor (parent, props = null) {
        super (parent, props)

        this.$parent   = $(parent)
        this.state     = frappe.Chirp.DEFAULT_STATES

        this.create()
    }

    get_user_details () {
        frappe.call({
              method: 'frappe.chat.user.get',
            callback: response => this.set_state({ user: response.message })
        })
    }

    create ( ) {
        this.get_user_details()

        frappe.realtime.on('chat:user:status', (response) => {
            const { user, first_name, status } = response
            frappe.show_alert({
                  message: `${first_name || user} is currently <b>${status.toLowerCase()}</b>`,
                indicator: frappe.Chirp.get_status_color(status)
            }, 1.5)
        })

        frappe.realtime.on('chat:room:update', (response) => {
            this.get_user_details()
        })
    }

    on_change (e) {
        this.set_state({
            [e.target.name]: e.target.value
        })
    }
    
    on_submit (e) {
        if ( !e.isDefaultPrevented() )
            e.preventDefault()
    }

    on_click_room (room) {
        frappe.call({
              method: 'frappe.chat.doctype.chat_room.chat_room.get',
                args: { name: room.name },
            callback: response => this.set_state({ room: response.message })
        })
    }

    on_click_call ( ) {
        const dialog = new frappe.ui.Dialog({
            animate: false
        })

        dialog.show()
    }

    render ( ) {
        const { state, style } = this
        const template_sidebar = 
        `
        <div class="fc-sb-user" >
            <div class="dropdown">
                <button class="btn btn-default btn-block dropdown-toggle" data-toggle="dropdown">
                    <span class="indicator ${frappe.Chirp.get_status_color(state.user.status)}"></span> ${state.user.status}
                </button>
                <div class="dropdown-menu">
                    ${ frappe.Chirp.USER_STATUSES.map(s => 
                        `<li>
                            ${frappe.Component.on_click(`<a><span class="indicator ${frappe.Chirp.get_status_color(s.name)}"></span> ${s.name}</a>`, () => {
                                if ( state.user.status != s.name ) {
                                    frappe.call({
                                        method: 'frappe.chat.user.set_status',
                                            args: { status: s.name },
                                        callback: this.set_state({
                                            user: { ...state.user, status: s.name }
                                        })
                                    })
                                }
                            })}
                        </li>
                        `
                    ).join('') }
                </div>
            </div>

            ${frappe.Component.on_submit(`<form class="fc-sb-search">
                <div class="input-group input-group-sm">
                    <input class="form-control" placeholder="Search"/>
                    <div class="input-group-btn">
                        <button class="btn btn-primary dropdown-toggle" data-toggle="dropdown">
                            <i class="octicon octicon-plus"/>
                        </button>
                        <ul class="fc-sb-search-dropdown-menu dropdown-menu dropdown-menu-right">
                            <li>
                                ${frappe.Component.on_click(`<a><i class="octicon octicon-comment"/> New Message</a>`, () => {
                                    const dialog = new frappe.ui.Dialog({
                                        animate: false
                                    })

                                    dialog.show()
                                })}
                            </li>
                            <li>
                                ${frappe.Component.on_click(`<a><i class="octicon octicon-organization"/> New Group</a>`, () => {
                                    const dialog = new frappe.ui.Dialog({
                                        animate: false
                                    })

                                    dialog.show()
                                })}
                            </li>
                        </ul>
                    </div>
                </div>
            </form>`, e => e.preventDefault())}

            <div class="fc-sb-list">
                <ul class="nav nav-pills nav-stacked">
                    ${ state.user.rooms.map(r => 
                    `
                    <li>
                        ${frappe.Component.on_click(`<a>${r.room_name}</a>`, () => {
                            this.on_click_room(r)
                        })}
                    </li>
                    `).join("") }
                </ul>
            </div>
        </div>
        `
        const template_room = 
        `
        <div class="fs-room">
            <div class="panel panel-default">
                ${
                    state.room.room_name ?
                        `
                        <div class="panel-heading">
                            <div class="row">
                                <div class="col-xs-7">
                                    <div>
                                        <b class="h5">${state.room.room_name || ''}</b>
                                    </div>
                                    <small>
                                        ${
                                            state.room.type === 'Direct' ? 
                                                `last seen `
                                                : 
                                                `${state.room.users.length} member${state.room.users.length == 1 ? '' : 's'}`
                                        }
                                    </small>
                                </div>
                                <div class="col-xs-5">
                                    <div class="text-right">
                                        ${frappe.Component.on_click(`<a><i class="fa fa-fw fa-phone"/></a>`, this.on_click_call)}
                                    </div>
                                </div>
                            </div>
                        </div>
                        ` : ''
                }
                <div class="panel-body">
                    ${
                        state.room.room_name ?
                            frappe.Component.on_submit(`<form>
                                <div class="input-group">
                                    ${frappe.Component.on_change(
                                        `<textarea
                                            rows="1"
                                            name="message"
                                            value="${state.message}"
                                            class="form-control"
                                            placeholder="Type a message"/>`, this.on_change)}
                                        <span class="input-group-addon btn btn-default" type="submit">
                                            <i class="fa fa-fw fa-send"/>
                                        </span>
                                </div>
                            </form>`, this.on_submit) : ''
                    }
                </div>
            </div>
        </div>
        `
        
        this.$parent.find('.layout-side-section').html(template_sidebar)
        this.$parent.find('.layout-main-section-wrapper').html(template_room)
    }
}
frappe.Chirp.USER_STATUSES    = [
    {
        name: 'Online',
       color: 'green'
    },
    {
        name: 'Away',
       color: 'yellow'
    },
    {
        name: 'Busy',
       color: 'red'
    },
    {
        name: 'Invisible',
       color: 'grey'
    }
]
frappe.Chirp.DEFAULT_STATES   = {
    user: {
        status: null
    },
    room: {
        room_name: null,
            users: [ ]
    },
    message: null
}
frappe.Chirp.get_status_color = (status) => {
    const meta = frappe.Chirp.USER_STATUSES.find(s => s.name === status)

    return meta.color
}