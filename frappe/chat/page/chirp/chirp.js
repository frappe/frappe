frappe.pages.chirp.on_page_load = (parent) => {
    const page = new frappe.ui.Page({
        parent: parent,
         title: 'Chat'
    })

    const $app = $(parent).find('.layout-main')
    frappe.pages.chirp.chirp = new frappe.Chirp()
    frappe.Component.mount(frappe.pages.chirp.chirp, $app)
}

// 
frappe.pluralize = (string, count) => {
    if ( count == 1 ) {
        return string
    } else {
        // This is incomplete. Do more parsing. - <achilles@frappe.io>
        return `${string}s`
    }
}
//

frappe.Component = class {
    constructor (props = { }) {
        this.props = Object.assign({ }, frappe.Component.defaultProps, props)
    }

    set_state (state) {
        this.state = Object.assign({ }, this.state, state)
        this.render()

        if ( this.parent )
            frappe.Component.mount(this, this.parent)
    }

    set_parent (parent) {
        this.parent = parent

        return this
    }
}
frappe.Component.defaultProps = { }

frappe.Component.on_click = (strdom, callback) => {
    const unique_id = frappe.dom.get_unique_id()
    const $element  = $(strdom).attr('id', unique_id)

    $(document).on('click', `#${unique_id}`, callback)

    strdom = $element.prop('outerHTML')

    return strdom
}
frappe.Component.on_change = (strdom, callback) => {
    const unique_id = frappe.dom.get_unique_id()
    const $element  = $(strdom).attr('id', unique_id)

    $(document).on('change', `#${unique_id}`, callback)

    strdom = $element.prop('outerHTML')

    return strdom
}
frappe.Component.on_submit = (strdom, callback) => {
    const unique_id = frappe.dom.get_unique_id()
    const $element  = $(strdom).attr('id', unique_id)

    $(document).on('submit', `#${unique_id}`, callback)

    strdom = $element.prop('outerHTML')

    return strdom
}

frappe.Component.mount = (component, element) => {
    const $parent  = $(element)
    const template = component.set_parent($parent).render()

    $parent.html(template)
}
frappe.component = { }
frappe.component.Indicator = class extends frappe.Component {
    set_parent (component) {
        this.parent = component
    }

    render ( ) {
        const { props } = this

        return `<span class="indicator ${props.color}"/>`
    }
}
frappe.component.Select = class extends frappe.Component {
    constructor (props) {
        super (props)

        this.on_change  = this.on_change.bind(this)
    }

    get_option (value) {
        const { props } = this
        const result    = props.options.find(o => o.value === value)

        return result
    }

    on_change (value) {
        const { props } = this
        if ( value != props.value ) {
            props.on_change(value)
        }
    }

    render ( ) {
        const { props } = this
        const options   = props.options.map(o => 
            new frappe.component.Select.Option({ ...o, on_click: this.on_change })
                .render()
        ).join("")

        const selected = this.get_option(props.value)
        
        return `
        <div class="dropdown">
            <button class="btn btn-default btn-block dropdown-toggle" data-toggle="dropdown">
                ${new frappe.component.Indicator({ color: selected.color }).render()} ${selected.label}
            </button>
            <div class="dropdown-menu">
                ${options}
            </div>
        </div>
        `
    }
}
frappe.component.Select.Option = class extends frappe.Component {
    constructor (props) {
        super (props)

        this.on_click = this.on_click.bind(this)
    }

    on_click ( ) {
        const { props } = this

        props.on_click(props.value)
    }

    render ( ) {
        const { props } = this
        
        return `
            <li>
                ${frappe.Component.on_click(`<a>${new frappe.component.Indicator({
                    color: props.color
                }).render()} ${props.label}</a>`, this.on_click)}
            </li>
        `
    }
}
frappe.component.List = class extends frappe.Component {
    render ( ) {
        const { props } = this
        const items     = props.items.map(i => 
            new frappe.component.List.Item({ ...i, on_click: props.on_click })
                .render()
        ).join("")

        return `
            <div class="nav nav-pills nav-stacked">
                ${items}
            </div>
        `
    }
}
frappe.component.List.Item = class extends frappe.Component {
    constructor (props) {
        super (props)

        this.on_click   = this.on_click.bind(this)
    }

    on_click ( ) {
        const { props } = this
        this.set_state({ active: true })

        props.on_click(props.value)
    }

    render ( ) {
        const { props, state } = this

        return `
            <li>
                ${frappe.Component.on_click(`<a class="h6">${props.label}</a>`, this.on_click)}
            </li>
        `
    }
}

frappe.Chirp = class extends frappe.Component {
    constructor (props) {
        super (props)

        this.on_change_user_status = this.on_change_user_status.bind(this)
        this.on_select_room        = this.on_select_room.bind(this)

        this.state = frappe.Chirp.DEFAULT_STATES

        this.make()
    }

    make ( ) {
        frappe.Chirp.Action.get_user(null, user => this.set_state({ user: user }))
        frappe.realtime.on('chat:user:status', user => 
            frappe.show_alert(`
                ${new frappe.component.Indicator({
                    color: frappe.Chirp.get_status_color(user.status)
                }).render()} ${user.first_name || user.name} is currently <b>${user.status}</b>`, 1.5)
        )
        frappe.realtime.on('chat:room:update', (room) => {
            frappe.Chirp.Action.get_user(null, user => this.set_state({ user: user }))
        })
    }

    on_change_user_status (status) {
        const { state } = this
        frappe.Chirp.Action.set_user_status(status,
            status => this.set_state({ user: { ...state.user, status: status }}))
    }

    on_select_room (room) {
        const { state } = this
        frappe.Chirp.Action.get_room(room , data => this.set_state({ room: data }))
    }

    render ( ) {
        const { state } = this

        return `
            <div class="fc">
                <div class="layout-sidebar-section col-sm-3 col-md-2 ">
                    ${new frappe.Chirp.AppBar({
                        user: state.user,
                        on_change_user_status: this.on_change_user_status,
                        on_select_room: this.on_select_room
                    }).render()}
                </div>
                <div class="layout-main-section-wrapper col-md-10 col-sm-9">
                    ${new frappe.Chirp.Room({
                         type: state.room.type,
                         name: state.room.room_name,
                        users: state.room.users
                    }).render()}
                </div>
            </div>
        `
    }
}
frappe.Chirp.Action = { }
frappe.Chirp.Action.get_user = (user, callback) => {
    frappe.call('frappe.chat.user.get',
        { user: user || frappe.session.user },
            r => callback(r.message))
}
frappe.Chirp.Action.set_user_status = (status, callback) => {
    frappe.call('frappe.chat.user.set_status',
        { status: status },
            r => callback(status))
}
frappe.Chirp.Action.get_room = (room, callback) => {
    frappe.call('frappe.chat.doctype.chat_room.chat_room.get',
        { name: room },
            r => callback(r.message))
}
frappe.Chirp.DEFAULT_STATES = {
    user: {
        status: "",
         rooms: [ ]
    },
    room: {
        room_name: ""
    }
}

frappe.Chirp.USER_STATUSES = [
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
        name: 'Offline',
       color: 'grey'
    }
]
frappe.Chirp.get_status_color = (status) => {
    return frappe.Chirp.USER_STATUSES.find(s => s.name === status).color
}

frappe.Chirp.AppBar = class extends frappe.Component {
    render ( ) {
        const { props } = this
        const options   = frappe.Chirp.USER_STATUSES.map(o => {
            return {
                label: o.name,
                value: o.name,
                color: o.color
            }
        })

        const rooms     = props.user.rooms.map(r => {
            return {
                label: r.type === "Direct" ? props.user.first_name || props.user.name : r.room_name,
                value: r.name
            }
        })
        
        return `
        <div class="fc-ab">
            ${
                props.user.status ?
                    `
                    <div class="fc-ab-status">
                        ${new frappe.component.Select({
                                name: "fc-user-status",
                                value: props.user.status,
                            options: options,
                            on_change: props.on_change_user_status
                        }).render()}
                    </div>
                    ` : ''
            }

            ${new frappe.Chirp.RoomSearchBar({

            }).render() }

            ${
                rooms ?
                    `
                    <div class="fc-ab-rl">
                        ${new frappe.component.List({
                            items: rooms,
                            on_click: props.on_select_room
                        }).render()}
                    </div>
                    ` : ''
            }
        </div>
        `
    }
}

frappe.Chirp.RoomSearchBar = class extends frappe.Component {
    constructor (props) {
        super (props)

        this.on_submit = this.on_submit.bind(this)
    }

    on_submit ( ) {

    }

    render ( ) {
        return frappe.Component.on_submit(`
            <form class="fc-ab-sb">
                <div class="input-group input-group-sm">
                    <input
                        class="form-control"
                        placeholder="Search"/>
                    <div class="input-group-btn">
                        <button class="btn btn-primary dropdown-toggle" data-toggle="dropdown">
                            <i class="octicon octicon-plus"/>
                        </button>
                        <div class="dropdown-menu dropdown-menu-right">
                            <li>
                                ${frappe.Component.on_click(`
                                    <a>
                                        <span class="octicon octicon-comment"/> New Message
                                    </a>`
                                , () => {
                                    const dialog = new frappe.ui.Dialog({
                                        animate: false
                                    })
                                    dialog.show()
                                })}
                            </li>
                            <li>
                                ${frappe.Component.on_click(`
                                    <a>
                                        <span class="octicon octicon-organization"/> New Group
                                    </a>`
                                , () => {
                                    const dialog = new frappe.ui.Dialog({
                                        animate: false
                                    })
                                    dialog.show()
                                })}
                            </li>
                        </div>
                    </div>
                </div>
            </form>
        `, this.on_submit)
    }
}

frappe.Chirp.Room = class extends frappe.Component {
    render ( ) {
        const { props } = this
        
        return props.type ? 
        `
            <div class="fc-cr">
                <div class="panel panel-default">
                    <div class="panel-heading">
                        <div class="row">
                            <div class="col-md-7">
                                <b class="h5">
                                    ${
                                        props.type === "Direct" ?
                                            props.users[0].user
                                            :
                                            props.name
                                    }
                                </b>
                            </div>
                            <div class="col-md-5">
                                <div class="text-right">

                                </div>
                            </div>
                        </div>
                        <small>
                            ${ props.type == "Direct" ?
                                `last seen` 
                                :
                                `${props.users.length} ${frappe.pluralize(`member`, props.users.length)}`
                            }
                        </small>
                    </div>
                    ${ new frappe.Chirp.MessageList({
                        messages: [ ]
                    }).render() }
                    <div class="panel-body">
                        ${ new frappe.Chirp.ChatForm({
                            
                        }).render() }
                    </div>
                </div>
            </div>
        ` : 
        `
        <div class="text-center">
            <p>
                <i class="octicon octicon-comment"/>
            </p>
            <small>Select a chat to start messaging</small>
        </div>
        `
    }
}

frappe.Chirp.MessageList = class extends frappe.Component {
    render ( ) {
        const { props } = this
        const items     = props.messages.map(m => 
            new frappe.Chirp.MessageList.Item({
                content: m.content
            })
        ).join("")

        return `
            <div class="fc-ml">
                <div class="list-group">
                    ${items}
                </div>
            </div>
        `
    }
}
frappe.Chirp.MessageList.Item = class extends frappe.Component {
    render ( ) {
        const { props } = this

        return `
        <div class="list-group-item">
            
        </div>
        `
    }
}

frappe.Chirp.ChatForm = class extends frappe.Component {
    constructor (props) {
        super (props)

        this.on_submit = this.on_submit.bind(this)
    }

    on_submit (e) {
        if ( !e.isDefaultPrevented() )
            e.preventDefault()
    }

    render ( ) {
        const { props } = this

        return frappe.Component.on_submit(`
            <form>
                <div class="input-group">
                    <textarea
                        class="form-control"
                        placeholder="Type a message"/>
                    <span class="input-group-addon btn btn-default">
                        <i class="octicon octicon-pencil"/>
                    </span>
                </div>
            </form>
        `, this.on_submit)
    }
}