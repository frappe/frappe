// frappe Chat
// Author - Achilles Rasquinha <achilles@frappe.io>

// frappe._
// frappe's utility namespace.
frappe.provide('frappe._');

/**
 * @description Fuzzy Searching
 * 
 * @param   {string} query   - A query string.
 * @param   {array}  dataset - A dataset to search within, can contain singletons or objects.
 * @param   {object} options - Options as per fuze.js
 * 
 * @returns {integer|object} - The fuzzy matched index/object within the dataset.
 * 
 * @example
 * frappe._.fuzzy_search("foo", ["foobar", "bartender"]);
 * // returns 0
 * 
 * frappe._.fuzzy_search("foo", [{ key: "foobar" }, { key: "tootifrooti" }]);
 * // returns [{ key: "foobar" }]
 * 
 * @see http://fusejs.io
 */
frappe._.fuzzy_search = function (query, dataset, options)
{
    const DEFAULT =
    {
                shouldSort: true,
                 threshold: 0.6,
                  location: 0,
                  distance: 100,
        minMatchCharLength: 1,
          maxPatternLength: 32
    };
    options       = { ...DEFAULT, ...options };

    const fuse    = new Fuse(dataset, options);
    const result  = fuse.search(query);

    return result;
};

/**
 * @description Converts a singleton to an array, if required.
 * 
 * @param {object} item - An object
 * 
 * @example
 * frappe._.as_array("foo");
 * // returns ["foo"]
 * 
 * frappe._.as_array(["foo"]);
 * // returns ["foo"]
 */
frappe._.as_array = function (item)
{
    if ( !Array.isArray(item) )
        return [item];
    return item;
};

/**
 * @description Return a singleton if array contains a single element.
 * 
 * @param   {array}        list - An array to squash.
 * 
 * @returns {array|object} Returns an array if there's more than 1 object else the first object itself.
 * 
 * @example
 * frappe._.squash(["foo"]);
 * // returns "foo"
 * frappe._.squash(["foo", "bar"]);
 * // returns ["foo", "bar"]
 */
frappe._.squash = function (list)
{
    if ( Array.isArray(list) && list.length === 1 )
        return list[0];
    return list;
};

/**
 * @description Returns true, if the current device is a mobile device.
 * 
 * @example
 * frappe._.is_mobile();
 * // returns true|false
 * 
 * @see https://developer.mozilla.org/en-US/docs/Web/HTTP/Browser_detection_using_the_user_agent
 */
frappe._.is_mobile = function ( )
{
    const regex    = new RegExp("android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini", "i");
    const agent    = navigator.userAgent;
    const mobile   = regex.test(agent.toLowerCase());

    return mobile;
};

const { h, Component } = hyper;

// frappe.components
// frappe's component namespace.
frappe.provide('frappe.components');

/**
 * @description Button Component
 * 
 * @extends Component
 */
frappe.components.Button
=
class extends Component
{
    render ( )
    {
        const { props } = this;

        return (
            h("button", { ...props, class: `btn btn-${props.type} ${props.block ? "btn-block" : ""} ${props.class}` },
                props.children
            )
        );
    }
};
frappe.components.Button.defaultProps =
{
     type: "default",
    block: false
};

/**
 * @description FAB Component
 * 
 * @extends frappe.components.Button
 */
frappe.components.FAB
=
class extends frappe.components.Button
{
    render ( )
    {
        const { props } = this;
        const size      = frappe.components.FAB.SIZE[props.size];
        
        return (
            h(frappe.components.Button, {...props, class: `${props.class} ${size && size.class}`},
                h("i", { class: props.icon })
            )
        );
    }
};
frappe.components.FAB.defaultProps
=
{
    icon: "octicon octicon-plus"
};
frappe.components.FAB.SIZE
=
{
    small:
    {
        class: "frappe-fab-sm"
    },
    large:
    {
        class: "frappe-fab-lg"
    }
};

/**
 * @description Octicon Component
 */
frappe.components.Octicon
=
class extends Component
{
    render ( )
    {
        const { props } = this;

        return props.type ?
            h("i", { class: `octicon octicon-${props.type}`})
            :
            null;
    }
};

/**
 * @description Frappe Chat Object.
 * 
 * @example
 * const chat = new frappe.Chat(options); // appends to "body"
 * chat.render();
 * const chat = new frappe.Chat(".selector", options);
 * chat.render();
 * 
 * const chat = new frappe.Chat();
 * chat.set_wrapper('.selector')
 *     .set_options(options)
 *     .render();
 */
frappe.Chat
=
class
{
    /**
     * @description Frappe Chat Object.
     * @param {string} selector - A query selector, HTML Element or jQuery object.
     * @param {object} options  - Optional configurations.
     */
    constructor (selector, options)
    {
        if ( typeof selector !== "string" )
        {
            options  = options;
            selector = null;
        }

        this.options = frappe.Chat.OPTIONS;

        this.set_wrapper(selector ? selector : "body");
        this.set_options(options);
    }

    /**
     * Set the container on which the chat widget is mounted on.
     * @param {string} selector
     * 
     * @example
     * const chat = new frappe.Chat();
     * chat.set_wrapper(".selector");
     */
    set_wrapper (selector)
    {
        this.$wrapper = $(selector);

        return this;
    }

    /**
     * Set the configurations for the chat interface.
     * @param {object} options
     * 
     * @example
     * const chat = new frappe.Chat();
     * chat.set_options({ layout: frappe.Chat.Layout.PAGE });
     */
    set_options (options)
    {
        this.options = { ...this.options, options };

        return this;
    }

    /**
     * @description Destory the chat widget.
     * 
     * @example
     * const chat = new frappe.Chat();
     * chat.render()
     *     .destroy();
     */
    destroy ( )
    {
        const $wrapper = this.$wrapper;
        $wrapper.remove(".frappe-chat");

        return this;
    }

    /**
     * @description Render the chat widget component onto destined wrapper.
     * 
     * @example
     * const chat = new frappe.Chat();
     * chat.render();
     */
    render ( )
    {
        this.destroy();

        const $wrapper = this.$wrapper;
        const options  = this.options;

        const component  = h(frappe.Chat.Widget, {
            layout: options.layout
        });

        hyper.render(component, $wrapper[0]);

        return this;
    }
};
frappe.Chat.Layout
=
{
    PAGE: "page", POPPER: "popper"
};
frappe.Chat.OPTIONS
=
{
    layout: frappe.Chat.Layout.POPPER
};

// frappe.chat
frappe.provide('frappe.chat');

// frappe.chat.profile
frappe.provide('frappe.chat.profile');
/**
 * @description Create a Chat Profile
 * 
 * @param   {string|array} fields - (Optional) fields to be retrieved after creating a Chat Profile.
 * @param   {function}     fn     - (Optional) callback with the returned Chat Profile.
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.profile.create(function (profile) {
 *      // do stuff
 * });
 * frappe.chat.profile.create("status").then(function (profile) {
 *      console.log(profile); // { status: "Online" }
 * });
 */
frappe.chat.profile.create
=
function (fields, fn)
{
    if ( typeof fields === "function" )
    {
        fn     = fields;
        fields = null;
    } else
    if ( typeof fields === "string" )
        fields = frappe._.as_array(fields);

    return new Promise(resolve =>
    {
        frappe.call("frappe.chat.doctype.chat_profile.chat_profile.create",
            { user: frappe.session.user, exists_ok: true, fields: fields },
                response =>
                {
                    if ( fn )
                        fn(response.message)
                    
                    resolve(response.message)
                });
    });
};

frappe.provide('frappe.chat.profile.on');

/**
 * @description Triggers on a Chat Profile update of a subscribed user.
 * 
 * @param {function} fn - (Optional) callback with the user and the Chat Profile update.
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.profile.on.update(function (user, update) {
 *      // do stuff
 * });
 */
frappe.chat.profile.on.update
= 
// You should use . and not :, use . for event, : for query.
function (fn) 
{
    frappe.realtime.on("frappe.chat.profile.update", r => fn(r.user, r.data))
};

frappe.chat.profile.STATUSES
=
[
    {
        name: "Online",
       color: "green"
    },
    {
         name: "Away",
        color: "yellow"
    },
    {
         name: "Busy",
        color: "red"
    },
    {
         name: "Offline",
        color: "darkgrey"
    }
];

// frappe.chat.room
frappe.provide('frappe.chat.room');

/**
 * @description Creates a Chat Room
 * 
 * @param   {string|array} kind   - (Required) "Direct", "Group" or "Visitor"
 * @param   {string|array} fields - (Optional) fields to be retrieved for each Chat Room.
 * @param   {function}     fn     - (Optional) callback with the returned Chat Room(s).
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.room.get(function (rooms) {
 *      // do stuff
 * });
 * frappe.chat.room.get().then(function (rooms) {
 *      // do stuff
 * });
 * 
 * frappe.chat.room.get(null, ["room_name", "avatar"], function (rooms) {
 *      // do stuff
 * });
 * 
 * frappe.chat.room.get("CR00001", "room_name", function (room) {
 *      // do stuff
 * });
 */
frappe.chat.room.create
=
(kind, owner, users, name, fn) =>
{
    if ( typeof name === "function" )
    {
        fn   = name;
        name = null;
    }
    
    return new Promise(resolve =>
    {
        frappe.call("frappe.chat.doctype.chat_room.chat_room.create",
            { kind: kind, owner: owner || frappe.session.user, users: users, name: name },
            r =>
            {
                if ( fn )
                    fn(r.message);

                resolve(r.message);
            });
    });
};

/**
 * @description Returns Chat Room(s)
 * 
 * @param   {string|array} names  - (Optional) Chat Room(s) to retrieve.
 * @param   {string|array} fields - (Optional) fields to be retrieved for each Chat Room.
 * @param   {function}     fn     - (Optional) callback with the returned Chat Room(s).
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.room.get(function (rooms) {
 *      // do stuff
 * });
 * frappe.chat.room.get().then(function (rooms) {
 *      // do stuff
 * });
 * 
 * frappe.chat.room.get(null, ["room_name", "avatar"], function (rooms) {
 *      // do stuff
 * });
 * 
 * frappe.chat.room.get("CR00001", "room_name", function (room) {
 *      // do stuff
 * });
 */
frappe.chat.room.get
=
function (names, fields, fn)
{
    if ( typeof names === "function" ) {
        fn     = names
        names  = null
        fields = null
    }
    else
    if ( typeof names === "string" ) {
        names  = frappe._.as_array(names);

        if ( typeof fields === "function" ) {
            fn     = fields
            fields = null
        }
        else
        if ( typeof fields === "string" )
            fields = frappe._.as_array(fields);
    }

    return new Promise(resolve =>
    {

        frappe.call("frappe.chat.doctype.chat_room.chat_room.get",
            { user: frappe.session.user, rooms: names, fields: fields },
                response =>
                {
                    if ( fn )
                        fn(response.message)

                    resolve(response.message)
                });
    });
};

/**
 * @description Subscribe current user to said Chat Room(s)
 * 
 * @param {string|array} rooms - Chat Room(s).
 * 
 * @example
 * frappe.chat.room.get(function (rooms) {
 *      frappe.chat.room.subscribe(rooms);
 * });
 */
frappe.chat.room.subscribe
=
function (rooms)
{
    frappe.realtime.publish("frappe.chat:subscribe", rooms);
};

/**
 * @description Searchs Rooms based on a query.
 * 
 * @param {string} query - the query string
 * @param {array}  rooms - array of Chat Rooms.
 */
frappe.chat.room.search
=
function (query, rooms)
{
    const dataset = rooms.map(r => 
    {
        if ( r.room_name )
            return r.room_name
        else
            if ( r.owner === frappe.session.user )
                return frappe.user.full_name(frappe._.squash(r.users))
            else
                return frappe.user.full_name(r.owner)
    });
    const results = frappe._.fuzzy_search(query, dataset)
    rooms         = results.map(i => rooms[i])

    return rooms
}

/**
 * @description The base Component for Frappe Chat
 */
frappe.Chat.Widget
=
class extends Component
{
    constructor (props)
    {
        super (props);

        this.on_change_status = this.on_change_status.bind(this)
        this.on_select_room   = this.on_select_room.bind(this)

        this.add_room         = this.add_room.bind(this)
        this.update_room      = this.update_room.bind(this)

        this.state            = frappe.Chat.Widget.defaultStates;

        this.make();
    }

    make ( ) {
        frappe.chat.profile.create([
            "status", "display_widget"
        ], profile =>
        {
            this.setState({ profile });

            frappe.chat.room.get(rooms =>
            {
                if ( rooms )
                {
                    frappe.chat.room.subscribe(rooms);

                    rooms = frappe._.as_array(rooms);
                    this.setState({ rooms });
                }
            });

            this.bind();
        });
    }
    
    bind ( ) {
        frappe.chat.profile.on.update((user, update) =>
        {
            if ( 'status' in update )
            {
                if ( user === frappe.session.user )
                {
                    this.setState({
                        profile: { ...this.state.profile, status: update.status }
                    });
                } else
                {
                    const status = frappe.chat.profile.STATUSES.find(s => s.name === update.status);
                    const color  = status.color;
                    
                    const alert  = `<span class="indicator ${color}"/> ${frappe.user.full_name(user)} is currently <b>${update.status}</b>`;
                    frappe.show_alert(alert, 3);
                }
            }

            if ( 'display_widget' in update )
            {
                this.setState({
                    profile: { ...this.state.profile, display_widget: update.display_widget }
                });
            }
        });

        frappe.chat.room.on.create((room) => {
            this.add_room(room)
        })

        frappe.chat.room.on.update((room, update) => {
            this.update_room(room, update)
        })
        
        frappe.chat.message.on.create((r) => 
        {
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
    
    on_change_status (status) {
        frappe.chat.profile.update(null, {
            status: status
        })
    }
    
    on_select_room (name) {
        frappe.chat.room.history(name, m => 
        {
            const { state } = this
            const room      = state.rooms.find(r => r.name === name)

            this.setState({
                 room: { ...state.room, ...room, messages: m }
            })
        })
    }

    update_room (room, update) {
        // update list
        const { state } = this
        const rooms     = state.rooms.map(r => {
            if ( r.name === room )
                return Object.assign({ }, r, update)
            return r
        })

        this.setState({ rooms })

        // update room
        if ( state.room.name === room ) {
            const room = Object.assign({ }, state.room, update)

            this.setState({ room })
        }
    }

    add_room (room)
    {
        frappe.chat.room.subscribe(room.name)
        
        const { state } = this
        const rooms     = state.rooms.slice()
        // push? update based on creation/update timestamp.
        rooms.push(room)

        this.setState({
            rooms: rooms
        })
    }

    render ( )
    {
        const { props, state } = this;
        const me               = this;
        
        const ActionBar = h(frappe.Chat.Widget.ActionBar,
        {
            actions:
            [
                {
                    label: __("New Message"),
                     icon: "octicon octicon-comment",
                    click: function ( )
                    {
                        const dialog = new frappe.ui.Dialog({
                              title: __("New Message"),
                            animate: false,
                             fields: [
                                {
                                        label: __("Select User"),
                                    fieldname: "user",
                                    fieldtype: "Link",
                                      options: "User",
                                         reqd: true,
                                      filters: { name: ["!=", frappe.session.user] }
                                }
                             ],
                             action:
                             {
                                primary:
                                {
                                    label: __("Create"),
                                    click: function (user)
                                    {
                                        dialog.hide();
                                    }
                                },
                                secondary:
                                {
                                    label: frappe._.is_mobile() ? "<b>&times;</b>" : __(`Cancel`)
                                }
                             }
                        });
                        dialog.show();
                    }
                },
                {
                    label: __("New Group"),
                     icon: "octicon octicon-organization",
                    click: function ( )
                    {
                        const dialog = new frappe.ui.Dialog({
                              title: __("New Group"),
                            animate: false,
                             fields: [
                                {
                                        label: __("Name"),
                                    fieldname: "name",
                                    fieldtype: "Data",
                                         reqd: true
                                },
                                {   
                                        label: __("Select Users"),
                                    fieldname: "users",
                                    fieldtype: "MultiSelect",
                                      options: Object.keys(frappe.boot.user_info).map(key => frappe.boot.user_info[key].email)
                                }
                             ],
                             action:
                             {
                                primary:
                                {
                                    label: __(`Create`),
                                    click: function ({ name, users })
                                    {
                                        dialog.hide();


                                    }
                                },
                                secondary:
                                {
                                    label: frappe._.is_mobile() ? "<b>&times;</b>" : __(`Cancel`)
                                }
                             }
                        });
                        dialog.show();
                    }
                }
            ],
            change: function (query)
            {
                me.setState({
                    query: query
                });
            }
        });

        const rooms      = state.query ? frappe.chat.room.search(state.query, state.rooms) : state.rooms
        
        const RoomList   = h(frappe.Chat.Widget.RoomList, { rooms: rooms });
        const Room       = h(frappe.Chat.Widget.Room, { ...state.room, layout: props.layout });

        const component  = props.layout === frappe.Chat.Layout.POPPER ?
            state.profile.display_widget ?
                h(frappe.Chat.Widget.Popper,
                    state.room.name ?
                        Room
                        :
                        h("span", null,
                            ActionBar, RoomList
                        )
                )
                :
                null
            :
            h("div", { class: "row" },
                h("div", { class: "col-md-2  col-sm-3" },
                    ActionBar, RoomList
                ),
                h("div", { class: "col-md-10 col-sm-9" },

                )
            );
        
        return component ?
            h("div", { class: "frappe-chat" },
                component
            )
            :
            null
    }
}
frappe.Chat.Widget.defaultStates
= 
{
      query: "",
    profile: { },
      rooms: [ ],
       room: 
       {
               name: null,
           messages: [ ]
       }
};
frappe.Chat.Widget.defaultProps =
{
    layout: frappe.Chat.Layout.POPPER
};

/**
 * @description Chat Widget Popper HOC.
 */
frappe.Chat.Widget.Popper
=
class extends Component
{
    constructor (props) {
        super (props)

        this.state = frappe.Chat.Widget.Popper.defaultState
    }

    render ( ) {
        const { props, state } = this
        
        return (
            h("div", { class: "frappe-chat-popper" },
                h(frappe.components.FAB, {
                      class: "frappe-fab",
                       icon: state.active ? "fa fa-fw fa-times" : "octicon octicon-comment",
                       size: frappe._.is_mobile() ? "small" : "large",
                       type: "primary", "data-toggle": "dropdown",
                    onclick: () =>
                    {
                        const active = state.active ? false : true;

                        this.setState({ active });
                    }},
                ),
                state.active ?
                    h("div", { class: "frappe-chat-popper-collapse" },
                        h("div", { class: `panel panel-default ${frappe._.is_mobile() ? "panel-span" : ""}` },
                            frappe._.is_mobile() ?
                                h("div", { class: "panel-heading" },
                                    h("div", { class: "row" },
                                        h("div", { class: "col-xs-9" }),
                                        h("div", { class: "col-xs-3" },
                                            h("div", { class: "text-right" },
                                                h("a", { onclick: () =>
                                                {
                                                    this.setState({ active: false });
                                                }},
                                                    h(frappe.components.Octicon, { type: "x" })
                                                )
                                            )
                                        )
                                    )
                                )
                                :
                                null,
                            h("div", { class: "panel-body" },
                                props.children
                            )
                        )
                    )
                    :
                    null
            )
        );
    }
};
frappe.Chat.Widget.Popper.defaultState =
{
    active: false
};

/**
 * @description Chat.Widget Action Bar Component
 */
frappe.Chat.Widget.ActionBar
=
class extends Component
{
    constructor (props)
    {
        super (props);
;
        this.change = this.change.bind(this);
        this.submit = this.submit.bind(this);

        this.state  = frappe.Chat.Widget.ActionBar.defaultState;
    }

    change (e)
    {
        const { props, state } = this;

        this.setState({
            [e.target.name]: e.target.value
        });

        props.change(state.query);
    }

    submit (e)
    {
        const { props, state } = this;
        
        e.preventDefault();

        props.submit(state.query);
    }

    render ( )
    {
        const { props, state } = this;

        return (
            h("form", { oninput: this.change, onsubmit: this.submit },
                h("div", { class: "form-group" },
                    h("div", { class: "input-group input-group-sm" },
                        h("div", { class: "input-group-addon" },
                            h(frappe.components.Octicon, { type: "search" })
                        ),
                        h("input", { class: "form-control", name: "query", value: state.query, placeholder: "Search" }),
                        h("div", { class: "input-group-btn" },
                            h(frappe.components.Button, { type: "primary", class: "dropdown-toggle", "data-toggle": "dropdown" },
                                h(frappe.components.Octicon, { type: "plus" })
                            ),
                            h("ul", { class: "dropdown-menu dropdown-menu-right" },
                                props.actions.map(action =>
                                    h("li", null,
                                        h("a", { onclick: action.click },
                                            h(frappe.Chat.Widget.ActionBar.Action, { ...action })
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        );
    }
};
frappe.Chat.Widget.ActionBar.defaultState =
{
    query: null
};

/**
 * @description ActionBar's Action.
 */
frappe.Chat.Widget.ActionBar.Action
=
class extends Component
{
    render ( )
    {
        const { props } = this;

        return (
            h("span", null,
                props.icon ?
                    h("i", { class: props.icon })
                    :
                    null,
                `${props.icon ? " " : ""}${props.label}`
            )
        );
    }
};

/**
 * @description Room List HOC
 */
frappe.Chat.Widget.RoomList
=
class extends Component
{
    render ( )
    {
        const { props } = this
        const rooms     = props.rooms;

        return rooms.length ?
            h("ul", { class: "nav nav-pills nav-stacked" },
                rooms.map(room => h(frappe.Chat.Widget.RoomList.Item, { ...room, click: props.click }))
            )
            :
            null
    }
}

/**
 * @description Room List Item
 */
frappe.Chat.Widget.RoomList.Item
=
class extends Component
{
    render ( )
    {
        const { props } = this;

        return (
            h("li", null,
                h("a", { class: props.active ? "active": "", onclick: () => props.click(props.name) },
                    h(frappe.Chat.Widget.MediaProfile, {
                        title: props.type === "Group" ? props.room_name :
                            props.owner === frappe.session.user ?
                                frappe.user.full_name(frappe._.squash(props.users))
                                :
                                frappe.user.full_name(props.owner),
                        image: props.type === "Group" ? props.avatar    :
                            props.owner === frappe.session.user ?
                                frappe.user.image(frappe._.squash(props.users))
                                :
                                frappe.user.image(props.owner),
                         size: "small",
                    })
                )
            )
        )
    }
}

/**
 * @description Chat Room HOC
 */
frappe.Chat.Widget.Room
=
class extends Component
{
    constructor (props)
    {
        super (props);

        this.on_typing = this.on_typing.bind(this);
        this.on_submit = this.on_submit.bind(this);
    }

    on_typing (what) {
        // const { props } = this

        // frappe.realtime.publish("frappe.chat:room:typing",
        //     { room: props.name, user: frappe.session.user })
    }

    on_submit (message) {
        const { props } = this
        const room      = props.name

        frappe.chat.message.send(room, message)
    }

    render ( ) {
        const { props, state } = this

        return (
            h("div", { class: "frappe-chat-room" },
                props.name ?
                    h("div", { class: "panel panel-default", style: `${props.layout === frappe.Chat.Layout.POPPER ? "" : "height: 720px;"}` + "overflow-y: scroll;" },
                        h(frappe.Chat.Widget.Room.Header, { ...props, click_phone: null }),
                        h(frappe.Chat.Widget.ChatList, {
                            messages: props.messages
                        }),
                        h("div", { class: "panel-body" },
                            h(frappe.Chat.Widget.ChatForm, {
                                on_change: this.on_typing,
                                on_submit: this.on_submit
                            })
                        )
                    )
                    :
                    h("div", { style: "margin-top: 240px;" },
                        h("div", { class: "text-center" },
                            h("i", { class: "octicon octicon-comment-discussion text-extra-muted", style: "font-size: 48px" }),
                            h("p", { class: "text-extra-muted" }, "Select a chat to start messaging.")
                        )
                    )
            )
        )
    }
}
frappe.Chat.Widget.Room.Header
=
class extends Component {
    render ( ) {
        const { props } = this
        
        return (
            h("div", { class: "panel-heading" },
                h("div", { class: "row" },
                    h("div", { class: "col-xs-9" },
                        h("div", { class: "panel-title" },
                            h(frappe.Chat.Widget.MediaProfile, {
                                title: props.type === "Group" ? props.room_name :
                                    props.owner === frappe.session.user ?
                                        frappe.user.full_name(frappe._.squash(props.users))
                                        :
                                        frappe.user.full_name(props.owner),
                                image: props.type === "Group" ? props.avatar    :
                                    props.owner === frappe.session.user ?
                                        frappe.user.image(frappe._.squash(props.users))
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
                                        `${props.users.length} ${frappe.utils.pluralize("member", props.users.length)}`
                            })
                        )
                    ),
                    h("div", { class: "col-xs-3" },
                        h("div", { class: "text-right" },
                            // Button ToolBar
                            h("a", null,
                                h("i", { class: "", onclick: props.click_phone })
                            )
                        )
                    )
                )
            )
            
        )
    }
};

frappe.Chat.Widget.Account
=
class extends Component {
    render ( ) {
        const { props } = this
        const statuses  = frappe.chat.profile.STATUSES.map(s => {
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




frappe.Chat.Widget.MediaProfile
=
class extends Component {
    render ( ) {
        const { props } = this
        const position  = props.position === "right" ? "media-right" : "media-left"
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
                position === "media-left" ?
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
                position === "media-right" ?
                    avatar : null
            )
        )
    }
}

/**
 * @description Chat List HOC
 * 
 * 
 */
frappe.Chat.Widget.ChatList
=
class extends Component {
    render ( ) {
        const { props } = this
        
        return props.messages && props.messages.length
            ?
            (
                h("ul", { class: "list-group" },
                    props.messages.map(m => h(frappe.Chat.Widget.ChatList.Item, {
                        ...m
                    }))
                )
            ) : null
    }
}

frappe.Chat.Widget.ChatList.Item
=
class extends Component {
    render ( ) {
        const { props } = this

        return (
            h("li", { class: "list-group-item", style: "border: none !important;" },
                h(frappe.Chat.Widget.ChatList.Bubble, props)
            )
        )
    }
}

frappe.Chat.Widget.ChatList.Bubble
=
class extends Component {
    render ( ) {
        const { props } = this
        const bubble    = (
            h(frappe.Chat.Widget.MediaProfile, {
                      title: frappe.user.full_name(props.user),
                      image: frappe.user.image(props.user),
                   subtitle: frappe.Chat.Widget.get_datetime_string(new Date(props.creation)),
                    content: props.content,
                width_title: "100%",
                   position: frappe.user.full_name(props.user) === "You" ? "right" : "left"
            })
        )

        return (
            h("div", { class: "row" },
                frappe.user.full_name(props.user) !== "You" ?
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
frappe.Chat.Widget.ChatList.Bubble.defaultState = {
    creation: ""
}

frappe.Chat.Widget.ChatForm
=
class extends Component {
    constructor (props) {
        super (props)

        this.on_change = this.on_change.bind(this)
        this.on_submit = this.on_submit.bind(this)

        this.on_click_camera = this.on_click_camera.bind(this)
        this.on_click_file = this.on_click_file.bind(this)

        this.state     = frappe.Chat.Widget.ChatForm.defaultState
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

    on_click_camera ( ) {
        const capture = new frappe.ui.Capture()
        capture.open()
        catpure.click((dataURI) => {
            console.log(dataURI)
        })
    }

    on_click_file ( ) {
        const dialog = new frappe.ui.Dialog({
            title: __("Upload"),
            fields: [
                {fieldtype:"HTML", fieldname:"upload_area"},
                {fieldtype:"HTML", fieldname:"or_attach", options: __("Or")},
                {fieldtype:"Select", fieldname:"select", label:__("Select from existing attachments") },
                {fieldtype:"Button", fieldname:"clear",
                    label:__("Clear Attachment"), click: function() {
                        // me.clear_attachment();
                        dialog.hide();
                    }
                },
            ]
        })

        dialog.show();
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
                                            h("a", { onclick: this.on_click_camera },
                                                h("i", { class: "octicon octicon-device-camera" }), " Camera"
                                            )
                                        ),
                                        h("li", null,
                                            h("a", { onclick: this.on_click_file },
                                                h("i", { class: "fa fa-fw fa-file" }), " File"
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
                                // h("button", { class: "btn btn-primary" },
                                //     h("i", { class: "fa fa-fw fa-smile-o" })
                                // ),
                                    h("div", { class: "btn-group dropup" },
                                        h("button", { class: "btn btn-primary dropdown-toggle", "data-toggle": "dropdown" },
                                            h("i", { class: "fa fa-fw fa-smile-o" })
                                        ),
                                        h("div", { class: "dropdown-menu dropdown-menu-right", style: "min-width: 150px" },
                                            h(frappe.Chat.Widget.EmojiPicker)
                                            // h("li", null,
                                            //     h("a", { onclick: this.on_click_camera },
                                            //         h("i", { class: "octicon octicon-device-camera" }), " Camera"
                                            //     )
                                            // ),
                                            // h("li", null,
                                            //     h("a", { onclick: this.on_click_file },
                                            //         h("i", { class: "fa fa-fw fa-file" }), " File"
                                            //     )
                                            // )
                                        )
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
frappe.Chat.Widget.ChatForm.defaultState = {
    content: null
}

frappe.Chat.Widget.EmojiPicker 
=
class extends Component {
    render ( ) {
        return (
            h("div", { class: "panel panel-default" },
                h("div", { class: "panel-body" },
            
                )
            )
        )
    }
}


































frappe.Chat.Widget.get_datetime_string   = (date) => {
    const instance = moment(date)
    const today    = moment()
    
    if ( today.isSame(instance, "d") ) {
        return today.format("hh:mm A") 
    } else 
    if ( today.isSame(instance, "week") ) {
        return today.format("dddd")
    } else {
        return today.format("DD/MM/YYYY")
    }
}

// frappe.components.Indicator
// Props
// color - (Required) color for the indicator
frappe.components.Indicator
=
class extends Component
{
    render ( ) {
        const { props } = this;

        return props.color ? (
            h("span", { class: `indicator ${props.color}` })
        ) : null;
    }
};

// frappe.components.Avatar
// NOTE  - styles at avatar.less
// title - (Required) title for the avatar.
// abbr  - (Optional) abbreviation for the avatar, defaults to the first letter of the title.
// size  - (Optional) size of the avatar to be displayed.
// image - (Optional) image for the avatar, defaults to the first letter of the title.
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

// frappe.components.Select
// options - (Required) array of options of the format
// {
//    label: "foo",
//    value: "bar"
// }
// value   - (Required) default value.
// click   - (Optional) click handler on click event.
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

frappe.chat.profile.update
=
function (user, update, fn)
{
    return new Promise(resolve => 
    {
        frappe.call("frappe.chat.doctype.chat_profile.chat_profile.update",
            { user: user || frappe.session.user, data: update },
                response => 
                {
                    if ( fn )
                        fn(response.message)
                    
                    resolve(response.message)
                });
    });
};

frappe.chat.room.history
=
function (name, fn)
{
    return new Promise(resolve =>
    {
        frappe.call("frappe.chat.doctype.chat_room.chat_room.get_history",
            { room: name },
                r =>
                {
                    const messages = r.message ? r.message : [ ] // frappe.api BOGZ! (emtpy arrays are falsified, not good design).

                    if ( fn )
                        fn(messages)
                    
                    resolve(messages)
                });
    });
};

frappe.chat.room.on = { }
frappe.chat.room.on.create
=
(fn) => frappe.realtime.on("frappe.chat.room.create", r => fn(r))

frappe.chat.room.on.update
=
(fn) => frappe.realtime.on("frappe.chat.room.update", r => fn(r.room, r.data))

frappe.chat.message = { }
frappe.chat.message.send 
=
(room, message) =>
{
    frappe.call("frappe.chat.doctype.chat_message.chat_message.send",
        { user: frappe.session.user, room: room, content: message.content })
}

frappe.chat.message.on   = { }
frappe.chat.message.on.create
=
(fn) => frappe.realtime.on("frappe.chat.message.create", r => fn(r))