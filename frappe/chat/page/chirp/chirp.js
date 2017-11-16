const { h, render, Component } = preact

frappe.is_array     = (what) => {
    return what.constructor === Array
}
frappe.fuzzy_search = (query, dataset, options) => {
    const DEFAULT   = {
                shouldSort: true,
                 threshold: 0.6,
                  location: 0,
                  distance: 100,
        minMatchCharLength: 1,
          maxPatternLength: 32
    }
    options       = Object.assign({ }, DEFAULT, options)
    const fuse    = new Fuse(dataset, options)
    const result  = fuse.search(query)

    return result
}
frappe.pluralize  = (what, count)  => {
    if ( !what.endsWith('s') && count != 1 )
        return `${what}s`

    return what
}
frappe.squash     = (what) => {
    if ( frappe.is_array(what) && what.length === 1 )
        return what[0]
    return what
}
frappe.copy_array = (array) => {
    var copied    = [ ]

    for (var i in array) {
        if ( typeof array[i] === 'object' ) {
            const obj = Object.assign({ }, array[i])
            copied.push(obj)
        } else {
            copied.push(array[i])
        }
    }
    
    return copied
}

frappe.components           = { }
frappe.components.Indicator
=
class extends Component {
    render ( ) {
        const { props } = this

        return h("span", { class: `indicator ${props.color}`})
    }
}

frappe.components.Avatar
=
class extends Component {
    render ( ) {
        const { props } = this
        const abbr      = props.title.substr(0, 1)

        return (
            h("span", { class: "avatar avatar-small" },
                props.image ?
                    h("img", { class: "media-object", src: props.image })
                    :
                    h("div", { class: "standard-image" }, abbr)
            )
        )
    }
}

frappe.components.Select
=
class extends Component {
    render ( ) {
        const { props } = this
        const selected  = props.options.find(o => o.value === props.value)

        return (
            h("div", { class: "dropdown" },
                h("button", { class: "btn btn-sm btn-default btn-block dropdown-toggle", "data-toggle": "dropdown" },
                    selected ?
                        h(frappe.components.Indicator, { color: selected.color }) : null, selected ? selected.label : null
                ),
                h("ul", { class: "dropdown-menu" },
                    props.options.map(o => h(frappe.components.Select.Option, {...o, click: props.click }))
                )
            )
        )
    }
}
frappe.components.Select.Option
=
class extends Component {
    render ( ) {
        const { props } = this

        return (
            h("li", null,
                h("a", { onclick: () => props.click(props.value) },
                    props.color ?
                        h(frappe.components.Indicator, { color: props.color }) : null, props.label
                )
            )
        )
    }
}

frappe.Chat
=
class extends Component {
    constructor (props) {
        super (props)

        this.on_change_status = this.on_change_status.bind(this)
        this.on_select_room   = this.on_select_room.bind(this)

        this.state = frappe.Chat.defaultState

        this.make()
    }

    make ( ) {
        frappe.Chat.Action.create_chat_profile(["status"], profile => {
            this.setState({
                profile: profile
            })

            frappe.Chat.Action.get_user_room(null, room => {
                if ( !frappe.is_array(room) )
                    room = [room]

                this.setState({
                    rooms: room
                })
            })

            frappe.realtime.on('frappe.chat:profile:update', (response) => {
                const { user, data } = response

                if ( data.status ) {
                    const color = frappe.Chat.CHAT_PROFILE_STATUSES.find(s => s.name === data.status).color
                    const alert = `<span class="indicator ${color}"/> ${frappe.user.full_name(user)} is currently <b>${data.status}</b>`
                    frappe.show_alert(alert, 3)
                }
            })
        })
    }

    on_change_status (status) {
        frappe.Chat.Action.update_chat_profile({ status: status }, () =>
            this.setState({
                profile: { ...this.state.profile, status: status }
            })
        )
    }

    on_select_room (name) {
        const room = this.state.rooms.find(r => r.name === name)
        
        this.setState({
            room: room
        })
    }
    
    render ( ) {
        const { state } = this
        
        return (
            h("div", { class: "frappe-chat" },
                h("div", { class: "col-md-2  col-sm-3 layout-side-section" },
                    state.profile ?
                        h(frappe.Chat.AppBar, {
                                       status: state.profile.status,
                                        rooms: state.rooms,
                             on_change_status: this.on_change_status,
                               on_select_room: this.on_select_room
                        }) : null
                ),
                h("div", { class: "col-md-10 col-sm-9 layout-main-section-wrapper" },
                    h(frappe.Chat.Room, { ...state.room })
                )
            )
        )
    }
}
frappe.Chat.defaultState = {
    profile: null,
      rooms: [ ],
       room: null
}
frappe.Chat.Action = { }
frappe.Chat.Action.create_chat_profile
= 
(fields, fn) =>
    frappe.call('frappe.chat.doctype.chat_profile.chat_profile.create',
        { user: frappe.session.user, exist_ok: true, fields: fields },
            r => fn(r.message))
frappe.Chat.Action.update_chat_profile
= 
(data, fn) =>
    frappe.call('frappe.chat.doctype.chat_profile.chat_profile.update',
        { user: frappe.session.user, data: data },
            r => fn())
frappe.Chat.Action.get_user_room
=
(names, fn) =>
    frappe.call('frappe.chat.doctype.chat_room.chat_room.get',
        { user: frappe.session.user, room: names || null },
            r => fn(r.message))
frappe.Chat.Action.get_room_history
=
(name, fn) =>
    frappe.call('frappe.chat.doctype.chat_room.chat_room.get_history',
        { name: name },
            r => fn(r.message))
frappe.Chat.Action.send_message
=
(message) =>
    frappe.call('frappe.chat.doctype.chat_message.chat_message.send',
        { ...message },
            r => fn())

frappe.Chat.AppBar
=
class extends Component {
    constructor (props) {
        super (props)

        this.search_rooms = this.search_rooms.bind(this)
        this.state        = frappe.Chat.AppBar.defaultState
    }

    search_rooms (query) {
        const props   = this.props
        const dataset = props.rooms.map(r => r.room_name || frappe.user.full_name(frappe.squash(r.users)))
        const results = frappe.fuzzy_search(query, dataset)

        const rooms   = results.map(i => props.rooms[i])

        return rooms
    }

    render ( ) {
        const { props, state } = this
        const rooms            = state.query ? this.search_rooms(state.query) : props.rooms

        return (
            h("div", { class: "frappe-chat__app-bar" },
                h("div", { class: "frappe-chat__app-bar-account" },
                    h(frappe.Chat.AppBar.Account, { status: props.status, on_change_status: props.on_change_status })
                ),
                h("div", { class: "frappe-chat__app-bar-search" },
                    h(frappe.Chat.AppBar.SearchBar, { on_query: (query) => this.setState({ query: query }) })
                ),
                h("div", { class: "frappe-chat__app-bar-room-list" },
                    h(frappe.Chat.AppBar.RoomList, { rooms: rooms, on_select_room: props.on_select_room })
                )
            )
        )
    }
}
frappe.Chat.AppBar.defaultState   = {
    query: null
}

frappe.Chat.CHAT_PROFILE_STATUSES = [
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
frappe.Chat.AppBar.Account
=
class extends Component {
    render ( ) {
        const { props } = this
        const statuses  = frappe.Chat.CHAT_PROFILE_STATUSES.map(s => {
            return {
                value: s.name,
                label: s.name,
                color: s.color
            }
        })
        return (
            h(frappe.components.Select, { value: props.status, options: statuses, click: (value) => {
                if ( props.status != value )
                    props.on_change_status(value)
            }})
        )
    }
}
frappe.Chat.AppBar.SearchBar
=
class extends Component {
    constructor (props) {
        super (props)

        this.on_change = this.on_change.bind(this)
        this.on_submit = this.on_submit.bind(this)

        this.state     = frappe.Chat.AppBar.SearchBar.defaultState
    }

    on_change (e) {
        this.setState({
            [e.target.name]: e.target.value
        })

        this.props.on_query(this.state.query)
    }

    on_submit (e) {
        e.preventDefault()

        this.props.on_submit(this.state)
    }

    render ( ) {
        const { state } = this

        return (
            h("form", { oninput: this.on_change, onsubmit: this.on_submit },
                h("div", { class: "input-group input-group-sm" },
                    h("input", { class: "form-control", name: "query", value: state.query, placeholder: "Search" }),
                    h("div", { class: "input-group-btn" },
                        h("button", { class: "btn btn-primary dropdown-toggle", "data-toggle": "dropdown" },
                            h("i", { class: "octicon octicon-plus" })
                        ),
                        h("ul", { class: "dropdown-menu dropdown-menu-right" },
                            h("li", null,
                                h("a", null,
                                    h("i", { class: "octicon octicon-comment" }), " New Message"
                                )
                            ),
                            h("li", null,
                                h("a", null,
                                    h("i", { class: "octicon octicon-organization" }), " New Group"
                                )
                            )
                        )
                    )
                )
            )
        )
    }
}
frappe.Chat.AppBar.SearchBar.defaultState = {
    query: null
}

frappe.Chat.AppBar.RoomList
=
class extends Component {
    render ( ) {
        const { props } = this
        const rooms     = props.rooms

        return (
            h("ul", { class: "nav nav-pills nav-stacked" },
                rooms.map(room => h(frappe.Chat.AppBar.RoomList.Item, {...room, click: props.on_select_room }))
            )
        )
    }
}
frappe.Chat.AppBar.RoomList.Item
=
class extends Component {
    constructor (props) {
        super (props)
    }

    render ( ) {
        const { props } = this

        return (
            h("li", null,
                h("a", { class: props.active ? "active": "", onclick: () => props.click(props.name) },
                    h(frappe.Chat.MediaProfile, {
                        title: props.type === "Group" ? props.room_name :
                            props.owner == frappe.session.user ?
                                frappe.user.full_name(frappe.squash(props.users))
                                :
                                frappe.user.full_name(props.owner),
                        image: props.type === "Group" ? props.avatar    :
                            props.owner == frappe.session.user ?
                                frappe.user.image(frappe.squash(props.users))
                                :
                                frappe.user.image(props.owner)
                    })
                )
            )
        )
    }
}

frappe.Chat.Room
=
class extends Component {
    constructor (props) {
        super (props)

        this.on_submit = this.on_submit.bind(this)

        this.state     = frappe.Chat.Room.defaultState
    }

    on_submit (message) {
        const props = this.props
        const mess  = Object.assign({ }, message,
            { user: frappe.session.user, room: props.name })

        this.setState({
            messages: frappe.copy_array([...this.state.messages, mess])
        })

        frappe.Chat.Action.send_message(mess)
    }

    render ( ) {
        const { props, state } = this

        return (
            h("div", { class: "frappe-chat__room" },
                props.name ?
                    h("div", { class: "panel panel-default", style: "height: 720px; overflow-y: scroll;" },
                        h("div", { class: "panel-heading" },
                            h("div", { class: "panel-title" },
                                h(frappe.Chat.MediaProfile, {
                                    title: props.type === "Group" ? props.room_name :
                                        props.owner == frappe.session.user ?
                                            frappe.user.full_name(frappe.squash(props.users))
                                            :
                                            frappe.user.full_name(props.owner),
                                    image: props.type === "Group" ? props.avatar    :
                                        props.owner == frappe.session.user ?
                                            frappe.user.image(frappe.squash(props.users))
                                            :
                                            frappe.user.image(props.owner),
                                            
                                    width_title: "150px",
                                       subtitle: props.type === "Direct" ?
                                            ""
                                            :
                                            `${props.users.length} ${frappe.pluralize("member", props.users.length)}`
                                })
                            )
                        ),
                        h(frappe.Chat.ChatList, {
                            messages: state.messages
                        }),
                        h("div", { class: "panel-body" },
                            h(frappe.Chat.ChatForm, {
                                on_change: console.log,
                                on_submit: this.on_submit
                            })
                        )
                    )
                    :
                    h("div", null,
                        h("div", { class: "text-center" },
                            h("i", { class: "octicon octicon-comment-discussion", style: "font-size: 56px" }),
                            h("p", { class: "text-muted" }, "Select a chat to start messaging.")
                        )
                    )
            )
        )
    }
}
frappe.Chat.Room.defaultState = {
    messages: [ ]
}

frappe.Chat.MediaProfile
=
class extends Component {
    render ( ) {
        const { props } = this

        return (
            h("div", { class: "media" },
                h("div", { class: "media-left" },
                    h(frappe.components.Avatar, {
                        title: props.title,
                        image: props.image
                    })
                ),
                h("div", { class: "media-body" },
                    h("div", {
                        class: "media-heading h6 ellipsis",
                        style: `max-width: ${props.width_title || "96px"}; display: inline-block;`
                    }, props.title),
                    props.subtitle ? h("div", null, h("small", { class: "h6" }, props.subtitle)) : null
                )
            )
            
        )
    }
}

frappe.Chat.ChatList
=
class extends Component {
    render ( ) {
        const { props } = this
        
        return (
            h("ul", { class: "list-group" },
                props.messages.map(m => h(frappe.Chat.ChatList.Item, { ...m }))
            )
        )
    }
}

frappe.Chat.ChatList.Item
=
class extends Component {
    render ( ) {
        const { props } = this

        return (
            h("li", { class: "list-group-item" },
                h(frappe.Chat.ChatList.Bubble, props)
            )
        )
    }
}

frappe.Chat.ChatList.Bubble
=
class extends Component {
    render ( ) {
        const { props } = this

        return (
            h("div", { class: "row" },
                h("div", { class: "col-md-6" },
                    h(frappe.Chat.MediaProfile, {
                           title: frappe.user.full_name(props.user),
                           image: frappe.user.image(props.image),
                        subtitle: props.content
                    })
                ),
                h("div", { class: "col-md-6" },
                    h("div", { class: "text-right" },
                        
                    )
                ),
            )
        )
    }
}

frappe.Chat.ChatForm
=
class extends Component {
    constructor (props) {
        super (props)

        this.on_change = this.on_change.bind(this)
        this.on_submit = this.on_submit.bind(this)

        this.state     = frappe.Chat.ChatForm.defaultState
    }

    on_change (e) {
        this.setState({
            [e.target.name]: e.target.value
        })

        this.props.on_change(this.state)
    }

    on_submit (e) {
        e.preventDefault()

        if ( this.state.content ) {
            this.props.on_submit(this.state)

            this.setState({
                content: null
            })
        }
    }

    render ( ) {
        const { state } = this

        return (
            h("div", { class: "frappe-chat__form" },
                h("form", { oninput: this.on_change, onsubmit: this.on_submit },
                    h("div", { class: "form-group" },
                        h("div", { class: "input-group input-group-sm" },
                            h("div", { class: "input-group-btn" },
                                h("div", { class: "btn-group dropup" },
                                    h("button", { class: "btn btn-primary dropdown-toggle", "data-toggle": "dropdown" },
                                        h("i", { class: "fa fa-fw fa-paperclip" })
                                    ),
                                    h("div", { class: "dropdown-menu", style: "min-width: 150px" },
                                        h("li", null,
                                            h("a", null,
                                                h("i", { class: "octicon octicon-device-camera" }), ' Camera'
                                            )
                                        ),
                                        h("li", null,
                                            h("a", null,
                                                h("i", { class: "fa fa-fw fa-file" }), ' File'
                                            )
                                        )
                                    )
                                )
                            ),
                            h("textarea", {
                                      class: "form-control",
                                       name: "content",
                                      value: state.content,
                                placeholder: "Type a message",
                                  autofocus: true,
                                 onkeypress: (e) => {
                                     if ( e.which === 13 && !e.shiftKey ) { // is not "shift" + "return"
                                        this.on_submit(e)                   // submit that shit.
                                     }
                                 }
                            }),
                            h("div", { class: "input-group-btn" },
                                h("button", { class: "btn btn-primary" },
                                    h("i", { class: "fa fa-fw fa-smile-o" })
                                ),
                                h("button", { class: "btn btn-primary", type: "submit" },
                                    h("i", { class: "fa fa-fw fa-send" })
                                )
                            )
                        )
                    )
                )
            )
        )
    }
}

frappe.Chat.ChatForm.defaultState = {
    content: null
}

frappe.pages.chirp.on_page_load = (parent) => {
    const page =
    new frappe.ui.Page({
        parent: parent, title: __(`Chat`)
    })
    const $container = $(parent).find(".layout-main")
    $container.html("")

    render(h(frappe.Chat), $container[0])
}