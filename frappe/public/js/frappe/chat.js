// Frappe Chat
// Author - Achilles Rasquinha <achilles@frappe.io>

import Fuse   from 'fuse.js'
import hyper  from '../lib/hyper.min'

import './socketio_client'

import './ui/dialog'
import './ui/capture'

import './misc/user'

/* eslint semi: "never" */
// Fuck semicolons - https://mislav.net/2010/05/semicolons

// frappe extensions

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
frappe.Error = Error
// class extends Error {
// 	constructor (message) {
// 		super (message)

// 		this.name = 'FrappeError'

// 		if ( typeof Error.captureStackTrace === 'function' )
// 			Error.captureStackTrace(this, this.constructor)
// 		else
// 			this.stack = (new Error(message)).stack
// 	}
// }

/**
 * @description TypeError
 */
frappe.TypeError  = TypeError
// class extends frappe.Error {
// 	constructor (message) {
// 		super (message)

// 		this.name = this.constructor.name
// 	}
// }

/**
 * @description ValueError
 */
frappe.ValueError = Error
// class extends frappe.Error {
// 	constructor (message) {
// 		super (message)

// 		this.name = this.constructor.name
// 	}
// }

/**
 * @description ImportError
 */
frappe.ImportError = Error
// class extends frappe.Error {
// 	constructor (message) {
// 		super (message)

// 		this.name  = this.constructor.name
// 	}
// }

// frappe.datetime
frappe.provide('frappe.datetime')

/**
 * @description Frappe's datetime object. (Inspired by Python's datetime object).
 *
 * @example
 * const datetime = new frappe.datetime.datetime()
 */
frappe.datetime.datetime = class {
	/**
	 * @description Frappe's datetime Class's constructor.
	 */
	constructor (instance, format = null) {
		if ( typeof moment === 'undefined' )
			throw new frappe.ImportError(`Moment.js not installed.`)

		this.moment = instance ? moment(instance, format) : moment()
	}

	/**
	 * @description Returns a formatted string of the datetime object.
	 */
	format (format = null) {
		const  formatted = this.moment.format(format)
		return formatted
	}
}

/**
 * @description Frappe's daterange object.
 *
 * @example
 * const range = new frappe.datetime.range(frappe.datetime.now(), frappe.datetime.now())
 * range.contains(frappe.datetime.now())
 */
frappe.datetime.range   = class {
	constructor (start, end) {
		if ( typeof moment === undefined )
			throw new frappe.ImportError(`Moment.js not installed.`)

		this.start = start
		this.end   = end
	}

	contains (datetime) {
		const  contains = datetime.moment.isBetween(this.start.moment, this.end.moment)
		return contains
	}
}

/**
 * @description Returns the current datetime.
 *
 * @example
 * const datetime = new frappe.datetime.now()
 */
frappe.datetime.now   = () => new frappe.datetime.datetime()

frappe.datetime.equal = (a, b, type) => {
	a = a.moment
	b = b.moment

	const equal = a.isSame(b, type)

	return equal
}

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
frappe.datetime.compare = (a, b) => {
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

// frappe.quick_edit
frappe.quick_edit      = (doctype, docname, fn) => {
	return new Promise(resolve => {
		frappe.model.with_doctype(doctype, () => {
			frappe.db.get_doc(doctype, docname).then(doc  => {
				const meta     = frappe.get_meta(doctype)
				const fields   = meta.fields
				const required = fields.filter(f => f.reqd || f.bold && !f.read_only)

				required.map(f => {
					if(f.fieldname == 'content' && doc.type == 'File') {
						f['read_only'] = 1;
					}
				})

				const dialog   = new frappe.ui.Dialog({
					 title: __(`Edit ${doctype} (${docname})`),
					fields: required,
					action: {
						primary: {
							   label: __("Save"),
							onsubmit: (values) => {
								frappe.call('frappe.client.save',
									{ doc: { doctype: doctype, docname: docname, ...doc, ...values } })
									  .then(r => {
										if ( fn )
											fn(r.message)

										resolve(r.message)
									  })

								dialog.hide()
							}
						},
						secondary: {
							label: __("Discard")
						}
					}
				})
				dialog.set_values(doc)

				const $element = $(dialog.body)
				$element.append(`
					<div class="qe-fp" style="padding-top: '15px'; padding-bottom: '15px'; padding-left: '7px'">
						<button class="btn btn-default btn-sm">
							${__("Edit in Full Page")}
						</button>
					</div>
				`)
				$element.find('.qe-fp').click(() => {
					dialog.hide()
					frappe.set_route(`Form/${doctype}/${docname}`)
				})

				dialog.show()
			})
		})
	})
}

// frappe._
// frappe's utility namespace.
frappe.provide('frappe._')

// String Utilities

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
frappe._.format = (string, object) => {
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
frappe._.fuzzy_search = (query, dataset, options) => {
	const DEFAULT     = {
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

// Array Utilities

/**
 * @description Returns the first element of an array.
 *
 * @param   {array} array - The array.
 *
 * @returns - The first element of an array, undefined elsewise.
 *
 * @example
 * frappe._.head([1, 2, 3])
 * // returns 1
 * frappe._.head([])
 * // returns undefined
 */
frappe._.head = arr => frappe._.is_empty(arr) ? undefined : arr[0]

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
frappe._.copy_array = array => {
	if ( Array.isArray(array) )
		return array.slice()
	else
		throw frappe.TypeError(`Expected Array, recieved ${typeof array} instead.`)
}

/**
 * @description Check whether an array|string|object|jQuery is empty.
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
 * frappe._.is_empty($('.papito'))   // returns false
 *
 * @todo Handle other cases.
 */
frappe._.is_empty = value => {
	let empty = false

	if ( value === undefined || value === null )
		empty = true
	else
	if ( Array.isArray(value) || typeof value === 'string' || value instanceof $ )
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
frappe._.is_mobile = () => {
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

// extend utils to base.
frappe.utils       = { ...frappe.utils, ...frappe._ }

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

frappe.provide('frappe.ui.keycode')
frappe.ui.keycode = { RETURN: 13 }

/**
 * @description Frappe's Store Class
 */
 // frappe.stores  - A registry for frappe stores.
frappe.provide('frappe.stores')
frappe.stores = [ ]
frappe.Store  = class
{
	/**
	 * @description Frappe's Store Class's constructor.
	 *
	 * @param {string} name - Name of the logger.
	 */
	constructor (name) {
		if ( typeof name !== 'string' )
			throw new frappe.TypeError(`Expected string for name, got ${typeof name} instead.`)
		this.name = name
	}

	/**
	 * @description Get instance of frappe.Store (return registered one if declared).
	 *
	 * @param {string} name - Name of the store.
	 */
	static get (name) {
		if ( !(name in frappe.stores) )
			frappe.stores[name] = new frappe.Store(name)
		return frappe.stores[name]
	}

	set (key, value) { localStorage.setItem(`${this.name}:${key}`, value) }
	get (key, value) { return localStorage.getItem(`${this.name}:${key}`) }
}

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
frappe.Logger = class {
	/**
	 * @description Frappe's Logger Class's constructor.
	 *
	 * @param {string} name - Name of the logger.
	 */
	constructor (name, level) {
		if ( typeof name !== 'string' )
			throw new frappe.TypeError(`Expected string for name, got ${typeof name} instead.`)

		this.name   = name
		this.level  = level

		if ( !this.level ) {
			if ( frappe.boot.developer_mode )
				this.level = frappe.Logger.ERROR
			else
				this.level = frappe.Logger.NOTSET
		}
		this.format = frappe.Logger.FORMAT
	}

	/**
	 * @description Get instance of frappe.Logger (return registered one if declared).
	 *
	 * @param {string} name - Name of the logger.
	 */
	static get (name, level) {
		if ( !(name in frappe.loggers) )
			frappe.loggers[name] = new frappe.Logger(name, level)
		return frappe.loggers[name]
	}

	debug (message) { this.log(message, frappe.Logger.DEBUG) }
	info  (message) { this.log(message, frappe.Logger.INFO)  }
	warn  (message) { this.log(message, frappe.Logger.WARN)  }
	error (message) { this.log(message, frappe.Logger.ERROR) }

	log (message, level) {
		const timestamp   = frappe.datetime.now()

		if ( level.value <= this.level.value ) {
			const format  = frappe._.format(this.format, {
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

frappe.log = frappe.Logger.get('frappe.chat', frappe.Logger.NOTSET)

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
frappe.chat.profile.create = (fields, fn) => {
	if ( typeof fields === "function" ) {
		fn     = fields
		fields = null
	} else
	if ( typeof fields === "string" )
		fields = frappe._.as_array(fields)

	return new Promise(resolve => {
		frappe.call("frappe.chat.doctype.chat_profile.chat_profile.create",
			{ user: frappe.session.user, exists_ok: true, fields: fields },
				response => {
					if ( fn )
						fn(response.message)

					resolve(response.message)
				})
	})
}

/**
 * @description Updates a Chat Profile.
 *
 * @param   {string} user   - (Optional) Chat Profile User, defaults to session user.
 * @param   {object} update - (Required) Updates to be dispatched.
 *
 * @example
 * frappe.chat.profile.update(frappe.session.user, { "status": "Offline" })
 */
frappe.chat.profile.update = (user, update, fn) => {
	return new Promise(resolve => {
		frappe.call("frappe.chat.doctype.chat_profile.chat_profile.update",
			{ user: user || frappe.session.user, data: update },
				response => {
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
frappe.chat.profile.on.update = function (fn) {
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
frappe.chat.room.create = function (kind, owner, users, name, fn) {
	if ( typeof name === "function" ) {
		fn   = name
		name = null
	}

	users    = frappe._.as_array(users)

	return new Promise(resolve => {
		frappe.call("frappe.chat.doctype.chat_room.chat_room.create",
			{ kind: kind, owner: owner || frappe.session.user, users: users, name: name },
			r => {
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
frappe.chat.room.get = function (names, fields, fn) {
	if ( typeof names === "function" ) {
		fn     = names
		names  = null
		fields = null
	}
	else
	if ( typeof names === "string" ) {
		names  = frappe._.as_array(names)

		if ( typeof fields === "function" ) {
			fn     = fields
			fields = null
		}
		else
		if ( typeof fields === "string" )
			fields = frappe._.as_array(fields)
	}

	return new Promise(resolve => {
		frappe.call("frappe.chat.doctype.chat_room.chat_room.get",
			{ user: frappe.session.user, rooms: names, fields: fields },
				response => {
					let rooms = response.message
					if ( rooms ) { // frappe.api BOGZ! (emtpy arrays are falsified, not good design).
						rooms = frappe._.as_array(rooms)
						rooms = rooms.map(room => {
							return { ...room, creation: new frappe.datetime.datetime(room.creation),
								last_message: room.last_message ? {
									...room.last_message,
									creation: new frappe.datetime.datetime(room.last_message.creation)
								} : null
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
frappe.chat.room.subscribe = function (rooms) {
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
frappe.chat.room.history = function (name, fn) {
	return new Promise(resolve => {
		frappe.call("frappe.chat.doctype.chat_room.chat_room.history",
			{ room: name, user: frappe.session.user },
				r => {
					let messages = r.message ? frappe._.as_array(r.message) : [ ] // frappe.api BOGZ! (emtpy arrays are falsified, not good design).
					messages     = messages.map(m => {
						return { ...m,
							creation: new frappe.datetime.datetime(m.creation)
						}
					})

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
frappe.chat.room.search = function (query, rooms) {
	const dataset = rooms.map(r => {
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
frappe.chat.room.sort = function (rooms, compare = null) {
	compare = compare || function (a, b) {
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
frappe.chat.room.on.update = function (fn) {
	frappe.realtime.on("frappe.chat.room:update", r => {
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
frappe.chat.room.on.create = function (fn) {
	frappe.realtime.on("frappe.chat.room:create", r =>
		fn({ ...r, creation: new frappe.datetime.datetime(r.creation) })
	)
}

/**
 * @description Triggers when a User is typing in a Chat Room.
 *
 * @param {function} fn - callback with the typing User within the Chat Room.
 */
frappe.chat.room.on.typing = function (fn) {
	frappe.realtime.on("frappe.chat.room:typing", r => fn(r.room, r.user))
}

// frappe.chat.message
frappe.provide('frappe.chat.message')

frappe.chat.message.typing = function (room, user) {
	frappe.realtime.publish("frappe.chat.message:typing", { user: user || frappe.session.user, room: room })
}

frappe.chat.message.send   = function (room, message, type = "Content") {
	frappe.call("frappe.chat.doctype.chat_message.chat_message.send",
		{ user: frappe.session.user, room: room, content: message, type: type })
}

frappe.chat.message.update = function (message, update, fn) {
	return new Promise(resolve => {
		frappe.call('frappe.chat.doctype.chat_message.chat_message.update',
			{ user: frappe.session.user, message: message, update: update },
			r =>  {
				if ( fn )
					fn(response.message)

				resolve(response.message)
			})
	})
}

frappe.chat.message.sort   = (messages) => {
	if ( !frappe._.is_empty(messages) )
		messages.sort((a, b) => frappe.datetime.compare(b.creation, a.creation))

	return messages
}

/**
 * @description Add user to seen (defaults to session.user)
 */
frappe.chat.message.seen   = (mess, user) => {
	frappe.call('frappe.chat.doctype.chat_message.chat_message.seen',
		{ message: mess, user: user || frappe.session.user })
}

frappe.provide('frappe.chat.message.on')
frappe.chat.message.on.create = function (fn) {
	frappe.realtime.on("frappe.chat.message:create", r =>
		fn({ ...r, creation: new frappe.datetime.datetime(r.creation) })
	)
}

frappe.chat.message.on.update = function (fn) {
	frappe.realtime.on("frappe.chat.message:update", r => fn(r.message, r.data))
}

frappe.chat.pretty_datetime   = function (date) {
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
frappe.chat.sound.play  = function (name, volume = 0.1) {
	// frappe._.play_sound(`chat-${name}`)
	const $audio = $(`<audio class="chat-audio"/>`)
	$audio.attr('volume', volume)

	if  ( frappe._.is_empty($audio) )
		$(document).append($audio)

	if  ( !$audio.paused ) {
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
frappe.chat.emoji  = function (fn) {
	return new Promise(resolve => {
		if ( !frappe._.is_empty(frappe.chat.emojis) ) {
			if ( fn )
				fn(frappe.chat.emojis)

			resolve(frappe.chat.emojis)
		}
		else
			$.get('https://cdn.rawgit.com/frappe/emoji/master/emoji', (data) => {
				frappe.chat.emojis = JSON.parse(data)

				if ( fn )
					fn(frappe.chat.emojis)

				resolve(frappe.chat.emojis)
			})
	})
}

// Website Settings
frappe.provide('frappe.chat.website.settings')
frappe.chat.website.settings = (fields, fn) =>
{
	if ( typeof fields === "function" ) {
		fn     = fields
		fields = null
	} else
	if ( typeof fields === "string" )
		fields = frappe._.as_array(fields)

	return new Promise(resolve => {
		frappe.call("frappe.chat.website.settings",
			{ fields: fields })
			.then(response => {
				var message = response.message

				if ( message.enable_from )
					message   = { ...message, enable_from: new frappe.datetime.datetime(message.enable_from, 'HH:mm:ss') }
				if ( message.enable_to )
					message   = { ...message, enable_to:   new frappe.datetime.datetime(message.enable_to,   'HH:mm:ss') }

				if ( fn )
					fn(message)

				resolve(message)
			})
	})
}

frappe.chat.website.token    = (fn) =>
{
	return new Promise(resolve => {
		frappe.call("frappe.chat.website.token")
			.then(response => {
				if ( fn )
					fn(response.message)

				resolve(response.message)
			})
	})
}

const { h, Component } = hyper

// frappe.components
// frappe's component namespace.
frappe.provide('frappe.components')

frappe.provide('frappe.chat.component')

/**
 * @description Button Component
 *
 * @prop {string}  type  - (Optional) "default", "primary", "info", "success", "warning", "danger" (defaults to "default")
 * @prop {boolean} block - (Optional) Render a button block (defaults to false).
 */
frappe.components.Button
=
class extends Component {
	render ( ) {
		const { props } = this
		const size      = frappe.components.Button.SIZE[props.size]

		return (
			h("button", { ...props, class: `btn ${size && size.class} btn-${props.type} ${props.block ? "btn-block" : ""} ${props.class ? props.class : ""}` },
				props.children
			)
		)
	}
}
frappe.components.Button.SIZE
=
{
	small: {
		class: "btn-sm"
	},
	large: {
		class: "btn-lg"
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
class extends frappe.components.Button {
	render ( ) {
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
class extends Component {
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
class extends Component {
	render ( ) {
		const { props } = this

		return props.type ? h("i", { ...props, class: `fa ${props.fixed ? "fa-fw" : ""} fa-${props.type} ${props.class}` }) : null
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
class extends Component {
	render ( ) {
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
class extends Component {
	render ( ) {
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
class {
	/**
	 * @description Frappe Chat Object.
	 *
	 * @param {string} selector - A query selector, HTML Element or jQuery object.
	 * @param {object} options  - Optional configurations.
	 */
	constructor (selector, options) {
		if ( !(typeof selector === "string" || selector instanceof $ || selector instanceof HTMLElement) ) {
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
	set_wrapper (selector) {
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
	set_options (options) {
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
	destroy ( ) {
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
	render (props = { }) {
		this.destroy()

		const $wrapper   = this.$wrapper
		const options    = this.options

		const component  = h(frappe.Chat.Widget, {
			layout: options.layout,
			target: options.target,
			...props
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
class extends Component {
	constructor (props) {
		super (props)

		this.setup(props)
		this.make()
	}

	setup (props) {
		// room actions
		this.room           = { }
		this.room.add       = rooms => {
			rooms           = frappe._.as_array(rooms)
			const names     = rooms.map(r => r.name)

			frappe.log.info(`Subscribing ${frappe.session.user} to Chat Rooms ${names.join(", ")}.`)
			frappe.chat.room.subscribe(names)

			const state     = [ ]

			for (const room of rooms)
				if ( ["Group", "Visitor"].includes(room.type) || room.owner === frappe.session.user || room.last_message ) {
					frappe.log.info(`Adding ${room.name} to component.`)
					state.push(room)
				}

			this.set_state({ rooms: [ ...this.state.rooms, ...state ] })
		}
		this.room.update    = (room, update) => {
			const { state } = this
			var   exists    = false
			const rooms     = state.rooms.map(r => {
				if ( r.name === room ) {
					exists  = true
					if ( update.typing ) {
						if ( !frappe._.is_empty(r.typing) ) {
							const usr = update.typing
							if ( !r.typing.includes(usr) ) {
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

			if ( frappe.session.user !== 'Guest' ) {
				if ( !exists )
					frappe.chat.room.get(room, (room) => this.room.add(room))
				else
					this.set_state({ rooms })
			}

			if ( state.room.name === room ) {
				if ( update.typing ) {
					if ( !frappe._.is_empty(state.room.typing) ) {
						const usr = update.typing
						if ( !state.room.typing.includes(usr) ) {
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
		this.room.select    = (name) => {
			frappe.chat.room.history(name, (messages) => {
				const  { state } = this
				const room       = state.rooms.find(r => r.name === name)

				this.set_state({
					room: { ...state.room, ...room, messages: messages }
				})
			})
		}

		this.state = { ...frappe.Chat.Widget.defaultState, ...props }
	}

	make ( ) {
		if ( frappe.session.user !== 'Guest' ) {
			frappe.chat.profile.create([
				"status", "message_preview", "notification_tones", "conversation_tones"
			]).then(profile => {
				this.set_state({ profile })

				frappe.chat.room.get(rooms => {
					rooms = frappe._.as_array(rooms)
					frappe.log.info(`User ${frappe.session.user} is subscribed to ${rooms.length} ${frappe._.pluralize('room', rooms.length)}.`)

					if ( !frappe._.is_empty(rooms) )
						this.room.add(rooms)
				})

				this.bind()
			})
		} else {
			this.bind()
		}
	}

	bind ( ) {
		frappe.chat.profile.on.update((user, update) => {
			frappe.log.warn(`TRIGGER: Chat Profile update ${JSON.stringify(update)} of User ${user}.`)

			if ( 'status' in update ) {
				if ( user === frappe.session.user ) {
					this.set_state({
						profile: { ...this.state.profile, status: update.status }
					})
				} else {
					const status = frappe.chat.profile.STATUSES.find(s => s.name === update.status)
					const color  = status.color

					const alert  = `<span class="indicator ${color}"/> ${frappe.user.full_name(user)} is currently <b>${update.status}</b>`
					frappe.show_alert(alert, 3)
				}
			}
		})

		frappe.chat.room.on.create((room) => {
			frappe.log.warn(`TRIGGER: Chat Room ${room.name} created.`)
			this.room.add(room)
		})

		frappe.chat.room.on.update((room, update) => {
			frappe.log.warn(`TRIGGER: Chat Room ${room} update ${JSON.stringify(update)} recieved.`)
			this.room.update(room, update)
		})

		frappe.chat.room.on.typing((room, user) => {
			if ( user !== frappe.session.user ) {
				frappe.log.warn(`User ${user} typing in Chat Room ${room}.`)
				this.room.update(room, { typing: user })

				setTimeout(() => this.room.update(room, { typing: null }), 5000)
			}
		})

		frappe.chat.message.on.create((r) => {
			const { state } = this

			// play sound.
			if ( state.room.name )
				state.profile.conversation_tones && frappe.chat.sound.play('message')
			else
				state.profile.notification_tones && frappe.chat.sound.play('notification')

			if ( r.user !== frappe.session.user && state.profile.message_preview && !state.toggle ) {
				const $element = $('body').find('.frappe-chat-alert')
				$element.remove()

				const  alert   = // TODO: ellipses content
				`
				<span data-action="show-message" class="cursor-pointer">
					<span class="indicator yellow"/> <b>${frappe.user.first_name(r.user)}</b>: ${r.content}
				</span>
				`
				frappe.show_alert(alert, 3, {
					"show-message": function (r) {
						this.room.select(r.room)
						this.base.firstChild._component.toggle()
					}.bind(this, r)
				})
			}

			if ( r.room === state.room.name ) {
				const mess  = frappe._.copy_array(state.room.messages)
				mess.push(r)

				this.set_state({ room: { ...state.room, messages: mess } })
			}
		})

		frappe.chat.message.on.update((message, update) => {
			frappe.log.warn(`TRIGGER: Chat Message ${message} update ${JSON.stringify(update)} recieved.`)
		})
	}

	render ( ) {
		const { props, state } = this
		const me               = this

		const ActionBar        = h(frappe.Chat.Widget.ActionBar, {
			placeholder: __("Search or Create a New Chat"),
				  class: "level",
				 layout: props.layout,
				actions:
			frappe._.compact([
				{
					  label: __("New"),
					onclick: function ( ) {
						const dialog = new frappe.ui.Dialog({
							  title: __("New Chat"),
							 fields: [
								 {
										 label: __("Chat Type"),
									 fieldname: "type",
									 fieldtype: "Select",
									   options: ["Group", "Direct Chat"],
									   default: "Group",
									  onchange: () =>  {
											const type     = dialog.get_value("type")
											const is_group = type === "Group"

											dialog.set_df_property("group_name", "reqd",  is_group)
											dialog.set_df_property("user",       "reqd", !is_group)
									  }
								 },
								 {
										 label: __("Group Name"),
									 fieldname: "group_name",
									 fieldtype: "Data",
										  reqd: true,
									depends_on: "eval:doc.type == 'Group'"
								 },
								 {
										 label: __("Users"),
									 fieldname: "users",
									 fieldtype: "MultiSelect",
									   options: frappe.user.get_emails(),
									depends_on: "eval:doc.type == 'Group'"
								 },
								 {
										 label: __("User"),
									 fieldname: "user",
									 fieldtype: "Link",
									   options: "User",
									depends_on: "eval:doc.type == 'Direct Chat'"
								 }
							 ],
							action: {
								primary: {
									   label: __('Create'),
									onsubmit: (values) => {
										if ( values.type === "Group" ) {
											if ( !frappe._.is_empty(values.users) ) {
												const name  = values.group_name
												const users = dialog.fields_dict.users.get_values()

												frappe.chat.room.create("Group",  null, users, name)
											}
										} else {
											const user      = values.user

											frappe.chat.room.create("Direct", null, user)
										}
										dialog.hide()
									}
								}
							}
						})
						dialog.show()
					}
				},
				frappe._.is_mobile() && {
					   icon: "octicon octicon-x",
					   class: "frappe-chat-close",
					onclick: () => this.set_state({ toggle: false })
				}
			], Boolean),
			change: query => { me.set_state({ query }) },
			  span: span  => { me.set_state({ span  }) },
		})

		var   contacts   = [ ]
		if ( 'user_info' in frappe.boot ) {
			const emails = frappe.user.get_emails()
			for (const email of emails) {
				var exists = false

				for (const room of state.rooms) {
					if ( room.type === 'Direct' ) {
						if ( room.owner === email || frappe._.squash(room.users) === email )
							exists = true
					}
				}

				if ( !exists )
					contacts.push({ owner: frappe.session.user, users: [email] })
			}
		}
		const rooms      = state.query ? frappe.chat.room.search(state.query, state.rooms.concat(contacts)) : frappe.chat.room.sort(state.rooms)

		const layout     = state.span  ? frappe.Chat.Layout.PAGE : frappe.Chat.Layout.POPPER

		const RoomList   = frappe._.is_empty(rooms) && !state.query ?
			h("div", { class: "vcenter" },
				h("div", { class: "text-center text-extra-muted" },
					h("p","",__("You don't have any messages yet."))
				)
			)
			:
			h(frappe.Chat.Widget.RoomList, { rooms: rooms, click: room =>  {
				if ( room.name )
					this.room.select(room.name)
				else
					frappe.chat.room.create("Direct", room.owner, frappe._.squash(room.users), ({ name }) => this.room.select(name))
			}})
		const Room       = h(frappe.Chat.Widget.Room, { ...state.room, layout: layout, destroy: () => {
			this.set_state({
				room: { name: null, messages: [ ] }
			})
		}})

		const component  = layout === frappe.Chat.Layout.POPPER ?
			h(frappe.Chat.Widget.Popper, { heading: ActionBar, page: state.room.name && Room, target: props.target,
				toggle: (t) => this.set_state({ toggle: t }) },
				RoomList
			)
			:
			h("div", { class: "frappe-chat-popper" },
				h("div", { class: "frappe-chat-popper-collapse" },
					h("div", { class: "panel panel-default panel-span", style: { width: "25%" } },
						h("div", { class: "panel-heading" },
							ActionBar
						),
						RoomList
					),
					Room
				)
			)

		return (
			h("div", { class: "frappe-chat" },
				component
			)
		)
	}
}
frappe.Chat.Widget.defaultState =  {
	  query: "",
	profile: { },
	  rooms: [ ],
	   room: { name: null, messages: [ ], typing: [ ] },
	 toggle: false,
	   span: false
}
frappe.Chat.Widget.defaultProps = {
	layout: frappe.Chat.Layout.POPPER
}

/**
 * @description Chat Widget Popper HOC.
 */
frappe.Chat.Widget.Popper
=
class extends Component {
	constructor (props) {
		super (props)

		this.setup(props);
	}

	setup (props) {
		this.toggle = this.toggle.bind(this)

		this.state  = frappe.Chat.Widget.Popper.defaultState

		if ( props.target )
			$(props.target).click(() => this.toggle())

		frappe.chat.widget = this
	}

	toggle  (active) {
		let toggle
		if ( arguments.length === 1 )
			toggle = active
		else
			toggle = this.state.active ? false : true

		this.set_state({ active: toggle })

		this.props.toggle(toggle)
	}

	on_mounted ( ) {
		$(document.body).on('click', '.page-container, .frappe-chat-close', ({ currentTarget }) => {
			this.toggle(false)
		})
	}

	render  ( )  {
		const { props, state } = this

		return !state.destroy ?
		(
			h("div", { class: "frappe-chat-popper", style: !props.target ? { "margin-bottom": "80px" } : null },
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
								h("div", { class: "panel-heading" },
									props.heading
								),
								props.children
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
class extends Component {
	constructor (props) {
		super (props)

		this.change = this.change.bind(this)
		this.submit = this.submit.bind(this)

		this.state  = frappe.Chat.Widget.ActionBar.defaultState
	}

	change (e) {
		const { props, state } = this

		this.set_state({
			[e.target.name]: e.target.value
		})

		props.change(state.query)
	}

	submit (e) {
		const { props, state } = this

		e.preventDefault()

		props.submit(state.query)
	}

	render ( ) {
		const me               = this
		const { props, state } = this
		const { actions }      = props

		return (
			h("div", { class: `frappe-chat-action-bar ${props.class ? props.class : ""}` },
				h("form", { oninput: this.change, onsubmit: this.submit },
					h("input", { autocomplete: "off", class: "form-control input-sm", name: "query", value: state.query, placeholder: props.placeholder || "Search" }),
				),
				!frappe._.is_empty(actions) ?
					actions.map(action => h(frappe.Chat.Widget.ActionBar.Action, { ...action })) : null,
				!frappe._.is_mobile() ?
					h(frappe.Chat.Widget.ActionBar.Action, {
						icon: `octicon octicon-screen-${state.span ? "normal" : "full"}`,
						onclick: () => {
							const span = !state.span
							me.set_state({ span })
							props.span(span)
						}
					})
					:
					null
			)
		)
	}
}
frappe.Chat.Widget.ActionBar.defaultState
=
{
	query: null,
	 span: false
}

/**
 * @description frappe.Chat.Widget ActionBar's Action Component.
 */
frappe.Chat.Widget.ActionBar.Action
=
class extends Component {
	render ( ) {
		const { props } = this

		return (
			h(frappe.components.Button, { size: "small", class: "btn-action", ...props },
				props.icon ? h("i", { class: props.icon }) : null,
				`${props.icon ? " " : ""}${props.label ? props.label : ""}`
			)
		)
	}
}

/**
 * @description frappe.Chat.Widget RoomList Component
 */
frappe.Chat.Widget.RoomList
=
class extends Component {
	render ( ) {
		const { props } = this
		const rooms     = props.rooms

		return !frappe._.is_empty(rooms) ? (
			h("ul", { class: "frappe-chat-room-list nav nav-pills nav-stacked" },
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
class extends Component {
	render ( ) {
		const { props }    = this
		const item         = { }

		if ( props.type === "Group" ) {
			item.title     = props.room_name
			item.image     = props.avatar

			if ( !frappe._.is_empty(props.typing) ) {
				props.typing  = frappe._.as_array(props.typing) // HACK: (BUG) why does typing return a string?
				const names   = props.typing.map(user => frappe.user.first_name(user))
				item.subtitle = `${names.join(", ")} typing...`
			} else
			if ( props.last_message ) {
				const message = props.last_message
				const content = message.content

				if ( message.type === "File" ) {
					item.subtitle = `📁 ${content.name}`
				} else {
					item.subtitle = props.last_message.content
				}
			}
		} else {
			const user     = props.owner === frappe.session.user ? frappe._.squash(props.users) : props.owner

			item.title     = frappe.user.full_name(user)
			item.image     = frappe.user.image(user)
			item.abbr      = frappe.user.abbr(user)

			if ( !frappe._.is_empty(props.typing) )
				item.subtitle = 'typing...'
			else
			if ( props.last_message ) {
				const message = props.last_message
				const content = message.content

				if ( message.type === "File" ) {
					item.subtitle = `📁 ${content.name}`
				} else {
					item.subtitle = props.last_message.content
				}
			}
		}

		let is_unread = false
		if ( props.last_message ) {
			item.timestamp = frappe.chat.pretty_datetime(props.last_message.creation)
			is_unread = !props.last_message.seen.includes(frappe.session.user)
		}

		return (
			h("li", null,
				h("a", { class: props.active ? "active": "", onclick: () => {
					if (props.last_message) {
						frappe.chat.message.seen(props.last_message.name);
					}
					props.click(props)
				} },
					h("div", { class: "row" },
						h("div", { class: "col-xs-9" },
							h(frappe.Chat.Widget.MediaProfile, { ...item })
						),
						h("div", { class: "col-xs-3 text-right" },
							[
								h("div", { class: "text-muted", style: { "font-size": "9px" } }, item.timestamp),
								is_unread ? h("span", { class: "indicator red" }) : null
							]
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
class extends Component {
	render ( ) {
		const { props } = this
		const position  = frappe.Chat.Widget.MediaProfile.POSITION[props.position || "left"]
		const avatar    = (
			h("div", { class: `${position.class} media-middle` },
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
					h("div", { class: "media-heading ellipsis small", style: `max-width: ${props.width_title || "100%"} display: inline-block` }, props.title),
					props.content  ? h("div","",h("small","",props.content))  : null,
					props.subtitle ? h("div",{ class: "media-subtitle small" },h("small", { class: "text-muted" }, props.subtitle)) : null
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
class extends Component {
	render ( ) {
		const { props, state } = this
		const hints            =
		[
			{
				 match: /@(\w*)$/,
				search: function (keyword, callback) {
					if ( props.type === 'Group' ) {
						const query = keyword.slice(1)
						const users = [].concat(frappe._.as_array(props.owner), props.users)
						const grep  = users.filter(user => user !== frappe.session.user && user.indexOf(query) === 0)

						callback(grep)
					}
				},
				component: function (item) {
					return (
						h(frappe.Chat.Widget.MediaProfile, {
							title: frappe.user.full_name(item),
							image: frappe.user.image(item),
							 size: "small"
						})
					)
				}
			},
			{
				match: /:([a-z]*)$/,
			   search: function (keyword, callback) {
					frappe.chat.emoji(function (emojis) {
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
			   component: function (item) {
					return (
						h(frappe.Chat.Widget.MediaProfile, {
							title: item.name,
							 abbr: item.value,
							 size: "small"
						})
					)
			   }
		   }
		]

		const actions = frappe._.compact([
			!frappe._.is_mobile() && {
				 icon: "camera",
				label: "Camera",
				onclick: ( ) => {
					const capture = new frappe.ui.Capture({
						animate: false,
						  error: true
					})
					capture.show()

					capture.submit(data_url => {
						// data_url
					})
				}
			},
			{
				 icon: "file",
				label: "File",
				onclick: ( ) => {
					const dialog = frappe.upload.make({
							args: { doctype: "Chat Room", docname: props.name },
						callback: (a, b, args) => {
							const { file_url, filename } = args
							frappe.chat.message.send(props.name, { path: file_url, name: filename }, "File")
						}
					})
				}
			}
		])

		if ( frappe.session.user !== 'Guest' ) {
			if (props.messages) {
				props.messages = frappe._.as_array(props.messages)
				for (const message of props.messages)
					if ( !message.seen.includes(frappe.session.user) )
						frappe.chat.message.seen(message.name)
					else
						break
			}
		}

		return (
			h("div", { class: `panel panel-default
				${props.name ? "panel-bg" : ""}
				${props.layout === frappe.Chat.Layout.PAGE || frappe._.is_mobile() ? "panel-span" : ""}`,
				style: props.layout === frappe.Chat.Layout.PAGE && { width: "75%", left: "25%", "box-shadow": "none" } },
				props.name && h(frappe.Chat.Widget.Room.Header, { ...props, on_back: props.destroy }),
				props.name ?
					!frappe._.is_empty(props.messages) ?
						h(frappe.chat.component.ChatList, {
							messages: props.messages
						})
						:
						h("div", { class: "panel-body", style: { "height": "100%" } },
							h("div", { class: "vcenter" },
								h("div", { class: "text-center text-extra-muted" },
									h(frappe.components.Octicon, { type: "comment-discussion", style: "font-size: 48px" }),
									h("p","",__("Start a conversation."))
								)
							)
						)
					:
					h("div", { class: "panel-body", style: { "height": "100%" } },
						h("div", { class: "vcenter" },
							h("div", { class: "text-center text-extra-muted" },
								h(frappe.components.Octicon, { type: "comment-discussion", style: "font-size: 125px" }),
								h("p","",__("Select a chat to start messaging."))
							)
						)
					),
				props.name ?
					h("div", { class: "chat-room-footer" },
						h(frappe.chat.component.ChatForm, { actions: actions,
							onchange: () => {
								frappe.chat.message.typing(props.name)
							},
							onsubmit: (message) => {
								frappe.chat.message.send(props.name, message)
							},
							hint: hints
						})
					)
					:
					null
			)
		)
	}
}

frappe.Chat.Widget.Room.Header
=
class extends Component {
	render ( ) {
		const { props }     = this

		const item          = { }

		if ( ["Group", "Visitor"].includes(props.type) ) {
			item.route      = `Form/Chat Room/${props.name}`

			item.title      = props.room_name
			item.image      = props.avatar

			if ( !frappe._.is_empty(props.typing) ) {
				props.typing  = frappe._.as_array(props.typing) // HACK: (BUG) why does typing return as a string?
				const users   = props.typing.map(user => frappe.user.first_name(user))
				item.subtitle = `${users.join(", ")} typing...`
			} else
				item.subtitle = props.type === "Group" ?
					__(`${props.users.length} ${frappe._.pluralize('member', props.users.length)}`)
					:
					""
		}
		else {
			const user      = props.owner === frappe.session.user ? frappe._.squash(props.users) : props.owner

			item.route      = `Form/User/${user}`

			item.title      = frappe.user.full_name(user)
			item.image      = frappe.user.image(user)

			if ( !frappe._.is_empty(props.typing) )
				item.subtitle = 'typing...'
		}

		const popper        = props.layout === frappe.Chat.Layout.POPPER || frappe._.is_mobile()

		return (
			h("div", { class: "panel-heading", style: { "height": "50px" } }, // sorry. :(
				h("div", { class: "level" },
					popper && frappe.session.user !== "Guest" ?
						h(frappe.components.Button,{class:"btn-back",onclick:props.on_back},
							h(frappe.components.Octicon, { type: "chevron-left" })
						) : null,
					h("div","",
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
 * @description ChatList Component
 *
 * @prop {array} messages - ChatMessage(s)
 */
frappe.chat.component.ChatList
=
class extends Component {
	on_mounted ( ) {
		this.$element  = $('.frappe-chat').find('.chat-list')
		this.$element.scrollTop(this.$element[0].scrollHeight)
	}

	on_updated ( ) {
		this.$element.scrollTop(this.$element[0].scrollHeight)
	}

	render ( ) {
		var messages = [ ]
		for (var i   = 0 ; i < this.props.messages.length ; ++i) {
			var   message   = this.props.messages[i]
			const me        = message.user === frappe.session.user

			if ( i === 0 || !frappe.datetime.equal(message.creation, this.props.messages[i - 1].creation, 'day') )
				messages.push({ type: "Notification", content: message.creation.format('MMMM DD') })

			messages.push(message)
		}

		return (
			h("div",{class:"chat-list list-group"},
				!frappe._.is_empty(messages) ?
					messages.map(m => h(frappe.chat.component.ChatList.Item, {...m})) : null
			)
		)
	}
}

/**
 * @description ChatList.Item Component
 *
 * @prop {string} name       - ChatMessage name
 * @prop {string} user       - ChatMessage user
 * @prop {string} room       - ChatMessage room
 * @prop {string} room_type  - ChatMessage room_type ("Direct", "Group" or "Visitor")
 * @prop {string} content    - ChatMessage content
 * @prop {frappe.datetime.datetime} creation - ChatMessage creation
 *
 * @prop {boolean} groupable - Whether the ChatMessage is groupable.
 */
frappe.chat.component.ChatList.Item
=
class extends Component {
	render ( ) {
		const { props } = this

		const me        = props.user === frappe.session.user
		const content   = props.content

		return (
			h("div",{class: "chat-list-item list-group-item"},
				props.type === "Notification" ?
					h("div",{class:"chat-list-notification"},
						h("div",{class:"chat-list-notification-content"},
							content
						)
					)
					:
					h("div",{class:`${me ? "text-right" : ""}`},
						props.room_type === "Group" && !me ?
							h(frappe.components.Avatar, {
								title: frappe.user.full_name(props.user),
								image: frappe.user.image(props.user)
							}) : null,
						h(frappe.chat.component.ChatBubble, props)
					)
			)
		)
	}
}

/**
 * @description ChatBubble Component
 *
 * @prop {string} name       - ChatMessage name
 * @prop {string} user       - ChatMessage user
 * @prop {string} room       - ChatMessage room
 * @prop {string} room_type  - ChatMessage room_type ("Direct", "Group" or "Visitor")
 * @prop {string} content    - ChatMessage content
 * @prop {frappe.datetime.datetime} creation - ChatMessage creation
 *
 * @prop {boolean} groupable - Whether the ChatMessage is groupable.
 */
frappe.chat.component.ChatBubble
=
class extends Component {
	constructor (props) {
		super (props)

		this.onclick = this.onclick.bind(this)
	}

	onclick ( ) {
		const { props } = this
		if ( props.user === frappe.session.user ) {
			frappe.quick_edit("Chat Message", props.name, (values) => {

			})
		}
	}

	render  ( ) {
		const { props } = this
		const creation 	= props.creation.format('hh:mm A')

		const me        = props.user === frappe.session.user
		const read      = !frappe._.is_empty(props.seen) && !props.seen.includes(frappe.session.user)

		const content   = props.content

		return (
			h("div",{class:`chat-bubble ${props.groupable ? "chat-groupable" : ""} chat-bubble-${me ? "r" : "l"}`,
				onclick: this.onclick},
				props.room_type === "Group" && !me?
					h("div",{class:"chat-bubble-author"},
						h("a", { onclick: () => { frappe.set_route(`Form/User/${props.user}`) } },
							frappe.user.full_name(props.user)
						)
					) : null,
				h("div",{class:"chat-bubble-content"},
						h("small","",
							props.type === "File" ?
								h("a", { class: "no-decoration", href: content.path, target: "_blank" },
									h(frappe.components.FontAwesome, { type: "file", fixed: true }), ` ${content.name}`
								)
								:
								content
						)
				),
				h("div",{class:"chat-bubble-meta"},
					h("span",{class:"chat-bubble-creation"},creation),
					me && read ?
						h("span",{class:"chat-bubble-check"},
							h(frappe.components.Octicon,{type:"check"})
						) : null
				)
			)
		)
	}
}

/**
 * @description ChatForm Component
 */
frappe.chat.component.ChatForm
=
class extends Component {
	constructor (props) {
		super (props)

		this.onchange   = this.onchange.bind(this)
		this.onsubmit   = this.onsubmit.bind(this)

		this.hint        = this.hint.bind(this)

		this.state       = frappe.chat.component.ChatForm.defaultState
	}

	onchange (e) {
		const { props, state } = this
		const value            = e.target.value

		this.set_state({
			[e.target.name]: value
		})

		props.onchange(state)

		this.hint(value)
	}

	hint (value) {
		const { props, state } = this

		if ( props.hint ) {
			const tokens =  value.split(" ")
			const sliced = tokens.slice(0, tokens.length - 1)

			const token  = tokens[tokens.length - 1]

			if ( token ) {
				props.hint   = frappe._.as_array(props.hint)
				const hint   = props.hint.find(hint => hint.match.test(token))

				if ( hint ) {
					hint.search(token, items => {
						const hints = items.map(item => {
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

	onsubmit (e) {
		e.preventDefault()

		if ( this.state.content ) {
			this.props.onsubmit(this.state.content)

			this.set_state({ content: null })
		}
	}

	render ( ) {
		const { props, state } = this

		return (
			h("div",{class:"chat-form"},
				state.hints.length ?
					h("ul", { class: "hint-list list-group" },
						state.hints.map((item) => {
							return (
								h("li", { class: "hint-list-item list-group-item" },
									h("a", { href: "javascript:void(0)", onclick: () => {
										this.set_state({ content: item.content, hints: [ ] })
									}},
										item.component
									)
								)
							)
						})
					) : null,
				h("form", { oninput: this.onchange, onsubmit: this.onsubmit },
					h("div",{class:"input-group input-group-lg"},
						!frappe._.is_empty(props.actions) ?
							h("div",{class:"input-group-btn dropup"},
								h(frappe.components.Button,{ class: "dropdown-toggle", "data-toggle": "dropdown"},
									h(frappe.components.FontAwesome, { class: "text-muted", type: "paperclip", fixed: true })
								),
								h("div",{ class:"dropdown-menu dropdown-menu-left", onclick: e => e.stopPropagation() },
									!frappe._.is_empty(props.actions) && props.actions.map((action) => {
										return (
											h("li", null,
												h("a",{onclick:action.onclick},
													h(frappe.components.FontAwesome,{type:action.icon,fixed:true}), ` ${action.label}`,
												)
											)
										)
									})
								)
							) : null,
						h("textarea", {
									class: "form-control",
									 name: "content",
									value: state.content,
							  placeholder: "Type a message",
								autofocus: true,
							   onkeypress: (e) => {
									if ( e.which === frappe.ui.keycode.RETURN && !e.shiftKey )
										this.onsubmit(e)
							   }
						}),
						h("div",{class:"input-group-btn"},
							h(frappe.components.Button, { onclick: this.onsubmit },
								h(frappe.components.FontAwesome, { class: !frappe._.is_empty(state.content) ? "text-primary" : "text-muted", type: "send", fixed: true })
							),
						)
					)
				)
			)
		)
	}
}
frappe.chat.component.ChatForm.defaultState
=
{
	content: null,
	  hints: [ ],
}

/**
 * @description EmojiPicker Component
 *
 * @todo Under Development
 */
frappe.chat.component.EmojiPicker
=
class extends Component  {
	render ( ) {
		const { props } = this

		return (
			h("div", { class: `frappe-chat-emoji dropup ${props.class}` },
				h(frappe.components.Button, { type: "primary", class: "dropdown-toggle", "data-toggle": "dropdown" },
					h(frappe.components.FontAwesome, { type: "smile-o", fixed: true })
				),
				h("div", { class: "dropdown-menu dropdown-menu-right", onclick: e => e.stopPropagation() },
					h("div", { class: "panel panel-default" },
						h(frappe.chat.component.EmojiPicker.List)
					)
				)
			)
		)
	}
}
frappe.chat.component.EmojiPicker.List
=
class extends Component {
	render ( ) {
		const { props } = this

		return (
			h("div", { class: "list-group" },

			)
		)
	}
}

/**
 * @description Python equivalent to sys.platform
 */
frappe.provide('frappe._')
frappe._.platform   = () => {
	const string    = navigator.appVersion

	if ( string.includes("Win") ) 	return "Windows"
	if ( string.includes("Mac") ) 	return "Darwin"
	if ( string.includes("X11") ) 	return "UNIX"
	if ( string.includes("Linux") ) return "Linux"

	return undefined
}

/**
 * @description Frappe's Asset Helper
 */
frappe.provide('frappe.assets')
frappe.assets.image = (image, app = 'frappe') => {
	const  path     = `/assets/${app}/images/${image}`
	return path
}

/**
 * @description Notify using Web Push Notifications
 */
frappe.provide('frappe.boot')
frappe.provide('frappe.browser')
frappe.browser.Notification = 'Notification' in window

frappe.notify     = (string, options) => {
	frappe.log    = frappe.Logger.get('frappe.notify')

	const OPTIONS = {
		icon: frappe.assets.image('favicon.png', 'frappe'),
		lang: frappe.boot.lang || "en"
	}
	options       = Object.assign({ }, OPTIONS, options)

	if ( !frappe.browser.Notification )
		frappe.log.error('ERROR: This browser does not support desktop notifications.')

	Notification.requestPermission(status => {
		if ( status === "granted" ) {
			const notification = new Notification(string, options)
		}
	})
}

frappe.chat.render = (render = true, force = false) =>
{
	frappe.log.info(`${render ? "Enable" : "Disable"} Chat for User.`)

	const desk = 'desk' in frappe
	if ( desk ) {
		// With the assumption, that there's only one navbar.
		const $placeholder = $('.navbar .frappe-chat-dropdown')

		// Render if frappe-chat-toggle doesn't exist.
		if ( frappe.utils.is_empty($placeholder.has('.frappe-chat-toggle')) ) {
			const $template = $(`
				<a class="dropdown-toggle frappe-chat-toggle" data-toggle="dropdown">
					<div>
						<i class="octicon octicon-comment-discussion"/>
					</div>
				</a>
			`)

			$placeholder.addClass('dropdown hidden')
			$placeholder.html($template)
		}

		if ( render ) {
			$placeholder.removeClass('hidden')
		} else {
			$placeholder.addClass('hidden')
		}
	}

	// Avoid re-renders. Once is enough.
	if ( !frappe.chatter || force ) {
		frappe.chatter = new frappe.Chat({
			target: desk ? '.frappe-chat-toggle' : null
		})

		if ( render ) {
			if ( frappe.session.user === 'Guest' && !desk ) {
				frappe.store = frappe.Store.get('frappe.chat')
				var token	 = frappe.store.get('guest_token')

				frappe.log.info(`Local Guest Token - ${token}`)

				const setup_room = (token) =>
				{
					return new Promise(resolve => {
						frappe.chat.room.create("Visitor", token).then(room => {
							frappe.log.info(`Visitor Room Created: ${room.name}`)
							frappe.chat.room.subscribe(room.name)

							var reference = room

							frappe.chat.room.history(room.name).then(messages => {
								const  room = { ...reference, messages: messages }
								return room
							}).then(room => {
								resolve(room)
							})
						})
					})
				}

				if ( !token ) {
					frappe.chat.website.token().then(token => {
						frappe.log.info(`Generated Guest Token - ${token}`)
						frappe.store.set('guest_token', token)

						setup_room(token).then(room => {
							frappe.chatter.render({ room })
						})
					})
				} else {
					setup_room(token).then(room => {
						frappe.chatter.render({ room })
					})
				}
			} else {
				frappe.chatter.render()
			}
		}
	}
}

frappe.chat.setup  = () => {
	frappe.log     = frappe.Logger.get('frappe.chat')

	frappe.log.info('Setting up frappe.chat')
	frappe.log.warn('TODO: frappe.chat.<object> requires a storage.')

	if ( frappe.session.user !== 'Guest' ) {
		// Create/Get Chat Profile for session User, retrieve enable_chat
		frappe.log.info('Creating a Chat Profile.')

		frappe.chat.profile.create('enable_chat').then(({ enable_chat }) => {
			frappe.log.info(`Chat Profile created for User ${frappe.session.user}.`)

			if ( 'desk' in frappe ) { // same as desk?
				const should_render = Boolean(parseInt(frappe.sys_defaults.enable_chat)) && enable_chat
				frappe.chat.render(should_render)
			}
		})

		// Triggered when a User updates his/her Chat Profile.
		// Don't worry, enable_chat is broadcasted to this user only. No overhead. :)
		frappe.chat.profile.on.update((user, profile) => {
			if ( user === frappe.session.user && 'enable_chat' in profile ) {
				frappe.log.warn(`Chat Profile update (Enable Chat - ${Boolean(profile.enable_chat)})`)
				const should_render = Boolean(parseInt(frappe.sys_defaults.enable_chat)) && profile.enable_chat
				frappe.chat.render(should_render)
			}
		})
	} else {
		// Website Settings
		frappe.log.info('Retrieving Chat Website Settings.')
		frappe.chat.website.settings(["socketio", "enable", "enable_from", "enable_to"])
			.then(settings => {
				frappe.log.info(`Chat Website Setting - ${JSON.stringify(settings)}`)
				frappe.log.info(`Chat Website Setting - ${settings.enable ? "Enable" : "Disable"}`)

				var should_render = settings.enable
				if ( settings.enable_from && settings.enable_to ) {
					frappe.log.info(`Enabling Chat Schedule - ${settings.enable_from.format()} : ${settings.enable_to.format()}`)

					const range   = new frappe.datetime.range(settings.enable_from, settings.enable_to)
					should_render = range.contains(frappe.datetime.now())
				}

				if ( should_render ) {
					frappe.log.info("Initializing Socket.IO")
					frappe.socketio.init(settings.socketio.port)
				}

				frappe.chat.render(should_render)
		})
	}
}

$(document).on('ready toolbar_setup', () =>
{
	frappe.chat.setup()
})
