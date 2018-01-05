// Frappe Chat
// Author - Achilles Rasquinha <achilles@frappe.io>

/* eslint semi: "never" */
// Fuck semicolons - https://mislav.net/2010/05/semicolons

// frappe extensions

// frappe.model extensions
frappe.provide('frappe.model')
/**
 * @description Subscribe to a model for realtime updates.
 * 
 * @example
 * frappe.model.subscribe('User')
 * // Subscribe to all User records
 * 
 * frappe.model.subscribe('User', 'achilles@frappe.io')
 * frappe.model.subscribe('User', ['achilles@frappe.io', 'rushabh@frappe.io'])
 * // Subscribe to User of name(s)
 * 
 * frappe.model.subscribe('User', 'achilles@frappe.io', 'username')
 * frappe.model.subscribe('User', ['achilles@frappe.io', 'rushabh@frappe.io'], ['email', 'username'])
 * // Subscribe to User of name for field(s)
 */
frappe.model.subscribe = (doctype, name, field) =>
    frappe.realtime.publish('frappe.model:subscribe', { doctype: doctype, name: name, field: field })

/**
 * @description The base class for all Frappe Errors.
 *
 * @example
 * try
 *      throw new frappe.Error("foobar")
 * catch (e)
 *      console.log(e.name)
 * // returns "FrappeError"
 * 
 * @see  https://stackoverflow.com/a/32749533
 * @todo Requires "transform-builtin-extend" for Babel 6
 */
frappe.Error = class extends Error
{
    constructor (message)
    {
        super (message)

        this.name = 'FrappeError'

        if ( typeof Error.captureStackTrace === 'function' )
            Error.captureStackTrace(this, this.constructor)
        else
            this.stack = (new Error(message)).stack
    }
}

/**
 * @description TypeError
 */
frappe.TypeError  = class extends frappe.Error
{
    constructor (message)
    {
        super (message)

        this.name = this.constructor.name
    }
}

/**
 * @description ValueError
 */
frappe.ValueError = class extends frappe.Error
{
    constructor (message)
    {
        super (message)

        this.name = this.constructor.name
    }
}

/**
 * @description ImportError
 */
frappe.ImportError = class extends frappe.Error
{
    constructor (message)
    {
        super (message)

        this.name  = this.constructor.name
    }
}

// frappe.datetime
frappe.provide('frappe.datetime')

/**
 * @description Frappe's datetime object. (Inspired by Python's datetime object).
 * 
 * @example
 * const datetime = new frappe.datetime.datetime()
 */
frappe.datetime.datetime = class
{
    /**
     * @description Frappe's datetime Class's constructor.
     */
    constructor (instance)
    {
        if ( typeof moment === undefined )
            throw new frappe.ImportError(`Moment.js not installed.`)

        this.moment      = instance ? moment(instance) : moment()
    }

    /**
     * @description Returns a formatted string of the datetime object.
     */
    format (format)
    {
        const  formatted = this.moment.format(format)
        return formatted
    }
}

/**
 * @description Returns the current datetime.
 * 
 * @example
 * const datetime = new frappe.datetime.now()
 */
frappe.datetime.now = () => new frappe.datetime.datetime()

/**
 * @description Compares two frappe.datetime.datetime objects.
 * 
 * @param   {frappe.datetime.datetime} a - A frappe.datetime.datetime/moment object.
 * @param   {frappe.datetime.datetime} b - A frappe.datetime.datetime/moment object.
 * 
 * @returns {number} 0 (if a and b are equal), 1 (if a is before b), -1 (if a is after b).
 * 
 * @example
 * frappe.datetime.compare(frappe.datetime.now(), frappe.datetime.now())
 * // returns 0
 * const then = frappe.datetime.now()
 * 
 * frappe.datetime.compare(then, frappe.datetime.now())
 * // returns 1
 */
frappe.datetime.compare = (a, b) =>
{
    a = a.moment
    b = b.moment

    if ( a.isBefore(b) )
        return  1
    else
    if ( b.isBefore(a) )
        return -1
    else
        return  0
}

// frappe._
// frappe's utility namespace.
frappe.provide('frappe._')

frappe._.head = arr => frappe._.is_empty(arr) ? undefined : arr[0]

/**
 * @description Python-inspired format extension for string objects.
 * 
 * @param  {string} string - A string with placeholders.
 * @param  {object} object - An object with placeholder, value pairs.
 * 
 * @return {string}        - The formatted string.
 * 
 * @example
 * frappe._.format('{foo} {bar}', { bar: 'foo', foo: 'bar' })
 * // returns "bar foo"
 */
frappe._.format = (string, object) =>
{
    for (const key in object)
        string  = string.replace(`{${key}}`, object[key])

    return string
}

/**
 * @description Fuzzy Search a given query within a dataset.
 * 
 * @param  {string} query   - A query string.
 * @param  {array}  dataset - A dataset to search within, can contain singletons or objects.
 * @param  {object} options - Options as per fuze.js
 * 
 * @return {array}          - The fuzzy matched index/object within the dataset.
 * 
 * @example
 * frappe._.fuzzy_search("foobar", ["foobar", "bartender"])
 * // returns [0, 1]
 * 
 * @see http://fusejs.io
 */
frappe._.fuzzy_search = (query, dataset, options) =>
{
    const DEFAULT  =
    {
                shouldSort: true,
                 threshold: 0.6,
                  location: 0,
                  distance: 100,
        minMatchCharLength: 1,
          maxPatternLength: 32
    }
    options       = { ...DEFAULT, ...options }

    const fuse    = new Fuse(dataset, options)
    const result  = fuse.search(query)

    return result
}

/**
 * @description Pluralizes a given word.
 * 
 * @param  {string} word  - The word to be pluralized.
 * @param  {number} count - The count.
 * 
 * @return {string}       - The pluralized string.
 * 
 * @example
 * frappe._.pluralize('member',  1)
 * // returns "member"
 * frappe._.pluralize('members', 0)
 * // returns "members"
 * 
 * @todo Handle more edge cases.
 */
frappe._.pluralize = (word, count = 0, suffix = 's') => `${word}${count === 1 ? '' : suffix}`

/**
 * @description Captializes a given string.
 * 
 * @param   {word}  - The word to be capitalized.
 * 
 * @return {string} - The capitalized word.
 * 
 * @example
 * frappe._.capitalize('foobar')
 * // returns "Foobar"
 */
frappe._.capitalize = word => `${word.charAt(0).toUpperCase()}${word.slice(1)}`

/**
 * @description Returns a copy of the given array (shallow).
 * 
 * @param   {array} array - The array to be copied.
 * 
 * @returns {array}       - The copied array.
 * 
 * @example
 * frappe._.copy_array(["foobar", "barfoo"])
 * // returns ["foobar", "barfoo"]
 * 
 * @todo Add optional deep copy.
 */
frappe._.copy_array = array =>
{
    if ( Array.isArray(array) )
        return array.slice()
    else
        throw frappe.TypeError(`Expected Array, recieved ${typeof array} instead.`)
}

/**
 * @description Check whether an array|string|object is empty.
 * 
 * @param   {any}     value - The value to be checked on.
 * 
 * @returns {boolean}       - Returns if the object is empty. 
 * 
 * @example
 * frappe._.is_empty([])      // returns true
 * frappe._.is_empty(["foo"]) // returns false
 * 
 * frappe._.is_empty("")      // returns true
 * frappe._.is_empty("foo")   // returns false
 * 
 * frappe._.is_empty({ })            // returns true
 * frappe._.is_empty({ foo: "bar" }) // returns false
 * 
 * @todo Handle other cases.
 */
frappe._.is_empty = value =>
{
    let empty = false

    if ( value === undefined || value === null )
        empty = true
    else
    if ( Array.isArray(value) || typeof value === 'string' )
        empty = value.length === 0
    else
    if ( typeof value === 'object' )
        empty = Object.keys(value).length === 0

    return empty
}

/**
 * @description Converts a singleton to an array, if required.
 * 
 * @param {object} item - An object
 * 
 * @example
 * frappe._.as_array("foo")
 * // returns ["foo"]
 * 
 * frappe._.as_array(["foo"])
 * // returns ["foo"]
 * 
 * @see https://docs.oracle.com/javase/8/docs/api/java/util/Arrays.html#asList-T...-
 */
frappe._.as_array = item => Array.isArray(item) ? item : [item]

/**
 * @description Return a singleton if array contains a single element.
 * 
 * @param   {array}        list - An array to squash.
 * 
 * @returns {array|object}      - Returns an array if there's more than 1 object else the first object itself.
 * 
 * @example
 * frappe._.squash(["foo"])
 * // returns "foo"
 * 
 * frappe._.squash(["foo", "bar"])
 * // returns ["foo", "bar"]
 */
frappe._.squash = list => Array.isArray(list) && list.length === 1 ? list[0] : list

/**
 * @description Returns true, if the current device is a mobile device.
 * 
 * @example
 * frappe._.is_mobile()
 * // returns true|false
 * 
 * @see https://developer.mozilla.org/en-US/docs/Web/HTTP/Browser_detection_using_the_user_agent
 */
frappe._.is_mobile = () =>
{
    const regex    = new RegExp("Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini", "i")
    const agent    = navigator.userAgent
    const mobile   = regex.test(agent)

    return mobile
}

/**
 * @description Removes falsey values from an array.
 * 
 * @example
 * frappe._.compact([1, 2, false, NaN, ''])
 * // returns [1, 2]
 */
frappe._.compact   = array => array.filter(Boolean)

// frappe extensions

// frappe.user extensions
/**
 * @description Returns the first name of a User.
 * 
 * @param {string} user - User
 * 
 * @returns The first name of the user.
 * 
 * @example
 * frappe.user.first_name("Rahul Malhotra")
 * // returns "Rahul"
 */
frappe.provide('frappe.user')
frappe.user.first_name = user => frappe._.head(frappe.user.full_name(user).split(" "))

// frappe.ui extensions
frappe.provide('frappe.ui')
frappe.ui.Uploader = class
{
    constructor (wrapper, options = { })
    {
        this.options = frappe.ui.Uploader.OPTIONS
        this.set_wrapper(wrapper)
        this.set_options(options)
    }

    set_wrapper (wrapper)
    {
        this.$wrapper = $(wrapper)

        return this
    }

    set_options (options)
    {
        this.options  = { ...this.options, ...options }

        return this
    }

    render ( )
    {
        const $template = $(frappe.ui.Uploader.TEMPLATE)
        this.$wrapper.html($template)
    }
}
frappe.ui.Uploader.Layout   = { DIALOG: 'DIALOG' }
frappe.ui.Uploader.OPTIONS  =
{
    layout: frappe.ui.Uploader.Layout.DIALOG
}
frappe.ui.Uploader.TEMPLATE =
`
<div class="foobar">
    FooBar
</div>
`

frappe.provide('frappe.ui.keycode')
frappe.ui.keycode = { RETURN: 13 }

// frappe.loggers - A registry for frappe loggers.
frappe.provide('frappe.loggers')
/**
 * @description Frappe's Logger Class
 * 
 * @example
 * frappe.log       = frappe.Logger.get('foobar')
 * frappe.log.level = frappe.Logger.DEBUG
 * 
 * frappe.log.info('foobar')
 * // prints '[timestamp] foobar: foobar'
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
            throw new frappe.TypeError(`Expected string for name, got ${typeof name} instead.`)

        this.name   = name
        if ( frappe.boot.developer_mode )
            this.level  = frappe.Logger.ERROR
        else
            this.level  = frappe.Logger.NOTSET
        this.format = frappe.Logger.FORMAT
    }

    /**
     * @description Get instance of frappe.Logger (return registered one if declared).
     * 
     * @param {string} name - Name of the logger.
     */
    static get (name)
    {
        if ( !(name in frappe.loggers) )
            frappe.loggers[name] = new frappe.Logger(name)
        return frappe.loggers[name]
    }

    debug (message) { this.log(message, frappe.Logger.DEBUG) }
    info  (message) { this.log(message, frappe.Logger.INFO)  }
    warn  (message) { this.log(message, frappe.Logger.WARN)  }
    error (message) { this.log(message, frappe.Logger.ERROR) }

    log (message, level)
    {
        const timestamp   = frappe.datetime.now()

        if ( level.value <= this.level.value )
        {
            const format  = frappe._.format(this.format,
            {
                time: timestamp.format('HH:mm:ss'),
                name: this.name
            })
            console.log(`%c ${format}:`, `color: ${level.color}`, message)
        }
    }
}

frappe.Logger.DEBUG  = { value: 10, color: '#616161', name: 'DEBUG'  }
frappe.Logger.INFO   = { value: 20, color: '#2196F3', name: 'INFO'   }
frappe.Logger.WARN   = { value: 30, color: '#FFC107', name: 'WARN'   }
frappe.Logger.ERROR  = { value: 40, color: '#F44336', name: 'ERROR'  }
frappe.Logger.NOTSET = { value:  0,                   name: 'NOTSET' }

frappe.Logger.FORMAT = '{time} {name}'

// frappe.chat
frappe.provide('frappe.chat')

frappe.log = frappe.Logger.get('frappe.chat')

// frappe.chat.profile
frappe.provide('frappe.chat.profile')

/**
 * @description Create a Chat Profile.
 * 
 * @param   {string|array} fields - (Optional) fields to be retrieved after creating a Chat Profile.
 * @param   {function}     fn     - (Optional) callback with the returned Chat Profile.
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.profile.create(console.log)
 * 
 * frappe.chat.profile.create("status").then(console.log) // { status: "Online" }
 */
frappe.chat.profile.create = (fields, fn) =>
{
    if ( typeof fields === "function" )
    {
        fn     = fields
        fields = null
    } else
    if ( typeof fields === "string" )
        fields = frappe._.as_array(fields)

    return new Promise(resolve =>
    {
        frappe.call("frappe.chat.doctype.chat_profile.chat_profile.create",
            { user: frappe.session.user, exists_ok: true, fields: fields },
                response =>
                {
                    if ( fn )
                        fn(response.message)
                    
                    resolve(response.message)
                })
    })
}

/**
 * @description Create a Chat Profile.
 * 
 * @param   {string|array} fields - (Optional) fields to be retrieved after creating a Chat Profile.
 * @param   {function}     fn     - (Optional) callback with the returned Chat Profile.
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.profile.create(console.log)
 * 
 * frappe.chat.profile.create("status").then(console.log) // { status: "Online" }
 */
frappe.chat.profile.update = (user, update, fn) =>
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
                })
    })
}

// frappe.chat.profile.on
frappe.provide('frappe.chat.profile.on')

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
 * })
 */
frappe.chat.profile.on.update = function (fn)
{
    frappe.realtime.on("frappe.chat.profile:update", r => fn(r.user, r.data))
}
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
]

// frappe.chat.room
frappe.provide('frappe.chat.room')

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
 * })
 * frappe.chat.room.create("Group",  frappe.session.user, ["santa@gmail.com", "banta@gmail.com"], "Santa and Banta", function (room) {
 *      // do stuff
 * })
 */
frappe.chat.room.create = function (kind, owner, users, name, fn)
{
    if ( typeof name === "function" )
    {
        fn   = name
        name = null
    }

    users    = frappe._.as_array(users)
    
    return new Promise(resolve =>
    {
        frappe.call("frappe.chat.doctype.chat_room.chat_room.create",
            { kind: kind, owner: owner || frappe.session.user, users: users, name: name },
            r =>
            {
                let room = r.message
                room     = { ...room, creation: new frappe.datetime.datetime(room.creation) }

                if ( fn )
                    fn(room)

                resolve(room)
            })
    })
}

/**
 * @description Returns Chat Room(s).
 * 
 * @param   {string|array} names   - (Optional) Chat Room(s) to retrieve.
 * @param   {string|array} fields  - (Optional) fields to be retrieved for each Chat Room.
 * @param   {function}     fn      - (Optional) callback with the returned Chat Room(s).
 * 
 * @returns {Promise}
 * 
 * @example
 * frappe.chat.room.get(function (rooms) {
 *      // do stuff
 * })
 * frappe.chat.room.get().then(function (rooms) {
 *      // do stuff
 * })
 * 
 * frappe.chat.room.get(null, ["room_name", "avatar"], function (rooms) {
 *      // do stuff
 * })
 * 
 * frappe.chat.room.get("CR00001", "room_name", function (room) {
 *      // do stuff
 * })
 * 
 * frappe.chat.room.get(["CR00001", "CR00002"], ["room_name", "last_message"], function (rooms) {
 * 
 * })
 */
frappe.chat.room.get = function (names, fields, fn)
{
    if ( typeof names === "function" )
    {
        fn     = names
        names  = null
        fields = null
    }
    else
    if ( typeof names === "string" )
    {
        names  = frappe._.as_array(names)

        if ( typeof fields === "function" ) {
            fn     = fields
            fields = null
        }
        else
        if ( typeof fields === "string" )
            fields = frappe._.as_array(fields)
    }

    return new Promise(resolve =>
    {

        frappe.call("frappe.chat.doctype.chat_room.chat_room.get",
            { user: frappe.session.user, rooms: names, fields: fields },
                response =>
                {
                    let rooms = response.message
                    if ( rooms ) // frappe.api BOGZ! (emtpy arrays are falsified, not good design).
                    {
                        rooms = frappe._.as_array(rooms)
                        rooms = rooms.map(room =>
                        {
                            return { ...room, creation: new frappe.datetime.datetime(room.creation),
                                last_message: room.last_message ? { ...room.last_message, creation: new frappe.datetime.datetime(room.last_message.creation) } : null
                            }
                        })
                        rooms = frappe._.squash(rooms)
                    }
                    else
                        rooms = [ ]

                    if ( fn )
                        fn(rooms)

                    resolve(rooms)
                })
    })
}

/**
 * @description Subscribe current user to said Chat Room(s).
 * 
 * @param {string|array} rooms - Chat Room(s).
 * 
 * @example
 * frappe.chat.room.subscribe("CR00001")
 */
frappe.chat.room.subscribe = function (rooms)
{
    frappe.realtime.publish("frappe.chat.room:subscribe", rooms)
}

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
 * })
 */
frappe.chat.room.history = function (name, fn)
{
    return new Promise(resolve =>
    {
        frappe.call("frappe.chat.doctype.chat_room.chat_room.history",
            { room: name },
                r =>
                {
                    let messages = r.message ? frappe._.as_array(r.message) : [ ] // frappe.api BOGZ! (emtpy arrays are falsified, not good design).
                    messages     = messages.map(m => { return { ...m, creation: new frappe.datetime.datetime(m.creation) } })

                    if ( fn )
                        fn(messages)
                    
                    resolve(messages)
                })
    })
}

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
            return r.room_name
        else
            if ( r.owner === frappe.session.user )
                return frappe.user.full_name(frappe._.squash(r.users))
            else
                return frappe.user.full_name(r.owner)
    })
    const results = frappe._.fuzzy_search(query, dataset)
    rooms         = results.map(i => rooms[i])

    return rooms
}

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
        if ( a.last_message && b.last_message )
            return frappe.datetime.compare(a.last_message.creation, b.last_message.creation)
        else
        if ( a.last_message )
            return frappe.datetime.compare(a.last_message.creation, b.creation)
        else
        if ( b.last_message )
            return frappe.datetime.compare(a.creation, b.last_message.creation)
        else
            return frappe.datetime.compare(a.creation, b.creation)
    }
    rooms.sort(compare)

    return rooms
}

// frappe.chat.room.on
frappe.provide('frappe.chat.room.on')

/**
 * @description Triggers on Chat Room updated.
 * 
 * @param {function} fn - callback with the Chat Room and Update.
 */
frappe.chat.room.on.update = function (fn)
{
    frappe.realtime.on("frappe.chat.room:update", r =>
    {
        if ( r.data.last_message )
            // creation to frappe.datetime.datetime (easier to manipulate).
            r.data = { ...r.data, last_message: { ...r.data.last_message, creation: new frappe.datetime.datetime(r.data.last_message.creation) } }
        
        fn(r.room, r.data)
    })
}

/**
 * @description Triggers on Chat Room created.
 * 
 * @param {function} fn - callback with the created Chat Room.
 */
frappe.chat.room.on.create = function (fn)
{
    frappe.realtime.on("frappe.chat.room:create", r => fn({ ...r, creation: new frappe.datetime.datetime(r.creation) }))
}

/**
 * @description Triggers when a User is typing in a Chat Room.
 * 
 * @param {function} fn - callback with the typing User within the Chat Room.
 */
frappe.chat.room.on.typing = function (fn)
{
    frappe.realtime.on("frappe.chat.room:typing", r => fn(r.room, r.user))
}

// frappe.chat.message
frappe.provide('frappe.chat.message')

frappe.chat.message.typing = function (room, user)
{
    frappe.realtime.publish("frappe.chat.message:typing", { user: user || frappe.session.user, room: room })
}

frappe.chat.message.send   = function (room, message)
{
    frappe.call("frappe.chat.doctype.chat_message.chat_message.send",
        { user: frappe.session.user, room: room, content: message })
}

frappe.chat.message.update = function (message, update, fn)
{
    return new Promise(resolve => {
        frappe.call('frappe.chat.doctype.chat_message.chat_message.update',
            { user: frappe.session.user, message: message, update: update },
            r => 
            {
                if ( fn )
                    fn(response.message)

                resolve(response.message)
            })
    })
}

frappe.chat.message.sort   = (messages) =>
{
    if ( !frappe._.is_empty(messages) )
        messages.sort((a, b) => frappe.datetime.compare(b.creation, a.creation));

    return messages
}

/**
 * @description Add user to seen (defaults to session.user)
 */
frappe.chat.message.seen   = (mess, user) =>
{
    frappe.call('frappe.chat.doctype.chat_message.chat_message.seen',
        { message: mess, user: user || frappe.session.user })
}

frappe.provide('frappe.chat.message.on')
frappe.chat.message.on.create = function (fn)
{
    frappe.realtime.on("frappe.chat.message:create", r => fn({ ...r, creation: new frappe.datetime.datetime(r.creation) }))
}


frappe.chat.message.on.update = function (fn)
{
    frappe.realtime.on("frappe.chat.message:update", r => fn(r.message, r.data))
}

frappe.chat.pretty_datetime   = function (date)
{
    const today    = moment()
    const instance = date.moment
        
    if ( today.isSame(instance, "d") )
        return instance.format("hh:mm A")
    else
    if ( today.isSame(instance, "week") )
        return instance.format("dddd")
    else
        return instance.format("DD/MM/YYYY")
}

// frappe.chat.sound
frappe.provide('frappe.chat.sound')

/**
 * @description Plays a given registered sound.
 * 
 * @param {value} - The name of the registered sound.
 * 
 * @example
 * frappe.chat.sound.play("message")
 */
frappe.chat.sound.play  = function (name, volume = 0.1)
{
    // frappe.utils.play_sound(`chat-${name}`)
    const $audio = $(`<audio class="chat-audio" volume="${volume}"/>`)
    if  ( $audio.length === 0 )
        $(document).append($audio)

    if  ( !$audio.paused )
    {
        frappe.log.info('Stopping sound playing.')
        $audio[0].pause()
        $audio.attr('currentTime', 0)
    }

    frappe.log.info('Playing sound.')
    $audio.attr('src', `${frappe.chat.sound.PATH}/chat-${name}.mp3`)
    $audio[0].play()
}
frappe.chat.sound.PATH  = '/assets/frappe/sounds'

// frappe.chat.emoji
frappe.chat.emojis = [ ]
frappe.chat.emoji  = function (fn)
{
    return new Promise(resolve => {
        if ( !frappe._.is_empty(frappe.chat.emojis) )
        {
            if ( fn )
                fn(frappe.chat.emojis)

            resolve(frappe.chat.emojis)
        }
        else
            $.get('https://cdn.rawgit.com/achillesrasquinha/emoji/master/emoji', (data) => {
                frappe.chat.emojis = JSON.parse(data)
                
                if ( fn )
                    fn(frappe.chat.emojis)

                resolve(frappe.chat.emojis)
            })
    })
}

const { h, Component } = hyper

// frappe.components
// frappe's component namespace.
frappe.provide('frappe.components')

/**
 * @description Button Component
 * 
 * @prop {string}  type  - (Optional) "default", "primary", "info", "success", "warning", "danger" (defaults to "default")
 * @prop {boolean} block - (Optional) Render a button block (defaults to false).
 */
frappe.components.Button
=
class extends Component
{
    render ( )
    {
        const { props } = this

        return (
            h("button", { ...props, class: `btn btn-${props.type} ${props.block ? "btn-block" : ""} ${props.class ? props.class : ""}` },
                props.children
            )
        )
    }
}
frappe.components.Button.defaultProps
=
{
     type: "default",
    block: false
}

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
        const { props } = this
        const size      = frappe.components.FAB.SIZE[props.size]
        
        return (
            h(frappe.components.Button, { ...props, class: `${props.class} ${size && size.class}`},
                h("i", { class: props.icon })
            )
        )
    }
}
frappe.components.FAB.defaultProps
=
{
    icon: "octicon octicon-plus"
}
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
}

/**
 * @description Octicon Component
 *
 * @prop color - (Required) color for the indicator
 */
frappe.components.Indicator
=
class extends Component
{
    render ( ) {
        const { props } = this

        return props.color ? h("span", { ...props, class: `indicator ${props.color}` }) : null
    }
}

/**
 * @description FontAwesome Component
 */
frappe.components.FontAwesome
=
class extends Component
{
    render ( )
    {
        const { props } = this

        return props.type ? h("i", { ...props, class: `fa ${props.fixed ? "fa-fw" : ""} fa-${props.type}` }) : null
    }
}
frappe.components.FontAwesome.defaultProps
=
{
    fixed: false
}

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
        const { props } = this

        return props.type ? h("i", { ...props, class: `octicon octicon-${props.type}` }) : null
    }
}

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
        const size      = frappe.components.Avatar.SIZE[props.size] || frappe.components.Avatar.SIZE.medium

        return (
            h("span", { class: `avatar ${size.class} ${props.class ? props.class : ""}` },
                props.image ?
                    h("img", { class: "media-object", src: props.image })
                    :
                    h("div", { class: "standard-image" }, abbr)
            )
        )
    }
}
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
    },
    medium:
    {
        class: "avatar-medium"
    }
}

/**
 * @description Frappe Chat Object.
 * 
 * @example
 * const chat = new frappe.Chat(options) // appends to "body"
 * chat.render()
 * const chat = new frappe.Chat(".selector", options)
 * chat.render()
 * 
 * const chat = new frappe.Chat()
 * chat.set_wrapper('.selector')
 *     .set_options(options)
 *     .render()
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
        if ( !(typeof selector === "string" || selector instanceof $ || selector instanceof HTMLElement) )
        {
            options  = selector
            selector = null
        }

        this.options = frappe.Chat.OPTIONS

        this.set_wrapper(selector ? selector : "body")
        this.set_options(options)

        // Load Emojis.
        frappe.chat.emoji()
    }

    /**
     * Set the container on which the chat widget is mounted on.
     * @param   {string|HTMLElement} selector - A query selector, HTML Element or jQuery object.
     * 
     * @returns {frappe.Chat}                 - The instance.
     * 
     * @example
     * const chat = new frappe.Chat()
     * chat.set_wrapper(".selector")
     */
    set_wrapper (selector)
    {
        this.$wrapper = $(selector)

        return this
    }

    /**
     * Set the configurations for the chat interface.
     * @param   {object}      options - Optional Configurations.
     * 
     * @returns {frappe.Chat}         - The instance.
     * 
     * @example
     * const chat = new frappe.Chat()
     * chat.set_options({ layout: frappe.Chat.Layout.PAGE })
     */
    set_options (options)
    {
        this.options = { ...this.options, ...options }

        return this
    }

    /**
     * @description Destory the chat widget.
     * 
     * @returns {frappe.Chat} - The instance.
     * 
     * @example
     * const chat = new frappe.Chat()
     * chat.render()
     *     .destroy()
     */
    destroy ( )
    {
        const $wrapper = this.$wrapper
        $wrapper.remove(".frappe-chat")

        return this
    }

    /**
     * @description Render the chat widget component onto destined wrapper.
     * 
     * @returns {frappe.Chat} - The instance.
     * 
     * @example
     * const chat = new frappe.Chat()
     * chat.render()
     */
    render ( )
    {
        this.destroy()

        const $wrapper = this.$wrapper
        const options  = this.options

        const component  = h(frappe.Chat.Widget,
        {
            layout: options.layout,
            target: options.target
        })

        hyper.render(component, $wrapper[0])

        return this
    }
}
frappe.Chat.Layout
=
{
    PAGE: "page", POPPER: "popper"
}
frappe.Chat.OPTIONS
=
{
    layout: frappe.Chat.Layout.POPPER
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
        super (props)

        this.room           = { }
        this.room.add       = (rooms) =>
        {   
            rooms           = frappe._.as_array(rooms)
            const names     = rooms.map(r => r.name)
            
            frappe.log.info(`Subscribing ${frappe.session.user} to Chat Rooms ${names.join(", ")}.`)
            frappe.chat.room.subscribe(names)
            
            const state     = [ ]

            for (const room of rooms)
                if ( room.type === "Group" || room.owner === frappe.session.user || room.last_message )
                {
                    frappe.log.info(`Adding ${room.name} to component.`)
                    state.push(room)
                }

            this.set_state({ rooms: [ ...this.state.rooms, ...state ] })
        }
        this.room.update    = (room, update) =>
        {
            const { state } = this
            var   exists    = false
            const rooms     = state.rooms.map(r =>
            {
                if ( r.name === room )
                {
                    exists  = true
                    if ( update.typing )
                    {
                        if ( !frappe._.is_empty(r.typing) )
                        {
                            const usr = update.typing
                            if ( !r.typing.includes(usr) )
                            {
                                update.typing = frappe._.copy_array(r.typing)
                                update.typing.push(usr)
                            }
                        }
                        else
                            update.typing = frappe._.as_array(update.typing)
                    }

                    return { ...r, ...update }
                }

                return r
            })

            if ( !exists )
                frappe.chat.room.get(room, (room) => this.room.add(room))
            else
                this.set_state({ rooms })

            if ( state.room.name === room )
            {
                if ( update.typing )
                {
                    if ( !frappe._.is_empty(state.room.typing) )
                    {
                        const usr = update.typing
                        if ( !state.room.typing.includes(usr) )
                        {
                            update.typing = frappe._.copy_array(state.room.typing)
                            update.typing.push(usr)
                        }
                    } else
                        update.typing = frappe._.as_array(update.typing)
                }

                const room  = { ...state.room, ...update }

                this.set_state({ room })
            }
        }
        this.room.select    = (name) =>
        {
            frappe.chat.room.history(name, (messages) =>
            {
                const  { state } = this
                const room       = state.rooms.find(r => r.name === name)
                
                this.set_state({
                    room: { ...state.room, ...room, messages: messages }
                })
            })
        }
        
        this.state = frappe.Chat.Widget.defaultState

        this.make()
    }

    make ( ) {
        frappe.chat.profile.create(["status", "display_widget", "notification_tones", "conversation_tones"]).then(profile =>
        {
            frappe.log.info(`Chat Profile created for User ${frappe.session.user} - ${JSON.stringify(profile)}.`)
            this.set_state({ profile })

            frappe.chat.room.get(rooms =>
            {
                rooms = frappe._.as_array(rooms)
                frappe.log.info(`User ${frappe.session.user} is subscribed to ${rooms.length} ${frappe._.pluralize('room', rooms.length)}.`)

                if ( rooms.length )
                    this.room.add(rooms)
            })

            this.bind()
        })
    }
    
    bind ( ) {
        frappe.chat.profile.on.update((user, update) =>
        {
            frappe.log.warn(`TRIGGER: Chat Profile update ${JSON.stringify(update)} of User ${user}.`)

            if ( 'status' in update )
            {
                if ( user === frappe.session.user )
                {
                    this.set_state({
                        profile: { ...this.state.profile, status: update.status }
                    })
                } else
                {
                    const status = frappe.chat.profile.STATUSES.find(s => s.name === update.status)
                    const color  = status.color
                    
                    const alert  = `<span class="indicator ${color}"/> ${frappe.user.full_name(user)} is currently <b>${update.status}</b>`
                    frappe.show_alert(alert, 3)
                }
            }

            if ( 'display_widget' in update )
            {
                this.set_state({
                    profile: { ...this.state.profile, display_widget: update.display_widget }
                })
            }
        })

        frappe.chat.room.on.create((room) =>
        {
            frappe.log.warn(`TRIGGER: Chat Room ${room.name} created.`)
            this.room.add(room)
        })

        frappe.chat.room.on.update((room, update) =>
        {
            frappe.log.warn(`TRIGGER: Chat Room ${room} update ${JSON.stringify(update)} recieved.`)
            this.room.update(room, update)
        })
        
        frappe.chat.room.on.typing((room, user) => {
            if ( user !== frappe.session.user )
            {
                frappe.log.warn(`User ${user} typing in Chat Room ${room}.`)
                this.room.update(room, { typing: user })
    
                setTimeout(() => this.room.update(room, { typing: null }), 1500)
            }
        })

        frappe.chat.message.on.create((r) => 
        {
            const { state } = this
            
            // play sound.
            if ( state.room.name )
                state.profile.conversation_tones && frappe.chat.sound.play('message')
            else
                state.profile.notification_tones && frappe.chat.sound.play('notification')
            
            if ( r.room === state.room.name )
            {
                const mess  = frappe._.copy_array(state.room.messages)
                mess.push(r)
                
                this.set_state({ room: { ...state.room, messages: mess } })
            }
        })

        frappe.chat.message.on.update((message, update) =>
        {
            frappe.log.warn(`TRIGGER: Chat Message ${message} update ${JSON.stringify(update)} recieved.`)
        })
    }

    render ( )
    {
        const { props, state } = this
        const me               = this
        
        const ActionBar        = h(frappe.Chat.Widget.ActionBar,
        {
             layout: props.layout,
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
                                        if ( user === frappe.session.user )
                                            frappe.throw(__('Sorry! You cannot chat with yourself.'))
                                        else
                                        {
                                            dialog.hide()
                                            
                                            // Don't Worry, frappe.chat.room.on.create gets triggered that then subscribes and adds to DOM. :)
                                            frappe.chat.room.create("Direct", null, user)
                                        }
                                    }
                                },
                                secondary:
                                {
                                    label: frappe._.is_mobile() ? "<b>&times</b>" : __(`Cancel`)
                                }
                             }
                        })
                        dialog.show()
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
                                        dialog.hide()
                                        
                                        // MultiSelect, y u no JSON? :(
                                        if ( users )
                                        {
                                            users = users.split(", ")
                                            users = users.slice(0, users.length - 1)
                                        }
                                        
                                        // Don't Worry, frappe.chat.room.on.create gets triggered that then subscribes and adds to DOM. :)
                                        frappe.chat.room.create("Group", null, users, name)
                                    }
                                },
                                secondary:
                                {
                                    label: frappe._.is_mobile() ? "<b>&times</b>" : __(`Cancel`)
                                }
                             }
                        })

                        dialog.show()
                    }
                }
            ],
            change: function (query)
            {
                me.set_state({
                    query: query
                })
            }
        })

        const rooms      = state.query ? frappe.chat.room.search(state.query, state.rooms) : frappe.chat.room.sort(state.rooms)
        
        const RoomList   = h(frappe.Chat.Widget.RoomList, { rooms: rooms, click: this.room.select })
        const Room       = h(frappe.Chat.Widget.Room, { ...state.room, layout: props.layout, destroy: () => {
            this.set_state({
                room: { name: null, messages: [ ] }
            })
        }})

        const component  = props.layout === frappe.Chat.Layout.POPPER ?
            state.profile.display_widget ?
                h(frappe.Chat.Widget.Popper, { page: state.room.name && Room, target: props.target },
                    h("span", null,
                        ActionBar, RoomList
                    )
                ) : null
            :
            h("div", { class: "row" },
                h("div", { class: "col-md-2  col-sm-3 layout-side-section" },
                    ActionBar, RoomList
                ),
                h("div", { class: "col-md-10 col-sm-9 layout-main-section-wrapper" },
                    state.room.name ?
                        Room : (
                            h("div", { style: "margin-top: 240px" },
                                h("div", { class: "text-center text-extra-muted" },
                                    h(frappe.components.Octicon, { type: "comment-discussion", style: "font-size: 48px" }),
                                    h("p", null, __("Select a chat to start messaging."))
                                )
                            )
                        )
                )
            )
        
        return component ?
            h("div", { class: "frappe-chat" },
                component
            ) : null
    }
}
frappe.Chat.Widget.defaultState = 
{
      query: "",
    profile: { },
      rooms: [ ],
       room: { name: null, messages: [ ], typing: [ ] }
}
frappe.Chat.Widget.defaultProps =
{
    layout: frappe.Chat.Layout.POPPER
}

/**
 * @description Chat Widget Popper HOC.
 */
frappe.Chat.Widget.Popper
=
class extends Component
{
    constructor (props) {
        super (props)

        this.toggle = this.toggle.bind(this)

        this.state  = frappe.Chat.Widget.Popper.defaultState

        if ( props.target )
            $(props.target).click(() => this.toggle())
    }

    toggle  (active)
    {

        let toggle
        if ( arguments.length === 1 )
            toggle = active
        else
            toggle = this.state.active ? false : true
        
        this.set_state({ active: toggle })
    }

    render  ( )
    {
        const { props, state } = this
        
        return !state.destroy ?
        (
            h("div", { class: "frappe-chat-popper" },
                !props.target ?
                    h(frappe.components.FAB, {
                          class: "frappe-fab",
                           icon: state.active ? "fa fa-fw fa-times" : "font-heavy octicon octicon-comment",
                           size: frappe._.is_mobile() ? null : "large",
                           type: "primary",
                        onclick: () => this.toggle(),
                    }) : null,
                state.active ?
                    h("div", { class: "frappe-chat-popper-collapse" },
                        props.page ? props.page : (
                            h("div", { class: `panel panel-default ${frappe._.is_mobile() ? "panel-span" : ""}` },
                                h("div", { class: "panel-heading cursor-pointer", onclick: () => this.toggle(false) },
                                    h("div", { class: "row" },
                                        h("div", { class: "col-xs-9" }),
                                        h("div", { class: "col-xs-3" },
                                            h("div", { class: "text-right" },
                                                // !frappe._.is_mobile() ?
                                                //     h("a", { class: "action", onclick: () =>
                                                //         {
                                                //          
                                                //         }},
                                                //         h(frappe.components.FontAwesome, { type: "expand", fixed: true })
                                                //     ) : null,
                                                h("a", { class: "action", onclick: () => this.toggle(false) },
                                                    h(frappe.components.Octicon, { type: "x" })
                                                )
                                            )
                                        )
                                    )
                                ),
                                h("div", { class: "panel-body" },
                                    props.children
                                )
                            )
                        )
                ) : null
            )
        ) : null
    }
}
frappe.Chat.Widget.Popper.defaultState
=
{
     active: false,
    destroy: false
}

/**
 * @description frappe.Chat.Widget ActionBar Component
 */
frappe.Chat.Widget.ActionBar
=
class extends Component
{
    constructor (props)
    {
        super (props)
        
        this.change = this.change.bind(this)
        this.submit = this.submit.bind(this)

        this.state  = frappe.Chat.Widget.ActionBar.defaultState
    }

    change (e)
    {
        const { props, state } = this

        this.set_state({
            [e.target.name]: e.target.value
        })

        props.change(state.query)
    }

    submit (e)
    {
        const { props, state } = this
        
        e.preventDefault()

        props.submit(state.query)
    }

    render ( )
    {
        const { props, state } = this
        const popper           =  props.layout === frappe.Chat.Layout.POPPER

        return (
            h("form", { oninput: this.change, onsubmit: this.submit, style: popper ? { "padding-left": "15px", "padding-right": "15px" } : null },
                h("div", { class: "form-group" },
                    h("div", { class: "input-group input-group-sm" },
                        props.span || props.layout !== frappe.Chat.Layout.PAGE ?
                            h("div", { class: "input-group-addon" },
                                h(frappe.components.Octicon, { type: "search" })
                            ) : null,
                        h("input", { class: "form-control", name: "query", value: state.query, placeholder: "Search" }),
                        Array.isArray(props.actions) ?
                            h("div", { class: "input-group-btn" },
                                h(frappe.components.Button, { type: "default", class: "dropdown-toggle", "data-toggle": "dropdown" },
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
        )
    }
}
frappe.Chat.Widget.ActionBar.defaultState
=
{
     span: false,
    query: null
}

/**
 * @description frappe.Chat.Widget ActionBar's Action Component.
 */
frappe.Chat.Widget.ActionBar.Action
=
class extends Component
{
    render ( )
    {
        const { props } = this

        return (
            h("span", null,
                props.icon ?
                    h("i", { class: props.icon })
                    :
                    null,
                `${props.icon ? " " : ""}${props.label}`
            )
        )
    }
}

/**
 * @description frappe.Chat.Widget RoomList Component
 */
frappe.Chat.Widget.RoomList
=
class extends Component
{
    render ( )
    {
        const { props } = this
        const rooms     = props.rooms

        return rooms.length ? (
            h("ul", { class: "nav nav-pills nav-stacked" },
                rooms.map(room => h(frappe.Chat.Widget.RoomList.Item, { ...room, click: props.click }))
            )
        ) : null
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
        const { props }    = this
        const item         = { }

        if ( props.type === "Group" ) {
            item.title     = props.room_name
            item.image     = props.avatar

            if ( !frappe._.is_empty(props.typing) )
            {
                props.typing  = frappe._.as_array(props.typing) // HACK: (BUG) why does typing return a string?
                const names   = props.typing.map(user => frappe.user.first_name(user))
                item.subtitle = `${names.join(", ")} typing...`
            } else
            if ( props.last_message )
                item.subtitle = props.last_message.content
        } else {
            const user     = props.owner === frappe.session.user ? frappe._.squash(props.users) : props.owner

            item.title     = frappe.user.full_name(user)
            item.image     = frappe.user.image(user)
            item.abbr      = frappe.user.abbr(user)

            if ( !frappe._.is_empty(props.typing) )
                item.subtitle = 'typing...'
            else
            if ( props.last_message )
                item.subtitle = props.last_message.content
        }

        if ( props.last_message )
            item.timestamp = frappe.chat.pretty_datetime(props.last_message.creation)

        return (
            h("li", null,
                h("a", { class: props.active ? "active": "", onclick: () => props.click(props.name) },
                    h("div", { class: "row" },
                        h("div", { class: "col-xs-9" },
                            h(frappe.Chat.Widget.MediaProfile, { ...item })
                        ),
                        h("div", { class: "col-xs-3 text-right" },
                            h("div", { class: "text-muted", style: { "font-size": "9px" } }, item.timestamp)
                        ),
                    )
                    
                )
            )
        )
    }
}

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
        const position  = frappe.Chat.Widget.MediaProfile.POSITION[props.position || "left"]
        const avatar    = (
            h("div", { class: `${position.class} media-top` },
                h(frappe.components.Avatar, { ...props,
                    title: props.title,
                    image: props.image,
                     size: props.size,
                     abbr: props.abbr
                })
            )
        )

        return (
            h("div", { class: "media", style: position.class === "media-right" ? { "text-align": "right" } : null },
                position.class === "media-left"  ? avatar : null,
                h("div", { class: "media-body" },
                    h("div", { class: "media-heading h6 ellipsis", style: `max-width: ${props.width_title || "100%"} display: inline-block` }, props.title),
                    props.content  ? h("div", null, h("small", { class: "h6" },         props.content))  : null,
                    props.subtitle ? h("div", null, h("small", { class: "text-muted" }, props.subtitle)) : null
                ),
                position.class === "media-right" ? avatar : null
            )
        )
    }
}
frappe.Chat.Widget.MediaProfile.POSITION
=
{
    left: { class: "media-left" }, right: { class: "media-right" }
}

/**
 * @description frappe.Chat.Widget Room Component
 */
frappe.Chat.Widget.Room
=
class extends Component
{
    render ( )
    {
        const { props, state } = this
        const hints            =
        [
            {
                 match: /@(\w*)$/,
                search: function (keyword, callback)
                {
                    if ( props.type === 'Group' )
                    {
                        const query = keyword.slice(1)
                        const users = [].concat(frappe._.as_array(props.owner), props.users)
                        const grep  = users.filter(user => user !== frappe.session.user && user.indexOf(query) === 0)

                        callback(grep)
                    }
                },
                component: function (item)
                {
                    return (
                        h(frappe.Chat.Widget.MediaProfile,
                        {
                            title: frappe.user.full_name(item),
                            image: frappe.user.image(item),
                             size: "small"
                        })
                    )
                }
            },
            {
                match: /:([a-z]*)$/,
               search: function (keyword, callback)
               {
                    frappe.chat.emoji(function (emojis)
                    {
                        const query = keyword.slice(1)
                        const items = [ ]
                        for (const emoji of emojis)
                            for (const alias of emoji.aliases)
                                if ( alias.indexOf(query) === 0 )
                                    items.push({ name: alias, value: emoji.emoji })

                        callback(items)
                    })
               },
                 content: (item) => item.value,
               component: function (item)
               {
                    return (
                        h(frappe.Chat.Widget.MediaProfile,
                        {
                            title: item.name,
                             abbr: item.value,
                             size: "small"
                        })
                    )
               }
           }
        ]

        const actions = frappe._.compact([
            !frappe._.is_mobile() &&
            {
                 icon: "camera",
                label: "Camera",
                click: ( ) => {
                    const capture = new frappe.ui.Capture({
                        animate: false,
                          error: true
                    })
                    capture.show()

                    capture.submit(data_url =>
                    {
                        // data_url
                    })
                }
            },
            {
                 icon: "file",
                label: "File",
                click: ( ) => {
                    
                }
            }
        ])

        if (props.messages)
        {
            props.messages = frappe._.as_array(props.messages)
            for (const message of props.messages)
                frappe.chat.message.seen(message.name)
        }

        return (
            h("div", { class: `panel panel-default ${frappe._.is_mobile() ? "panel-span" : ""}` },
                h(frappe.Chat.Widget.Room.Header, { ...props, back: props.destroy }),
                !frappe._.is_empty(props.messages) ?
                    h(frappe.Chat.Widget.ChatList, {
                        messages: !frappe._.is_empty(props.messages) && frappe.chat.message.sort(props.messages)
                    })
                    :
                    h("div", { class: "panel-body" },
                        h("div", { style: "margin-top: 145px" },
                            h("div", { class: "text-center text-extra-muted" },
                                h(frappe.components.Octicon, { type: "comment-discussion", style: "font-size: 48px" }),
                                h("p", null, __("Start a conversation."))
                            )
                        )
                    ),
                h("div", { class: "frappe-chat-room-footer" },
                    h(frappe.Chat.Widget.ChatForm, { actions: actions,
                        change: () => {
                            frappe.chat.message.typing(props.name)
                        },
                        submit: (message) => {
                            frappe.chat.message.send(props.name, message)
                        },
                          hint: hints
                    })
                )
            )
        )
    }
}

frappe.Chat.Widget.Room.Header
=
class extends Component
{
    render ( )
    {
        const { props }     = this

        const item          = { }
        
        if ( props.type === "Group" ) {
            item.route      = `Form/Chat Room/${props.name}`

            item.title      = props.room_name
            item.image      = props.avatar

            if ( !frappe._.is_empty(props.typing) )
            {
                props.typing  = frappe._.as_array(props.typing) // HACK: (BUG) why does typing return as a string?
                const users   = props.typing.map(user => frappe.user.first_name(user))
                item.subtitle = `${users.join(", ")} typing...`
            } else
                item.subtitle = __(`${props.users.length} ${frappe._.pluralize('member', props.users.length)}`)
        }
        else
        {
            const user      = props.owner === frappe.session.user ? frappe._.squash(props.users) : props.owner

            item.route      = `Form/User/${user}`

            item.title      = frappe.user.full_name(user)
            item.image      = frappe.user.image(user)

            if ( !frappe._.is_empty(props.typing) )
                item.subtitle = 'typing...'
        }

        const popper        = props.layout === frappe.Chat.Layout.POPPER || frappe._.is_mobile()
        
        return (
            h("div", { class: "panel-heading" },
                h("div", { class: "row" },
                    popper ?
                        h("div", { class: "col-xs-1" },
                            h("a", { onclick: props.back }, h(frappe.components.Octicon, { type: "chevron-left" }))
                        ) : null,
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
}

/**
 * @description Chat Form Component
 */
frappe.Chat.Widget.ChatForm
=
class extends Component {
    constructor (props) {
        super (props)
        
        this.change   = this.change.bind(this)
        this.submit   = this.submit.bind(this)

        this.hint     = this.hint.bind(this)

        this.state    = frappe.Chat.Widget.ChatForm.defaultState
    }

    change (e)
    {
        const { props, state } = this
        const value            = e.target.value

        this.set_state({
            [e.target.name]: value
        })

        props.change(state)

        this.hint(value)
    }

    hint (value)
    {
        const { props, state } = this

        if ( props.hint )
        {
            const tokens =  value.split(" ")
            const sliced = tokens.slice(0, tokens.length - 1)

            const token  = tokens[tokens.length - 1]

            if ( token )
            {
                props.hint   = frappe._.as_array(props.hint)
                const hint   = props.hint.find(hint => hint.match.test(token))
    
                if ( hint )
                {
                    hint.search(token, items =>
                    {
                        const hints = items.map(item =>
                        {
                            // You should stop writing one-liners! >_>
                            const replace = token.replace(hint.match, hint.content ? hint.content(item) : item)
                            const content = `${sliced.join(" ")} ${replace}`.trim()
                            item          = { component: hint.component(item), content: content }

                            return item
                        }).slice(0, hint.max || 5)
    
                        this.set_state({ hints })
                    })
                }
                else
                    this.set_state({ hints: [ ] })
            } else
                this.set_state({ hints: [ ] })
        }
    }

    submit (e)
    {
        e.preventDefault()

        if ( this.state.content )
        {
            this.props.submit(this.state.content)

            this.set_state({ content: null })
        }
    }

    render ( ) {
        const { props, state } = this

        return (
            h("div", { class: "frappe-chat-form" },
                state.hints.length ?
                    h("li", { class: "list-group" },
                        state.hints.map((item) =>
                        {
                            return (
                                h("a", { class: "list-group-item", href: "javascript:void(0)", onclick: () =>
                                {
                                    this.set_state({ content: item.content, hints: [ ] })
                                }},
                                    item.component
                                )
                            )
                        })
                    ) : null,
                h("form", { oninput: this.change, onsubmit: this.submit },
                    h("div", { class: "input-group input-group-lg" },
                        h("div", { class: "input-group-btn dropup" },
                            h(frappe.components.Button, { class: "dropdown-toggle", "data-toggle": "dropdown" },
                                h(frappe.components.FontAwesome, { type: "paperclip", fixed: true, style: { "font-size": "14px" } })
                            ),
                            h("div", { class: "dropdown-menu dropdown-menu-left", onclick: e => e.stopPropagation() },
                                !frappe._.is_empty(props.actions) && props.actions.map((action) => {
                                    return (
                                        h("li", null,
                                            h("a", { onclick: action.click },
                                                h(frappe.components.FontAwesome, { type: action.icon, fixed: true }), ` ${action.label}`,
                                            )
                                        )
                                    )
                                })
                            )
                        ),
                        h("input",
                        {
                                    class: "form-control",
                                     name: "content",
                                    value: state.content,
                              placeholder: "Type a message",
                                autofocus: true,
                               onkeypress: (e) =>
                               {
                                    if ( e.which === frappe.ui.keycode.RETURN && !e.shiftKey )
                                        this.submit(e)
                               }
                        }),
                        h("div", { class: "input-group-btn" },
                            h(frappe.components.Button, { type: "primary", class: "dropdown-toggle", "data-toggle": "dropdown", onclick: this.submit },
                                h(frappe.components.FontAwesome, { type: "send", fixed: true, style: { "font-size": "14px" } })
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
      hints: [ ],
}

frappe.Chat.Widget.EmojiPicker
=
class extends Component 
{
    render ( )
    {
        const { props } = this

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
        )
    }
}
frappe.Chat.Widget.EmojiPicker.List
=
class extends Component
{
    render ( )
    {
        const { props } = this

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









































// return (
//     h("a", { class: "list-group-item", href: "#", onclick: () => {
//         this.set_state({
//             content: `${this.state.content}${item.value}`
//         })
//     }},
//         props.hint.component(item)
//     )
// )


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
        
        return !frappe._.is_empty(props.messages) ? (
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
            h("li", { class: "list-group-item", style: "border: none !important" },
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

        return (
            h(frappe.Chat.Widget.MediaProfile, {
                      title: frappe.user.full_name(props.user),
                   subtitle: frappe.chat.pretty_datetime(props.creation),
                    content: props.content,
                      image: frappe.user.image(props.user),
                width_title: "100%",
                   position: frappe.user.full_name(props.user) === "You" ? "right" : "left"
            })
        )
    }
}
frappe.Chat.Widget.ChatList.Bubble.defaultState =
{
    creation: ""
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

