// frappe Chat
// Author - Achilles Rasquinha <achilles@frappe.io>

// frappe.loggers - A registry for frappe loggers.
frappe.loggers = Object();

/**
 * @description Frappe's Logger Class
 * 
 * @example
 * frappe.log       = frappe.Logger.get('foobar');
 * frappe.log.level = frappe.Logger.DEBUG;
 * 
 * frappe.log.debug('foobar');
 * // prints 'foobar:foobar'
 */
frappe.Logger = class
{
    /**
     * @description Frappe's Logger Class's constructor.
     * 
     * @param {string} name - Name of the logger.
     */
    constructor (name)
    {
        if ( typeof name !== 'string' )
            throw new frappe.TypeError(`Expected string for name, got ${typeof name} instead.`);

        this.name  = name;
        this.level = frappe.Logger.NOTSET;
    }

    /**
     * @description Set the level of the logger.
     * 
     * @param {level} level - Level of the logger.
     * 
     * @example
     * frappe.log = new frappe.get_logger('foobar');
     * frappe.log.set_level(frappe.Logger.DEBUG);
     */
    set_level (level)
    {
        this.level = level;
    }

    debug (message)
    {
        if ( this.level === frappe.Logger.DEBUG )
            console.log(`${this.name}: ${message}`);
    }
};

frappe.Logger.NOTSET =  0
frappe.Logger.DEBUG  = 10

frappe.get_logger    = function (name)
{
    if ( !(name in frappe.loggers) )
        frappe.loggers[name] = new frappe.Logger(name);
    
    return frappe.loggers[name];
};

frappe.log = frappe.get_logger('frappe.chat');
frappe.log.set_level(frappe.Logger.DEBUG);

/**
 * @description FrappeError
 * 
 * @example
 * try
 *      throw new frappe.Error("foobar");
 * catch (e)
 *      console.log(e.name); // returns FrappeError
 */
frappe.Error   = class extends Error
{
    constructor (message)
    {
        super (message);

        this.name  = 'FrappeError';
        this.stack = (new Error()).stack;
    }
};

/**
 * @description TypeError
 * 
 * @example
 * try
 *      throw new frappe.TypeError("foobar");
 * catch (e)
 *      console.log(e.name); // returns TypeError
 */
 frappe.TypeError = class extends TypeError { };

/**
 * @description ValueError
 * 
 * @example
 * try
 *      throw new frappe.ValueError("foobar");
 * catch (e)
 *      console.log(e.name); // returns ValueError
 */
frappe.ValueError = class extends frappe.Error
{
    constructor (message)
    {
        super (message);

        this.name     = 'ValueError';
        this.stack    = (new Error()).stack;
    }
};

// frappe._
// frappe's utility namespace.
frappe.provide('frappe._');

/**
 * @description Fuzzy Search a given query within a dataset.
 * 
 * @param   {string} query   - A query string.
 * @param   {array}  dataset - A dataset to search within, can contain singletons or objects.
 * @param   {object} options - Options as per fuze.js
 * 
 * @returns {array}          - The fuzzy matched index/object within the dataset.
 * 
 * @example
 * frappe._.fuzzy_search("foobar", ["foobar", "bartender"]);
 * // returns [0, 1];
 * 
 * @see http://fusejs.io
 */
frappe._.fuzzy_search = function (query, dataset, options)
{
    const DEFAULT     =
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
 * @description Pluralizes a given word.
 * 
 * @param   {string} word  - The word to be pluralized.
 * @param   {number} count - The count.
 * 
 * @returns {string}       - The pluralized string.
 * 
 * @todo Handle more edge cases.
 */
frappe._.pluralize  = function (word, count = 0, suffix = 's')
{
    return `${word}${count === 1 ? '' : suffix}`;
};

frappe._.capitalize = function (word)
{
    return `${word.charAt(0).toUpperCase()}${word.slice(1)}`;
};

/**
 * @description Returns a copy of the given array (shallow).
 * 
 * @param   {array} array - The array to be copied.
 * 
 * @returns {array}       - The copied array.
 * 
 * @example
 * frappe._.copy_array(["foobar", "barfoo"]);
 * // returns ["foobar", "barfoo"]
 * 
 * @todo Add optional deep copy.
 */
frappe._.copy_array = function (array)
{
    if ( Array.isArray(array) )
        return array.slice();
    else
        throw frappe.TypeError(`Expected Array, recieved ${typeof array} instead.`);
};

frappe._.is_empty   = function (what)
{
    return Object.keys(what).length === 0;
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
 * 
 * @see https://docs.oracle.com/javase/8/docs/api/java/util/Arrays.html#asList-T...-
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
 * @returns {array|object}      - Returns an array if there's more than 1 object else the first object itself.
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
    const mobile   = regex.test(agent);

    return mobile;
};

/**
 * @description Returns 1, 0 or -1 if a < b, a > b or a == b respectively.
 * 
 * @returns {number} 1, 0 or -1
 * 
 * @example
 * frappe._.compare(1, 2);
 * // returns  1
 * frappe._.compare(2, 1);
 * // returns -1
 * frappe._.compare(1, 1);
 * // returns  0
 */
frappe._.compare = function (a, b)
{
    if ( a < b )
        return  1;
    else
    if ( a > b )
        return -1;
    else
        return  0;
};

// frappe.chat
frappe.provide('frappe.chat');

// frappe.chat.profile
frappe.provide('frappe.chat.profile');

/**
 * @description Create a Chat Profile.
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
frappe.chat.profile.create = function (fields, fn)
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
                        fn(response.message);
                    
                    resolve(response.message);
                });
    });
};

// frappe.chat.profile.on.
frappe.provide('frappe.chat.profile.on');

/**
 * @description Triggers on a Chat Profile update of a user (Only if there's a one-on-one conversation).
 * 
 * @param   {function} fn - (Optional) callback with the User and the Chat Profile update.
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.profile.on.update(function (user, update)
 * {
 *      // do stuff
 * });
 */
frappe.chat.profile.on.update = function (fn)
{
    frappe.realtime.on("frappe.chat.profile:update", r => fn(r.user, r.data));
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
 * @description Creates a Chat Room.
 * 
 * @param   {string}       kind  - (Required) "Direct", "Group" or "Visitor".
 * @param   {string}       owner - (Optional) Chat Room owner (defaults to current user).
 * @param   {string|array} users - (Required for "Direct" and "Visitor", Optional for "Group") User(s) within Chat Room.
 * @param   {string}       name  - Chat Room name.
 * @param   {function}     fn    - callback with created Chat Room.
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.room.create("Direct", frappe.session.user, "foo@bar.com", function (room) {
 *      // do stuff
 * });
 * frappe.chat.room.create("Group",  frappe.session.user, ["santa@gmail.com", "banta@gmail.com"], "Santa and Banta", function (room) {
 *      // do stuff
 * });
 */
frappe.chat.room.create = function (kind, owner, users, name, fn)
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
 * @description Returns Chat Room(s).
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
 * 
 * frappe.chat.room.get(["CR00001", "CR00002"], ["room_name", "last_message_timestamp"], function (rooms) {
 * 
 * });
 */
frappe.chat.room.get = function (names, fields, fn)
{
    if ( typeof names === "function" )
    {
        fn     = names;
        names  = null;
        fields = null;
    }
    else
    if ( typeof names === "string" )
    {
        names  = frappe._.as_array(names);

        if ( typeof fields === "function" ) {
            fn     = fields;
            fields = null;
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
                    var rooms = response.message;
                    if ( rooms ) // frappe.api BOGZ! (emtpy arrays are falsified, not good design).
                    {
                        rooms = rooms.map(room =>
                        {
                            return { ...room, creation: moment(room.creation),
                                last_message_timestamp: room.last_message_timestamp && moment(room.last_message_timestamp) };
                        });
                        rooms = frappe._.squash(rooms);
                    }
                    else
                    {
                        rooms = [ ];
                    }

                    if ( fn )
                        fn(rooms);

                    resolve(rooms);
                });
    });
};

/**
 * @description Subscribe current user to said Chat Room(s).
 * 
 * @param {string|array} rooms - Chat Room(s).
 * 
 * @example
 * frappe.chat.room.subscribe("CR00001");
 */
frappe.chat.room.subscribe = function (rooms)
{
    frappe.realtime.publish("frappe.chat:subscribe", rooms);
};

/**
 * @description Get Chat Room history.
 * 
 * @param   {string} name - Chat Room name
 * 
 * @returns {Promise}     - Chat Message(s)
 * 
 * @example
 * frappe.chat.room.history(function (messages)
 * {
 *      // do stuff.
 * });
 */
frappe.chat.room.history = function (name, fn)
{
    return new Promise(resolve =>
    {
        frappe.call("frappe.chat.doctype.chat_room.chat_room.get_history",
            { room: name },
                r =>
                {
                    const messages = r.message ? r.message : [ ] // frappe.api BOGZ! (emtpy arrays are falsified, not good design).

                    if ( fn )
                        fn(messages);
                    
                    resolve(messages);
                });
    });
};

/**
 * @description Searches Rooms based on a query.
 * 
 * @param   {string} query - The query string.
 * @param   {array}  rooms - A list of Chat Rooms.
 * 
 * @returns {array}        - A fuzzy searched list of rooms.
 */
frappe.chat.room.search = function (query, rooms)
{
    const dataset = rooms.map(r =>
    {
        if ( r.room_name )
            return r.room_name;
        else
            if ( r.owner === frappe.session.user )
                return frappe.user.full_name(frappe._.squash(r.users));
            else
                return frappe.user.full_name(r.owner);
    });
    const results = frappe._.fuzzy_search(query, dataset);
    rooms         = results.map(i => rooms[i]);

    return rooms;
};

/**
 * @description Sort Chat Room(s) based on Last Message Timestamp or Creation Date.
 * 
 * @param {array}   - A list of Chat Room(s)
 * @param {compare} - (Optional) a comparision function.
 */
frappe.chat.room.sort = function (rooms, compare = null)
{
    compare = compare || function (a, b)
    {
        if ( a.last_message_timestamp && b.last_message_timestamp )
            return frappe._.compare(a.last_message_timestamp, b.last_message_timestamp);
        else
        {
            if ( a.last_message_timestamp )
                return frappe._.compare(a.last_message_timestamp, b.creation);
            else
            if ( b.last_message_timestamp )
                return frappe._.compare(b.last_message_timestamp, a.creation);
            else
                return frappe._.compare(a.creation, b.creation);
        }
    };
    rooms.sort(compare);

    return rooms;
};

// frappe.chat.room.on
frappe.provide('frappe.chat.room.on');

/**
 * @description Triggers on Chat Room updated.
 * 
 * @param {function} fn - callback with the Chat Room and Update.
 */
frappe.chat.room.on.update = fn => frappe.realtime.on("frappe.chat.room:update", r => fn(r.room, r.data));

/**
 * @description Triggers on Chat Room created.
 * 
 * @param {function} fn - callback with the created Chat Room.
 */
frappe.chat.room.on.create = function (fn)
{
    frappe.realtime.on("frappe.chat.room.create", r => fn(r));
};

// frappe.chat.emoji
frappe.chat.emojis = Object();
frappe.chat.emoji  = function (fn)
{
    return new Promise(resolve => {
        if ( !frappe._.is_empty(frappe.chat.emojis) )
            fn(frappe.chat.emojis);
        else
            $.get('https://api.github.com/emojis', (data) => {
                frappe.chat.emojis = data;

                fn(frappe.chat.emojis);
            })
    })
}

const { h, Component } = hyper;

// frappe.components
// frappe's component namespace.
frappe.provide('frappe.components');

/**
 * @description Button Component
 * 
 * @prop {string}  type  - (Optional) "default", "primary", "info", "success", "warning", "danger" (defaults to "default")
 * @prop {boolean} block - (Optional) Render a button block (defaults to false).
 * 
 * @extends Component
 */
frappe.components.Button = class extends Component
{
    render ( )
    {
        const { props } = this;

        return (
            h("button", { ...props, class: `btn btn-${props.type} ${props.block ? "btn-block" : ""} ${props.class ? props.class : ""}` },
                props.children
            )
        );
    }
};
frappe.components.Button.defaultProps
=
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
            h(frappe.components.Button, { ...props, class: `${props.class} ${size && size.class}`},
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
 * 
 * @extends frappe.Component
 *
 * @prop color - (Required) color for the indicator
 */
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

/**
 * @description FontAwesome Component
 * 
 * @extends frappe.Component
 */
frappe.components.FontAwesome
=
class extends Component
{
    render ( )
    {
        const { props } = this;

        return props.type ?
            h("i", { class: `fa ${props.fixed ? "fa-fw" : ""} fa-${props.type}` })
            :
            null;
    }
};
frappe.components.FontAwesome.defaultProps
=
{
    fixed: false
};

/**
 * @description Octicon Component
 * 
 * @extends frappe.Component
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
 * @description Avatar Component
 * 
 * @prop {string} title - (Optional) title for the avatar.
 * @prop {string} abbr  - (Optional) abbreviation for the avatar, defaults to the first letter of the title.
 * @prop {string} size  - (Optional) size of the avatar to be displayed.
 * @prop {image}  image - (Optional) image for the avatar, defaults to the first letter of the title.
 */
frappe.components.Avatar
=
class extends Component
{
    render ( )
    {
        const { props } = this
        const abbr      = props.abbr || props.title.substr(0, 1)
        const size      = frappe.components.Avatar.SIZE[props.size] || { class: "avatar-medium" };

        return (
            h("span", { class: `avatar ${size.class}` },
                props.image ?
                    h("img", { class: "media-object", src: props.image })
                    :
                    h("div", { class: "standard-image" }, abbr)
            )
        );
    }
};
frappe.components.Avatar.SIZE
=
{
    small:
    {
        class: "avatar-small"
    },
    large:
    {
        class: "avatar-large"
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
     * 
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
     * @param   {string|HTMLElement} selector - A query selector, HTML Element or jQuery object.
     * 
     * @returns {frappe.Chat}                 - The instance.
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
     * @param   {object}      options - Optional Configurations.
     * 
     * @returns {frappe.Chat}         - The instance.
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
     * @returns {frappe.Chat} - The instance.
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
     * @returns {frappe.Chat} - The instance.
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

        this.room           = { };
        this.room.add       = (rooms) =>
        {   
            const state     = [ ];
            rooms           = frappe._.as_array(rooms);
            const names     = rooms.map(r => r.name);

            frappe.log.debug(`Subscribing ${frappe.session.user} to Chat Rooms ${names.join(", ")}.`);
            frappe.chat.room.subscribe(names);

            for (const room of rooms )
            {
                if ( room.type === "Group" || room.owner === frappe.session.user || room.last_message_timestamp )
                {
                    frappe.log.debug(`Adding ${room.name} to component.`);
                    state.push(room);
                }
            }

            this.setState({ rooms: [ ...this.state.rooms, ...state ] });
        };
        this.room.update    = (room, update) =>
        {
            const { state } = this;
            const rooms     = state.rooms.map(r =>
            {
                if ( r.name === room )
                    return { ...r, ...update };
                return r;
            });

            this.setState({ rooms });

            if ( state.room.name === room )
            {
                const room  = { ...state.room, ...update };

                this.setState({ room });
            }
        };
        this.room.select    = (name) =>
        {
            frappe.chat.room.history(name, (messages) =>
            {
                const  { state } = this;
                const room       = state.rooms.find(r => r.name === name);
                
                this.setState({
                    room: { ...state.room, ...room, messages: messages }
                });
            });
        }
        
        this.state          =
        {
              query: "",
            profile: { },
              rooms: [ ],
               room: { name: null, messages: [ ] }
        };

        this.make();
    }

    make ( ) {
        frappe.chat.profile.create(["status", "display_widget"], profile =>
        {
            frappe.log.debug(`Chat Profile created for User ${frappe.session.user}.`)
            this.setState({ profile });

            frappe.chat.room.get(rooms =>
            {
                frappe.log.debug(`User ${frappe.session.user} is subscribed to ${rooms.length} rooms.`);

                if ( rooms.length )
                    this.room.add(rooms);
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

        frappe.chat.room.on.create((room) =>
        {
            this.room.add(room);
        });

        frappe.chat.room.on.update((room, update) =>
        {
            frappe.log.debug(`Chat Room ${room} update ${JSON.stringify(update)} recieved.`);
            this.room.update(room, update);
        });
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
                                      filters: { name: ["!=", frappe.session.user] } // not working?
                                }
                             ],
                             action:
                             {
                                primary:
                                {
                                    label: __("Create"),
                                    click: function ({ user })
                                    {
                                        dialog.hide();
                                        
                                        // Don't Worry, frappe.chat.room.on.create gets triggered that then subscribes and adds to DOM. :)
                                        frappe.chat.room.create("Direct", null, user);
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
                                        
                                        // MultiSelect, y u no JSON? :(
                                        if ( users )
                                        {
                                            users = users.split(", ")
                                            users = users.slice(0, users.length - 1);
                                        }
                                        
                                        // Don't Worry, frappe.chat.room.on.create gets triggered that then subscribes and adds to DOM. :)
                                        frappe.chat.room.create("Group", null, users, name);
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

        const rooms      = state.query ? frappe.chat.room.search(state.query, state.rooms) : frappe.chat.room.sort(state.rooms)
        
        const RoomList   = h(frappe.Chat.Widget.RoomList, { rooms: rooms, click: this.room.select });
        const Room       = h(frappe.Chat.Widget.Room, { ...state.room, layout: props.layout, destroy: () => {
            this.setState({
                room: { name: null, messages: [ ] }
            });
        }});

        const component  = props.layout === frappe.Chat.Layout.POPPER ?
            state.profile.display_widget ?
                h(frappe.Chat.Widget.Popper, { page: state.room.name && Room },
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
        super (props);

        this.state = frappe.Chat.Widget.Popper.defaultState;
    }

    render  ( )
    {
        const { props, state } = this;
        
        return !state.destroy ? 
        (
            h("div", { class: "frappe-chat-popper" },
                h(frappe.components.FAB, {
                      class: "frappe-fab",
                       icon: state.active ? "fa fa-fw fa-times" : "octicon octicon-comment",
                       size: frappe._.is_mobile() ? null : "large",
                       type: "primary", "data-toggle": "dropdown",
                    onclick: () =>
                    {
                        const active = state.active ? false : true;

                        this.setState({ active });
                    }},
                ),
                state.active ?
                    h("div", { class: "frappe-chat-popper-collapse" },
                        props.page ?
                            props.page
                            :
                        h("div", { class: `panel panel-primary ${frappe._.is_mobile() ? "panel-span" : ""}` },
                            h("div", { class: "panel-heading" },
                                h("div", { class: "row" },
                                    h("div", { class: "col-xs-9" }),
                                    h("div", { class: "col-xs-3" },
                                        h("div", { class: "text-right" },
                                            frappe._.is_mobile() ?
                                                h("a", { onclick: () =>
                                                {
                                                    this.setState({ active: false });
                                                }},
                                                    h(frappe.components.Octicon, { type: "x" })
                                                )
                                                :
                                                h("a", { onclick: () =>
                                                {
                                                    frappe.set_route('chat');
                                                }},
                                                    h(frappe.components.FontAwesome, { type: "expand", fixed: true })
                                                )
                                        )
                                    )
                                )
                            ),
                            h("div", { class: "panel-body" },
                                props.children
                            )
                        )
                    ) : null
            )
        ) : null;
    }
};
frappe.Chat.Widget.Popper.defaultState
=
{
     active: false,
    destroy: false
};

/**
 * @description frappe.Chat.Widget ActionBar Component
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
                        Array.isArray(props.actions) ?
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
                            ) : null
                    )
                )
            )
        );
    }
};
frappe.Chat.Widget.ActionBar.defaultState
=
{
    query: null
};

/**
 * @description frappe.Chat.Widget ActionBar's Action Component.
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
 * @description frappe.Chat.Widget RoomList Component
 */
frappe.Chat.Widget.RoomList
=
class extends Component
{
    render ( )
    {
        const { props } = this;
        const rooms     = props.rooms;

        return rooms.length ?
            h("ul", { class: "nav nav-pills nav-stacked" },
                rooms.map(room => h(frappe.Chat.Widget.RoomList.Item, { ...room, click: props.click }))
            )
            :
            null;
    }
}

/**
 * @description frappe.Chat.Widget RoomList's Item Component
 */
frappe.Chat.Widget.RoomList.Item
=
class extends Component
{
    render ( )
    {
        const { props } = this;
        const item      = { };

        if ( props.type === "Group" ) {
            item.title  = props.room_name;
            item.image  = props.avatar;
        } else {
            const user  = props.owner === frappe.session.user ? frappe._.squash(props.users) : props.owner;

            item.title  = frappe.user.full_name(user);
            item.image  = frappe.user.image(user);
            item.abbr   = frappe.user.abbr(user);
        }

        return (
            h("li", null,
                h("a", { class: props.active ? "active": "", onclick: () => props.click(props.name) },
                    h(frappe.Chat.Widget.MediaProfile, { ...item })
                )
            )
        );
    }
};

/**
 * @description frappe.Chat.Widget's MediProfile Component.
 */
frappe.Chat.Widget.MediaProfile
=
class extends Component
{
    render ( )
    {
        const { props } = this
        const position  = frappe.Chat.Widget.MediaProfile.POSITION[props.position || "left"];
        const avatar    = (
            h("div", { class: `${position.class} media-top` },
                h(frappe.components.Avatar, {
                    title: props.title,
                    image: props.image,
                     size: props.size,
                     abbr: props.abbr
                })
            )
        );

        return (
            h("div", { class: "media" },
                position.class === "media-left"  ? avatar : null,
                h("div", { class: "media-body" },
                    h("div", { class: "media-heading h6 ellipsis", style: `max-width: ${props.width_title || "100%"}; display: inline-block;` }, props.title),
                    props.content  ? h("div", null, h("small", { class: "h6" }, props.content))  : null,
                    props.subtitle ? h("div", null, h("small", { class: "h6" }, props.subtitle)) : null
                ),
                position.class === "media-right" ? avatar : null
            )
        );
    }
};

frappe.Chat.Widget.MediaProfile.POSITION
=
{
    left: { class: "media-left" }, right: { class: "media-right" }
};

/**
 * @description frappe.Chat.Widget Room Component
 */
frappe.Chat.Widget.Room
=
class extends Component
{
    render ( )
    {
        const { props, state } = this;

        return (
            h("div", { class: `panel panel-primary ${frappe._.is_mobile() ? "panel-span" : ""}` },
                h(frappe.Chat.Widget.Room.Header, { ...props, back: props.destroy }),
                h(frappe.Chat.Widget.ChatList, {
                    messages: props.messages
                }),
                h("div", { class: "panel-body" },
                    
                ),
                h("div", { class: "panel-footer" },
                    h(frappe.Chat.Widget.ChatForm, {
                        change: console.log,
                        submit: console.log,
                          hint:
                          {
                                match: /^(@\w*)|(:[a-z]*)$/,
                               search: function (keyword, callback)
                               {
                                    if ( keyword.startsWith(':') )
                                    {
                                        const query = keyword.slice(1);
                                        frappe.chat.emoji(function (emojis) {
                                            const names  = Object.keys(emojis);
                                            // let   result = frappe._.fuzzy_search(query, names);
                                            let result   = names.filter((name) => {
                                                return name.indexOf(query) === 0;
                                            });
                                            result       = result.map(r => {
                                                return {
                                                    title: r,
                                                    image: emojis[r]
                                                }
                                            });

                                            callback(result);
                                        });
                                    } else
                                    if ( keyword.startsWith('@') )
                                    {
                                        const query = keyword.slice(1);
                                        let  users = Object.keys(frappe.boot.user_info).filter((name) => {
                                            return name.indexOf(query) === 0;
                                        });
                                        users = users.map(r => {
                                            return {
                                                title: frappe.user.full_name(r),
                                                image: frappe.user.image(r)
                                            }
                                        });

                                        callback(users);
                                    }
                               },
                               component: function (item) {
                                    return h(frappe.Chat.Widget.MediaProfile, { ...item, size: "small" })
                                }
                          }
                    })
                )
            )
        );
    }
};

frappe.Chat.Widget.Room.Header
=
class extends Component
{
    render ( )
    {
        const { props }    = this;

        const item         = { };
        
        if ( props.type === "Group" ) {
            item.route     = `Form/Chat Room/${props.name}`

            item.title     = props.room_name;
            item.image     = props.avatar;
            item.subtitle  = __(`${props.users.length} ${frappe._.pluralize('member', props.users.length)}`);
        }
        else
        {
            const user     = props.owner === frappe.session.user ? frappe._.squash(props.users) : props.owner;

            item.route     = `Form/User/${user}`;

            item.title     = frappe.user.full_name(user);
            item.image     = frappe.user.image(user);
        }

        const popper       = props.layout === frappe.Chat.Layout.POPPER || frappe._.is_mobile();
        
        return (
            h("div", { class: "panel-heading" },
                h("div", { class: "row" },
                    popper ?
                        h("div", { class: "col-xs-1" },
                            h("a", { onclick: props.back }, h(frappe.components.Octicon, { type: "chevron-left" }))
                        )
                        :
                        null,
                    h("div", { class: popper ? "col-xs-10" : "col-xs-9" },
                        h("div", { class: "panel-title" },
                            h("div", { class: "cursor-pointer", onclick: () => { frappe.set_route(item.route) }},
                                h(frappe.Chat.Widget.MediaProfile, { ...item })
                            )
                        )
                    ),
                    h("div", { class: popper ? "col-xs-1"  : "col-xs-3" },
                        h("div", { class: "text-right" },

                        )
                    )
                )
            )
            
        )
    }
};

/**
 * @description Chat Form Component
 */
frappe.Chat.Widget.ChatForm
=
class extends Component {
    constructor (props) {
        super (props);
        
        this.change = this.change.bind(this);
        this.submit = this.submit.bind(this);

        this.state  = frappe.Chat.Widget.ChatForm.defaultState;
    }

    change (e)
    {
        const { props, state } = this;
        const value            = e.target.value;

        this.setState({
            [e.target.name]: value
        });

        props.change(state);

        if ( props.hint )
        {
            const hint   = props.hint;
            const tokens = value.split(" ");

            if ( tokens.length )
            {
                const query = tokens[tokens.length - 1];
                
                if (hint.match.test(query))
                    hint.search(query, (dataset) => {
                        this.setState({
                            hint: dataset
                        })
                    });
                else
                    this.setState({
                        hint: [ ]
                    })
            } else {
                this.setState({
                    hint: [ ]
                })
            }
        }
    }

    submit (e)
    {
        e.preventDefault()

        if ( this.state.content )
        {
            this.props.submit(this.state);

            this.setState({
                content: null
            });
        }
    }

    render ( ) {
        const { props, state } = this;

        return (
            h("div", { class: "frappe-chat-form" },
                state.hint.length ?
                    h("div", { class: "list-group", style: { "max-height": "200px", "overflow-y": "scroll" } },
                        state.hint.map((item) => {
                            return (
                                h("div", { class: "list-group-item" },
                                    props.hint.component(item)
                                )
                            )
                        })
                    ) : null,
                h("form", { oninput: this.change, onsubmit: this.submit },
                    h("div", { class: "input-group input-group-sm" },
                        h("textarea",
                        {
                                    class: "form-control",
                                     name: "content",
                                    value: state.content,
                              placeholder: "Type a message",
                                autofocus: true,
                               onkeypress: (e) =>
                               {
                                    if ( e.which === 13 && !e.shiftKey )
                                        this.submit(e)
                               }
                        }),
                        h("div", { class: "input-group-btn" },
                            // h(frappe.Chat.Widget.EmojiPicker, { class: "btn-group" }),
                            h(frappe.components.Button, { type: "primary", class: "dropdown-toggle", "data-toggle": "dropdown" },
                                h(frappe.components.FontAwesome, { type: "send", fixed: true })
                            ),
                        )
                    )
                )
            )
        )
    }
}
frappe.Chat.Widget.ChatForm.defaultState
=
{
    content: null,
       hint: [ ],
};

frappe.Chat.Widget.EmojiPicker
=
class extends Component 
{
    render ( )
    {
        const { props } = this;

        return (
            h("div", { class: `frappe-chat-emoji dropup ${props.class}` },
                h(frappe.components.Button, { type: "primary", class: "dropdown-toggle", "data-toggle": "dropdown" },
                    h(frappe.components.FontAwesome, { type: "smile-o", fixed: true })
                ),
                h("div", { class: "dropdown-menu dropdown-menu-right", onclick: e => e.stopPropagation() },
                    h("div", { class: "panel panel-default" },
                        h(frappe.Chat.Widget.EmojiPicker.List)
                    )
                )
            )
        );
    }
};
frappe.Chat.Widget.EmojiPicker.List
=
class extends Component
{
    render ( )
    {
        const { props } = this;

        return (
            h("div", { class: "list-group" },
                frappe.ui.Emoji.map((category) =>
                {
                    return (
                        h("div", { class: "list-group-item" },
                            h("div", { class: "h6" }, frappe._.capitalize(category.name)),
                            h("div", null,
                                
                            )
                        )
                    )
                })
            )
        )
    }
}












































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
        const { props } = this;
        const bubble    = (
            h(frappe.Chat.Widget.MediaProfile, {
                      title: frappe.user.full_name(props.user),
                      image: frappe.user.image(props.user),
                   subtitle: frappe.Chat.Widget.get_datetime_string(new Date(props.creation)),
                    content: props.content,
                width_title: "100%",
                   position: frappe.user.full_name(props.user) === "You" ? "right" : "left"
            })
        );

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
        );
    }
};
frappe.Chat.Widget.ChatList.Bubble.defaultState =
{
    creation: ""
};







// subtitle: props.typing && props.typing !== frappe.session.user ? // Am I Typing?
//         props.type === "Group" ?
//             // show name yo.
//             `${frappe.user.get_full_name(props.typing)} typing...`
//             :
//             "typing..."
//         :
//         "",

// constructor (props)
// {
//     super (props);

//     this.on_typing = this.on_typing.bind(this);
//     this.on_submit = this.on_submit.bind(this);
// }

// on_typing (what) {
//     // const { props } = this

//     // frappe.realtime.publish("frappe.chat:room:typing",
//     //     { room: props.name, user: frappe.session.user })
// }

// on_submit (message) {
//     const { props } = this
//     const room      = props.name

//     frappe.chat.message.send(room, message)
// }

// h(frappe.Chat.Widget.ChatForm, {
//     on_change: this.on_typing,
//     on_submit: this.on_submit
// })

// on_change_status (status) {
//     frappe.chat.profile.update(null, {
//         status: status
//     })
// }

// on_select_room (name) {
//     frappe.chat.room.history(name, m => 
//     {
//         const { state } = this
//         const room      = state.rooms.find(r => r.name === name)

//         this.setState({
//              room: { ...state.room, ...room, messages: m }
//         })
//     })
// }?

        
// frappe.chat.message.on.create((r) => 
// {
//     console.log(`Message Recieved - ${JSON.stringify(r)}`)

//     const { state } = this
//     if ( r.room === state.room.name ) {
//         const mess  = state.room.messages.slice()
//         mess.push(r)
        
//         this.setState({
//             room: { ...state.room, messages: mess }
//         })
//     }
// })
// h("div", { class: "input-group-btn" },
// h("div", { class: "btn-group dropup" },
//     h("button", { class: "btn btn-primary dropdown-toggle", "data-toggle": "dropdown" },
//         h("i", { class: "fa fa-fw fa-paperclip" })
//     ),
//     h("div", { class: "dropdown-menu", style: "min-width: 150px" },
//         h("li", null,
//             h("a", { onclick: this.on_click_camera },
//                 h("i", { class: "octicon octicon-device-camera" }), " Camera"
//             )
//         ),
//         h("li", null,
//             h("a", { onclick: this.on_click_file },
//                 h("i", { class: "fa fa-fw fa-file" }), " File"
//             )
//         )
//     )
// )
// ),

// :
// h("div", { style: "margin-top: 240px;" },
//     h("div", { class: "text-center" },
//         h("i", { class: "octicon octicon-comment-discussion text-extra-muted", style: "font-size: 48px" }),
//         h("p", { class: "text-extra-muted" }, "Select a chat to start messaging.")
//     )
// )

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



// on_click_camera ( ) {
//     const capture = new frappe.ui.Capture()
//     capture.open()
//     catpure.click((dataURI) => {
//         console.log(dataURI)
//     })
// }

// on_click_file ( ) {
//     const dialog = new frappe.ui.Dialog({
//         title: __("Upload"),
//         fields: [
//             {fieldtype:"HTML", fieldname:"upload_area"},
//             {fieldtype:"HTML", fieldname:"or_attach", options: __("Or")},
//             {fieldtype:"Select", fieldname:"select", label:__("Select from existing attachments") },
//             {fieldtype:"Button", fieldname:"clear",
//                 label:__("Clear Attachment"), click: function() {
//                     // me.clear_attachment();
//                     dialog.hide();
//                 }
//             },
//         ]
//     })

//     dialog.show();
// }


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