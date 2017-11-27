// frappe.Chat
// Author - Achilles Rasquinha
// Dependencies
// * momentjs
const { h, render, Component } = preact

frappe.is_array     = (what) => 
{
    if ( what && what.constructor )
        return what.constructor === Array
    return false
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
    options         = Object.assign({ }, DEFAULT, options)
    
    const fuse      = new Fuse(dataset, options)
    const result    = fuse.search(query)

    return result
}

frappe.pluralize   = (what, count)  => {
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

frappe.components = { }
frappe.components.Indicator
=
class extends Component {
    render ( ) {
        const { props } = this

        return h("span", { class: `indicator ${props.color}` })
    }
}
// frappe.components.Indicator props
// color - color for the indicator
// NOTE - Depends on avatar.less
frappe.components.Avatar
=
class extends Component {
    render ( ) {
        const { props } = this
        const abbr = props.abbr || props.title.substr(0, 1)
        const size = props.size === "small" ? "avatar-small" : "";

        return (
            h("span", { class: `avatar ${size}` },
                props.image ?
                    h("img", { class: "media-object", src: props.image })
                    :
                    h("div", { class: "standard-image" }, abbr)
            )
        )
    }
}
// frappe.components.Avatar props
// title - title for the avatar.
// abbr  - abbreviation for the avatar (optional), defaults to the first letter of the title.
// image - image for the avatar (optional), defaults to the first letter of the title.

frappe.components.Select
=
class extends Component {
    render ( ) {
        const { props } = this
        const selected  = props.options.find(o => o.value === props.value)

        return (
            h("div", { class: "dropdown" },
                h("button", { class: "btn btn-sm btn-default btn-block dropdown-toggle", "data-toggle": "dropdown" },
                    selected.color ?
                        h(frappe.components.Indicator, { color: selected.color }) : null,
                    selected.label ?
                        selected.label : selected.value,
                ),
                h("ul", { class: "dropdown-menu" },
                    props.options.map(o => h(frappe.components.Select.Option, { ...o, click: props.click }))
                )
            )
        )
    }
}
// frappe.components.Select props
// options - array of options of the format { label, value }.
// value   - default value.
// click   - click handler on click option.

// NOTES   - This could have been done wayyy better by passing custom component rendered.

frappe.components.Select.Option
=
class extends Component {
    render ( ) {
        const { props } = this

        return (
            h("li", null,
                h("a", { onclick: () => props.click(props.value) },
                    props.color ?
                        h(frappe.components.Indicator, { color: props.color }) : null, 
                    props.label ?
                        props.label : props.value
                )
            )
        )
    }
}
// frappe.components.Select.Option props
// same as frappe.components.Select.

frappe.chat = { }
frappe.chat.profile = { }
frappe.chat.profile.create
=
(fields, fn) =>
{
    return new Promise(resolve => {
        if ( typeof fields === 'function' ) {
            fn     = fields
            fields = null
        } else
        if ( typeof fields === 'string' )
            fields = [fields]
        
        frappe.call('frappe.chat.doctype.chat_profile.chat_profile.create',
            { user: frappe.session.user, exists_ok: true, fields: fields },
                r => {
                    if ( fn )
                        fn(r.message)
                    
                    resolve(r.message)
                })
    })
}

frappe.chat.update_chat_profile
= 
(data, fn) =>
    frappe.call('frappe.chat.doctype.chat_profile.chat_profile.update',
        { user: frappe.session.user, data: data },
            r => fn && fn())
frappe.chat.create_room
=
(kind, owner, users, name) =>
    frappe.call('frappe.chat.doctype.chat_room.chat_room.create',
        { kind: kind, user: owner || frappe.session.user, users: users, name: name })

frappe.chat.room = { }
frappe.chat.room.get
=
(names, fields, fn) =>
{
    if ( typeof names === 'function' ) {
        fn     = names
        names  = null
        fields = null
    }
    else
    if ( typeof names === 'string' ) {
        names  = [names]
        if ( typeof fields === 'function' ) {
            fn     = fields
            fields = null
        }
        else
        if ( typeof fields === 'string' )
            fields = [fields]
    }

    frappe.call('frappe.chat.doctype.chat_room.chat_room.get',
        { user: frappe.session.user, room: names, fields: fields },
            r => fn(r.message))
}

frappe.chat.get_room_history
=
(name, fn) =>
    frappe.call('frappe.chat.doctype.chat_room.chat_room.get_history',
        { room: name },
            r => {
                if ( r.message ) // frappe.api BOGZ!
                    fn(r.message)
                else
                    fn([])
            })
frappe.chat.send_message
=
(message) =>
    frappe.call('frappe.chat.doctype.chat_message.chat_message.send',
        { ...message })
frappe.chat.room.subscribe
=
(rooms) =>
    frappe.realtime.publish('frappe.chat:subscribe', rooms)

frappe.Chat
=
class extends Component {
    constructor (props) {
        super (props)

        this.on_change_status = this.on_change_status.bind(this)
        this.on_select_room   = this.on_select_room.bind(this)

        this.update_room      = this.update_room.bind(this)

        this.state            = frappe.Chat.defaultState

        this.make()
    }

    make ( ) {
        frappe.chat.profile.create("status", profile => {
            this.setState({ profile })

            frappe.chat.room.get(rooms => {
                if ( rooms ) { // if you're not a loner
                    frappe.chat.room.subscribe(rooms, (rooms) => {
                        if ( !frappe.is_array(rooms) ) {
                            rooms = [rooms]
                        }
                        
                        this.setState({ rooms })

                        // Bind events now that we have everything on plate.
                        this.bind()
                    })
                }
            })
        })
    }
    
    bind ( ) {
        frappe.realtime.on('frappe.chat:profile:update', (response) => {
            const { user, data } = response
            
            if ( data.status ) {
                if ( user === frappe.session.user ) {
                    this.setState({
                        profile: { ...this.state.profile, status: data.status }
                    })
                } else {
                    const status = frappe.Chat.CHAT_PROFILE_STATUSES.find(s => s.name === data.status)
                    const color  = status.color
                    
                    const alert  = `<span class="indicator ${color}"/> ${frappe.user.full_name(user)} is currently <b>${data.status}</b>`
                    frappe.show_alert(alert, 3)
                }
            }
        })
        
        frappe.realtime.on('frappe.chat:room:update', r => this.update_room(r.name, r))
        
        frappe.realtime.on('frappe.chat:message:new', (r) => {
            console.log(`Message Recieved - ${JSON.stringify(r)}`)
            const { state } = this
            if ( r.room === state.room.name ) {
                const mess  = state.room.messages.slice()
                mess.push(r)
                
                this.setState({
                    room: { ...state.room, messages: mess }
                })
            }
        })
    }
    
    update_room (name, update) {
        // Update Room List
        const { state } = this
        const rooms     = state.rooms.map(r => {
            if ( r.name === name )
                return Object.assign({ }, r, update)
            return r
        })

        this.setState({ rooms })

        // Update Room View
        if ( state.room.name === name ) {
            console.log(update)
            const room = Object.assign({ }, state.room, update)

            this.setState({ room })
        }
    }
    
    on_change_status (status) {
        frappe.chat.update_chat_profile({ status: status })
    }

    on_select_room (name) {
        frappe.chat.get_room_history(name, m => {
            const { state } = this
            const room      = this.state.rooms.find(r => r.name === name)

            this.setState({
                room: { ...state.room, ...room, messages: m }
            })
        })
    }
    
    render ( ) {
        const { state } = this
        
        return (
            h("div", { class: "frappe-chat" },
                h("div", { class: "col-md-2 col-sm-3 layout-side-section" },
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
       room: { name: null, messages: [ ], typing: null }
}

frappe.Chat.Layout = 
{
    PAGE: 'page', COLLAPSIBLE: 'collapsible'
}


frappe.Chat.AppBar
=
class extends Component {
    constructor (props) {
        super (props)

        this.search_rooms = this.search_rooms.bind(this)

        this.on_click_new_message = this.on_click_new_message.bind(this)
        this.on_click_new_group   = this.on_click_new_group.bind(this)

        this.state        = frappe.Chat.AppBar.defaultState
    }

    search_rooms (query) {
        const props   = this.props
        const dataset = props.rooms.map(r => {
            if ( r.room_name )
                return r.room_name
            else
                if ( r.owner === frappe.session.user )
                    return frappe.user.full_name(frappe.squash(r.users))
                else
                    return frappe.user.full_name(r.owner)
        })
        const results = frappe.fuzzy_search(query, dataset)

        const rooms   = results.map(i => props.rooms[i])

        return rooms
    }

    on_click_new_message ( ) {
        const dialog = new frappe.ui.Dialog({
              title: __(`New Message`),
            animate: false,
             fields: [
                {   
                        label: "Select User",
                    fieldname: "user",
                    fieldtype: "Link",
                      options: "User",
                         reqd: true,
                      filters: { "name": ["!=", frappe.session.user] }
                }
             ],
            primary_action_label: __(`Create`),
            primary_action: ({ user }) => {
                frappe.chat.create_room("Direct", frappe.session.user, user)
            }
        })
        dialog.show()
    }

    on_click_new_group ( ) {
        const dialog = new frappe.ui.Dialog({
              title: __(`New Group`),
            animate: false,
             fields: [
                {   
                        label: "Select Users",
                    fieldname: "user",
                    fieldtype: "MultiSelect",
                      options: [ ], // Hmm, how does this work?
                }
             ],
            primary_action_label: __(`Create`),
            primary_action: (data) => {
                
            }
        })
        dialog.show()
    }

    render ( ) {
        const { props, state } = this
        const rooms            = state.query ? this.search_rooms(state.query) : props.rooms

        return (
            h("div", { class: "frappe-chat__app-bar" },
                h("div", { class: "frappe-chat__app-bar-account" },
                    h(frappe.Chat.AppBar.Account, {
                                  status: props.status,
                        on_change_status: props.on_change_status
                    })
                ),
                h("div", { class: "frappe-chat__app-bar-search" },
                    h(frappe.Chat.AppBar.SearchBar, {
                                    on_query: query => this.setState({ query: query }),
                        on_click_new_message: this.on_click_new_message,
                        on_click_new_group:   this.on_click_new_group
                    })
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
        const { props, state } = this

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
                                h("a", { onclick: props.on_click_new_message },
                                    h("i", { class: "octicon octicon-comment" }), " New Message"
                                )
                            ),
                            h("li", null,
                                h("a", { onclick: props.on_click_new_group },
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
                            props.owner === frappe.session.user ?
                                frappe.user.full_name(frappe.squash(props.users))
                                :
                                frappe.user.full_name(props.owner),
                        image: props.type === "Group" ? props.avatar    :
                            props.owner === frappe.session.user ?
                                frappe.user.image(frappe.squash(props.users))
                                :
                                frappe.user.image(props.owner),
                         size: "small",
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

        this.on_typing = this.on_typing.bind(this)
        this.on_submit = this.on_submit.bind(this)

        this.state     = frappe.Chat.Room.defaultState
    }

    on_typing (what) {
        // const { props } = this

        // frappe.realtime.publish('frappe.chat:room:typing',
        //     { room: props.name, user: frappe.session.user })
    }

    on_submit (message) {
        const props = this.props
        const mess  = Object.assign({ }, message,
            { user: frappe.session.user, room: props.name })

        frappe.chat.send_message(mess)
    }

    render ( ) {
        const { props, state } = this

        return (
            h("div", { class: "frappe-chat__room" },
                props.name ?
                    h("div", { class: "panel panel-default", style: "height: 720px; overflow-y: scroll;" },
                        h(frappe.Chat.Room.Header, { ...props, click_phone: null }),
                        h(frappe.Chat.ChatList, {
                            messages: props.messages
                        }),
                        h("div", { class: "panel-body" },
                            h(frappe.Chat.ChatForm, {
                                on_change: this.on_typing,
                                on_submit: this.on_submit
                            })
                        )
                    )
                    :
                    h("div", null,
                        h("div", { class: "text-center" },
                            h("i", { class: "octicon octicon-comment-discussion text-extra-muted", style: "font-size: 48px" }),
                            h("p", { class: "text-extra-muted" }, "Select a chat to start messaging.")
                        )
                    )
            )
        )
    }
}
frappe.Chat.Room.Header
=
class extends Component {
    render ( ) {
        const { props } = this
        
        return (
            h("div", { class: "panel-heading" },
                h("div", { class: "row" },
                    h("div", { class: "col-xs-9" },
                        h("div", { class: "panel-title" },
                            h(frappe.Chat.MediaProfile, {
                                title: props.type === "Group" ? props.room_name :
                                    props.owner === frappe.session.user ?
                                        frappe.user.full_name(frappe.squash(props.users))
                                        :
                                        frappe.user.full_name(props.owner),
                                image: props.type === "Group" ? props.avatar    :
                                    props.owner === frappe.session.user ?
                                        frappe.user.image(frappe.squash(props.users))
                                        :
                                        frappe.user.image(props.owner),
                                abbr: props.type !== "Group" ? frappe.user.abbr : null,
                                width_title: "150px",
                                // subtitle: props.typing && props.typing !== frappe.session.user ? // Am I Typing?
                                //         props.type === "Group" ?
                                //             // show name yo.
                                //             `${frappe.user.get_full_name(props.typing)} typing...`
                                //             :
                                //             "typing..."
                                //         :
                                //         "",
                                    content: props.type === "Direct" ?
                                        ""
                                        :
                                        `${props.users.length} ${frappe.pluralize("member", props.users.length)}`
                            })
                        )
                    ),
                    h("div", { class: "col-xs-3" },
                        h("div", { class: "text-right" },
                            // Button ToolBar
                            h("a", null,
                                h("i", { class: "fa fa-fw fa-phone", onclick: props.click_phone })
                            )
                        )
                    )
                )
            )
            
        )
    }
}

frappe.Chat.MediaProfile
=
class extends Component {
    render ( ) {
        const { props } = this
        const position  = props.position === 'right' ? 'media-right' : 'media-left'
        const avatar    = (
            h("div", { class: `${position} media-top` },
                h(frappe.components.Avatar, {
                    title: props.title,
                    image: props.image,
                     size: props.size,
                     abbr: props.abbr
                })
            )
        )

        return (
            h("div", { class: "media" },
                position === 'media-left' ?
                    avatar : null,
                h("div", { class: "media-body" },
                    h("div", {
                        class: "media-heading h6 ellipsis",
                        style: `max-width: ${props.width_title || "96px"}; display: inline-block;`
                    },
                        props.title,
                    ),
                    props.content ? h("div", null, h("small", { class: "h6" }, props.content)) : null,
                    h("div", null, h("small", { class: "text-muted" }, props.subtitle))
                ),
                position === 'media-right' ?
                    avatar : null
            )
        )
    }
}

frappe.Chat.ChatList
=
class extends Component {
    render ( ) {
        const { props } = this
        
        return props.messages && props.messages.length
            ?
            (
                h("ul", { class: "list-group" },
                    props.messages.map(m => h(frappe.Chat.ChatList.Item, {
                        ...m
                    }))
                )
            ) : null
    }
}

frappe.Chat.ChatList.Item
=
class extends Component {
    render ( ) {
        const { props } = this

        return (
            h("li", { class: "list-group-item", style: "border: none !important;" },
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
        const bubble    = (
            h(frappe.Chat.MediaProfile, {
                      title: frappe.user.full_name(props.user),
                      image: frappe.user.image(props.user),
                   subtitle: frappe.Chat.get_datetime_string(new Date(props.creation)),
                    content: props.content,
                width_title: "100%",
                   position: frappe.user.full_name(props.user) === 'You' ? 'right' : 'left'
            })
        )

        return (
            h("div", { class: "row" },
                frappe.user.full_name(props.user) !== 'You' ?
                    h("div", { class: "col-md-6" }, bubble)
                    :
                    h("div", { class: "col-md-6 col-md-offset-6" },
                        h("div", { class: "text-right" },
                            bubble
                        )
                    )
            )
        )
    }
}
frappe.Chat.ChatList.Bubble.defaultState = {
    creation: ""
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

frappe.Chat.get_datetime_string   = (date) => {
    const instance = moment(date)
    const today    = moment()
    
    if ( today.isSame(instance, 'd') ) {
        return today.format("hh:mm A") 
    } else 
    if ( today.isSame(instance, 'week') ) {
        return today.format("dddd")
    } else {
        return today.format("DD/MM/YYYY")
    }
}

frappe.pages.chirp.on_page_load   = (parent) => {
    const page =
    new frappe.ui.Page({
        parent: parent, title: __(`Chat`)
    })
    const $container = $(parent).find(".layout-main")
    $container.html("")

    render(h(frappe.Chat), $container[0])
}

// frappe.Peer.boot()