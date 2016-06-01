/*
 * blueimp helper JS
 * https://github.com/blueimp/Gallery
 *
 * Copyright 2013, Sebastian Tschan
 * https://blueimp.net
 *
 * Licensed under the MIT license:
 * http://www.opensource.org/licenses/MIT
 */

/* global define, window, document */

;(function () {
  'use strict'

  function extend (obj1, obj2) {
    var prop
    for (prop in obj2) {
      if (obj2.hasOwnProperty(prop)) {
        obj1[prop] = obj2[prop]
      }
    }
    return obj1
  }

  function Helper (query) {
    if (!this || this.find !== Helper.prototype.find) {
      // Called as function instead of as constructor,
      // so we simply return a new instance:
      return new Helper(query)
    }
    this.length = 0
    if (query) {
      if (typeof query === 'string') {
        query = this.find(query)
      }
      if (query.nodeType || query === query.window) {
        // Single HTML element
        this.length = 1
        this[0] = query
      } else {
        // HTML element collection
        var i = query.length
        this.length = i
        while (i) {
          i -= 1
          this[i] = query[i]
        }
      }
    }
  }

  Helper.extend = extend

  Helper.contains = function (container, element) {
    do {
      element = element.parentNode
      if (element === container) {
        return true
      }
    } while (element)
    return false
  }

  Helper.parseJSON = function (string) {
    return window.JSON && JSON.parse(string)
  }

  extend(Helper.prototype, {
    find: function (query) {
      var container = this[0] || document
      if (typeof query === 'string') {
        if (container.querySelectorAll) {
          query = container.querySelectorAll(query)
        } else if (query.charAt(0) === '#') {
          query = container.getElementById(query.slice(1))
        } else {
          query = container.getElementsByTagName(query)
        }
      }
      return new Helper(query)
    },

    hasClass: function (className) {
      if (!this[0]) {
        return false
      }
      return new RegExp('(^|\\s+)' + className +
        '(\\s+|$)').test(this[0].className)
    },

    addClass: function (className) {
      var i = this.length
      var element
      while (i) {
        i -= 1
        element = this[i]
        if (!element.className) {
          element.className = className
          return this
        }
        if (this.hasClass(className)) {
          return this
        }
        element.className += ' ' + className
      }
      return this
    },

    removeClass: function (className) {
      var regexp = new RegExp('(^|\\s+)' + className + '(\\s+|$)')
      var i = this.length
      var element
      while (i) {
        i -= 1
        element = this[i]
        element.className = element.className.replace(regexp, ' ')
      }
      return this
    },

    on: function (eventName, handler) {
      var eventNames = eventName.split(/\s+/)
      var i
      var element
      while (eventNames.length) {
        eventName = eventNames.shift()
        i = this.length
        while (i) {
          i -= 1
          element = this[i]
          if (element.addEventListener) {
            element.addEventListener(eventName, handler, false)
          } else if (element.attachEvent) {
            element.attachEvent('on' + eventName, handler)
          }
        }
      }
      return this
    },

    off: function (eventName, handler) {
      var eventNames = eventName.split(/\s+/)
      var i
      var element
      while (eventNames.length) {
        eventName = eventNames.shift()
        i = this.length
        while (i) {
          i -= 1
          element = this[i]
          if (element.removeEventListener) {
            element.removeEventListener(eventName, handler, false)
          } else if (element.detachEvent) {
            element.detachEvent('on' + eventName, handler)
          }
        }
      }
      return this
    },

    empty: function () {
      var i = this.length
      var element
      while (i) {
        i -= 1
        element = this[i]
        while (element.hasChildNodes()) {
          element.removeChild(element.lastChild)
        }
      }
      return this
    },

    first: function () {
      return new Helper(this[0])
    }

  })

  if (typeof define === 'function' && define.amd) {
    define(function () {
      return Helper
    })
  } else {
    window.blueimp = window.blueimp || {}
    window.blueimp.helper = Helper
  }
}())
