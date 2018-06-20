// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/*

Inheritence "Class"
-------------------
see: http://ejohn.org/blog/simple-javascript-inheritance/
To subclass, use:

	var MyClass = Class.extend({
		init: function
	})

*/
// https://stackoverflow.com/a/15052240/5353542

/* Simple JavaScript Inheritance for ES 5.1
 * based on http://ejohn.org/blog/simple-javascript-inheritance/
 *  (inspired by base2 and Prototype)
 * MIT Licensed.
 */
(function(global) {
	"use strict";
	var fnTest = /xyz/.test(function(){xyz;}) ? /\b_super\b/ : /.*/;

	// The base Class implementation (does nothing)
	function Class(){}

	// Create a new Class that inherits from this class
	Class.extend = function(props) {
	  var _super = this.prototype;

	  // Set up the prototype to inherit from the base class
	  // (but without running the init constructor)
	  var proto = Object.create(_super);

	  // Copy the properties over onto the new prototype
	  for (var name in props) {
		// Check if we're overwriting an existing function
		proto[name] = typeof props[name] === "function" &&
		  typeof _super[name] == "function" && fnTest.test(props[name])
		  ? (function(name, fn){
			  return function() {
				var tmp = this._super;

				// Add a new ._super() method that is the same method
				// but on the super-class
				this._super = _super[name];

				// The method only need to be bound temporarily, so we
				// remove it when we're done executing
				var ret = fn.apply(this, arguments);
				this._super = tmp;

				return ret;
			  };
			})(name, props[name])
		  : props[name];
	  }

	  // The new constructor
	  var newClass = typeof proto.init === "function"
		? proto.hasOwnProperty("init")
		  ? proto.init // All construction is actually done in the init method
		  : function SubClass(){ _super.init.apply(this, arguments); }
		: function EmptyClass(){};

	  // Populate our constructed prototype object
	  newClass.prototype = proto;

	  // Enforce the constructor to be what we expect
	  proto.constructor = newClass;

	  // And make this class extendable
	  newClass.extend = Class.extend;

	  return newClass;
	};

	// export
	global.Class = Class;
  })(this);