(function($){
	var $chk = function(obj){
		return !!(obj || obj === 0);
	};

	/**
	 * Masks an input with a pattern
	 * @class
	 * @requires jQuery
	 * @name jQuery.iMask
	 * @param {Object}    options
	 * @param {String}    options.type (number|fixed)
	 * @param {String}    options.mask Mask using 9,a,x notation
	 * @param {String}   [options.maskEmptyChr=' ']
	 * @param {String}   [options.validNumbers='1234567890']
	 * @param {String}   [options.validAlphas='abcdefghijklmnopqrstuvwxyz']
	 * @param {String}   [options.validAlphaNums='abcdefghijklmnopqrstuvwxyz1234567890']
	 * @param {Number}   [options.groupDigits=3]
	 * @param {Number}   [options.decDigits=2]
	 * @param {String}   [options.currencySymbol]
	 * @param {String}   [options.groupSymbol=',']
	 * @param {String}   [options.decSymbol='.']
	 * @param {Boolean}  [options.showMask=true]
	 * @param {Boolean}  [options.stripMask=false]
	 * @param {Function} [options.sanity]
	 * @param {Object}   [options.number] Override options for when validating numbers only
	 * @param {Boolean}  [options.number.stripMask=false]
	 * @param {Boolean}  [options.number.showMask=false]
	 */
	var iMask = function(){
		this.initialize.apply(this, arguments);
	};

	iMask.prototype = {
		std_options: {
			maskEmptyChr   : ' ',

			validNumbers   : "1234567890",
			validAlphas    : "abcdefghijklmnopqrstuvwxyz",
			validAlphaNums : "abcdefghijklmnopqrstuvwxyz1234567890",

			groupDigits    : 3,
			decDigits      : 2,
			currencySymbol : '',
			groupSymbol    : ',',
			decSymbol      : '.',
			showMask       : true,
			stripMask      : false,

			lastFocus      : 0,

			number : {
				stripMask : false,
				showMask  : false
			}
		},

		initialize: function(node, options) {
			this.node    = node;
			this.domNode = node[0];
			this.setOptions(options);
			var self     = this;

			if(options.type == "number") this.node.css("text-align", "right");

			this.node
				.bind( "mousedown click", function(ev){
					ev.stopPropagation(); ev.preventDefault(); } )

				.bind( "mouseup",  function(){ self.onMouseUp .apply(self, arguments); } )
				.bind( "keydown",  function(){ self.onKeyDown .apply(self, arguments); } )
				.bind( "keypress", function(){ self.onKeyPress.apply(self, arguments); } )
				.bind( "focus",    function(){ self.onFocus   .apply(self, arguments); } )
				//.bind( "blur",     function(){ self.onBlur    .apply(self, arguments); } );
		},
		
		setOptions: function(options) {
			this.options = $.extend({}, 
				this.std_options, this.std_options[options.type] || {}, options);
		},

		isFixed  : function(){ return this.options.type == 'fixed';  },
		isNumber : function(){ return this.options.type == 'number'; },

		onMouseUp: function( ev ) {
			ev.stopPropagation();
			ev.preventDefault();

			if( this.isFixed() ) {
				var p = this.getSelectionStart();
				this.setSelection(p, (p + 1));
			} else if(this.isNumber() ) {
				this.setEnd();
			}
		},

		onKeyDown: function(ev) {
			if(ev.ctrlKey || ev.altKey || ev.metaKey) {
				return;

			} else if(ev.which == 13) { // enter
				this.node.blur();

				this.submitForm(this.node);

			} else if(!(ev.which == 9)) { // tab
				if(this.options.type == "fixed") {
					ev.preventDefault();

					var p = this.getSelectionStart();
					switch(ev.which) {
						case 8: // Backspace
							this.updateSelection( this.options.maskEmptyChr );
							this.selectPrevious();
							break;
						case 36: // Home
							this.selectFirst();
							break;
						case 35: // End
							this.selectLast();
							break;
						case 37: // Left
						case 38: // Up
							this.selectPrevious();
							break;
						case 39: // Right
						case 40: // Down
							this.selectNext();
							break;
						case 46: // Delete
							this.updateSelection( this.options.maskEmptyChr );
							this.selectNext();
							break;
						default:
							var chr = this.chrFromEv(ev);
							if( this.isViableInput( p, chr ) ) {
								this.updateSelection( ev.shiftKey ? chr.toUpperCase() : chr );
								this.node.trigger("valid", ev, this.node);
								this.selectNext();
							} else {
								this.node.trigger("invalid", ev, this.node);
							}
							break;
					}
				} else if(this.options.type == "number") {
					switch(ev.which) {
						case 35: // END
						case 36: // HOME
						case 37: // LEFT
						case 38: // UP
						case 39: // RIGHT
						case 40: // DOWN
							break;
						case 8:  // backspace
						case 46: // delete
							var self = this;
							setTimeout(function(){
								self.formatNumber();
							}, 1);
							break;

						default:
							ev.preventDefault();

							var chr = this.chrFromEv( ev );
							if( this.isViableInput( p, chr ) ) {
								var range = new Range( this )
								 ,    val = this.sanityTest( range.replaceWith( chr ) );

								if(val !== false){
									this.updateSelection( chr );
									this.formatNumber();
								}
								this.node.trigger( "valid", ev, this.node );
							} else {	
								this.node.trigger( "invalid", ev, this.node );
							}
							break;
					}
				}
			}
		},

		allowKeys : {
			   8 : 1 // backspace
			,  9 : 1 // tab
			, 13 : 1 // enter
			, 35 : 1 // end
			, 36 : 1 // home
			, 37 : 1 // left
			, 38 : 1 // up
			, 39 : 1 // right
			, 40 : 1 // down
			, 46 : 1 // delete
		},

		onKeyPress: function(ev) {
			var key = ev.which || ev.keyCode;

			if(
				!( this.allowKeys[ key ] )
				&& !(ev.ctrlKey || ev.altKey || ev.metaKey)
			) {
				ev.preventDefault();
				ev.stopPropagation();
			}
		},

		onFocus: function(ev) {
			ev.stopPropagation();
			ev.preventDefault();

			this.options.showMask && (this.domNode.value = this.wearMask(this.domNode.value));
			this.sanityTest( this.domNode.value );

			var self = this;

			setTimeout( function(){
				self[ self.options.type === "fixed" ? 'selectFirst' : 'setEnd' ]();
			}, 1 );
		},

		onBlur: function(ev) {
			// ev.stopPropagation();
			// ev.preventDefault();
			// 
			// if(this.options.stripMask)
			// 	this.domNode.value = this.stripMask();
		},

		selectAll: function() {
			this.setSelection(0, this.domNode.value.length);
		},

		selectFirst: function() {
			for(var i = 0, len = this.options.mask.length; i < len; i++) {
				if(this.isInputPosition(i)) {
					this.setSelection(i, (i + 1));
					return;
				}
			}
		},

		selectLast: function() {
			for(var i = (this.options.mask.length - 1); i >= 0; i--) {
				if(this.isInputPosition(i)) {
					this.setSelection(i, (i + 1));
					return;
				}
			}
		},

		selectPrevious: function(p) {
			if( !$chk(p) ){ p = this.getSelectionStart(); }

			if(p <= 0) {
				this.selectFirst();
			} else {
				if(this.isInputPosition(p - 1)) {
					this.setSelection(p - 1, p);
				} else {
					this.selectPrevious(p - 1);
				}
			}
		},

		selectNext: function(p) {
			if( !$chk(p) ){ p = this.getSelectionEnd(); }

			if( this.isNumber() ){
				this.setSelection( p+1, p+1 );
				return;
			}

			if( p >= this.options.mask.length) {
				this.selectLast();
			} else {
				if(this.isInputPosition(p)) {
					this.setSelection(p, (p + 1));
				} else {
					this.selectNext(p + 1);
				}
			}
		},

		setSelection: function( a, b ) {
			a = a.valueOf();
			if( !b && a.splice ){
				b = a[1];
				a = a[0];
			}

			if(this.domNode.setSelectionRange) {
				this.domNode.focus();
				this.domNode.setSelectionRange(a, b);
			} else if(this.domNode.createTextRange) {
				var r = this.domNode.createTextRange();
				r.collapse();
				r.moveStart("character", a);
				r.moveEnd("character", (b - a));
				r.select();
			}
		},

		updateSelection: function( chr ) {
			var value = this.domNode.value
			 ,  range = new Range( this )
			 , output = range.replaceWith( chr );

			this.domNode.value = output;
			if( range[0] === range[1] ){
				this.setSelection( range[0] + 1, range[0] + 1 );
			}else{
				this.setSelection( range );
			}
		},

	 	setEnd: function() {
			var len = this.domNode.value.length;
			this.setSelection(len, len);
		},

		getSelectionRange : function(){
			return [ this.getSelectionStart(), this.getSelectionEnd() ];
		},

		getSelectionStart: function() {
			var p = 0,
			    n = this.domNode.selectionStart;

			if( n ) {
				if( typeof( n ) == "number" ){
					p = n;
				}
			} else if( document.selection ){
				var r = document.selection.createRange().duplicate();
				r.moveEnd( "character", this.domNode.value.length );
				p = this.domNode.value.lastIndexOf( r.text );
				if( r.text == "" ){
					p = this.domNode.value.length;
				}
			}
			return p;
		},

		getSelectionEnd: function() {
			var p = 0,
			    n = this.domNode.selectionEnd;

			if( n ) {
				if( typeof( n ) == "number"){
					p = n;
				}
			} else if( document.selection ){
				var r = document.selection.createRange().duplicate();
				r.moveStart( "character", -this.domNode.value.length );
				p = r.text.length;
			}
			return p;
		},

		isInputPosition: function(p) {
			var mask = this.options.mask.toLowerCase();
			var chr = mask.charAt(p);
			return !!~"9ax".indexOf(chr);
		},

		sanityTest: function( str, p ){
			var sanity = this.options.sanity;

			if(sanity instanceof RegExp){
				return sanity.test(str);
			}else if($.isFunction(sanity)){
				var ret = sanity(str, p);
				if(typeof(ret) == 'boolean'){
					return ret;
				}else if(typeof(ret) != 'undefined'){
					if( this.isFixed() ){
						var p = this.getSelectionStart();
						this.domNode.value = this.wearMask( ret );
						this.setSelection( p, p+1 );
						this.selectNext();
					}else if( this.isNumber() ){
						var range = new Range( this );
						this.domNode.value = ret;
						this.setSelection( range );
						this.formatNumber();
					}
					return false;
				}
			}
		},

		isViableInput: function() {
			return this[ this.isFixed() ? 'isViableFixedInput' : 'isViableNumericInput' ].apply( this, arguments );
		},

		isViableFixedInput : function( p, chr ){
			var mask   = this.options.mask.toLowerCase();
			var chMask = mask.charAt(p);

			var val = this.domNode.value.split('');
			val.splice( p, 1, chr );
			val = val.join('');

			var ret = this.sanityTest( val, p );
			if(typeof(ret) == 'boolean'){ return ret; }

			if(({
				'9' : this.options.validNumbers,
				'a' : this.options.validAlphas,
				'x' : this.options.validAlphaNums
			}[chMask] || '').indexOf(chr) >= 0){
				return true;
			}

			return false;
		},

		isViableNumericInput : function( p, chr ){
			return !!~this.options.validNumbers.indexOf( chr );
		},

		wearMask: function(str) {
			var   mask = this.options.mask.toLowerCase()
			 ,  output = ""
			 , chrSets = {
				  '9' : 'validNumbers'
				, 'a' : 'validAlphas'
				, 'x' : 'validAlphaNums'
			};

			for(var i = 0, u = 0, len = mask.length; i < len; i++) {
				switch(mask.charAt(i)) {
					case '9':
					case 'a':
					case 'x':
						output += 
							((this.options[ chrSets[ mask.charAt(i) ] ].indexOf( str.charAt(u).toLowerCase() ) >= 0) && ( str.charAt(u) != ""))
								? str.charAt( u++ )
								: this.options.maskEmptyChr;
						break;

					default:
						output += mask.charAt(i);
						if( str.charAt(u) == mask.charAt(i) ){
							u++;
						}

						break;
				}
			}
			return output;
		},

		stripMask: function() {
			var value = this.domNode.value;
			if("" == value) return "";
			var output = "";

			if( this.isFixed() ) {
				for(var i = 0, len = value.length; i < len; i++) {
					if((value.charAt(i) != this.options.maskEmptyChr) && (this.isInputPosition(i)))
						{output += value.charAt(i);}
				}
			} else if( this.isNumber() ) {
				for(var i = 0, len = value.length; i < len; i++) {
					if(this.options.validNumbers.indexOf(value.charAt(i)) >= 0)
						{output += value.charAt(i);}
				}
			}

			return output;
		},

		chrFromEv: function(ev) {
			var chr = '', key = ev.which;

			if(key >= 96 && key <= 105){ key -= 48; }     // shift number-pad numbers to corresponding character codes
			chr = String.fromCharCode(key).toLowerCase(); // key pressed as a lowercase string
			return chr;
		},

		formatNumber: function() {
			// stripLeadingZeros
			var olen = this.domNode.value.length
			 ,  str2 = this.stripMask()
			 ,  str1 = str2.replace( /^0+/, '' )
			 , range = new Range(this);

			// wearLeadingZeros

			str2 = str1;
			str1 = "";
			for(var len = str2.length, i = this.options.decDigits; len <= i; len++) {
				str1 += "0";
			}
			str1 += str2;

			// decimalSymbol
			str2 = str1.substr(str1.length - this.options.decDigits)
			str1 = str1.substring(0, (str1.length - this.options.decDigits))

			// groupSymbols
			var re = new RegExp("(\\d+)(\\d{"+ this.options.groupDigits +"})");
			while(re.test(str1)) {
				str1 = str1.replace(re, "$1"+ this.options.groupSymbol +"$2");
			}

			this.domNode.value = this.options.currencySymbol + str1 + this.options.decSymbol + str2;
			this.setSelection( range );
		},

		getObjForm: function() {
			return this.node.getClosest('form');
		},

		submitForm: function() {
			//var form = this.getObjForm();
			//form.trigger('submit');
		}
	};

	function Range( obj ){
		this.range = obj.getSelectionRange();
		this.len   = obj.domNode.value.length
		this.obj   = obj;

		this['0']  = this.range[0];
		this['1']  = this.range[1];
	}
	Range.prototype = {
		valueOf : function(){
			var len = this.len - this.obj.domNode.value.length;
			return [ this.range[0] - len, this.range[1] - len ];
		},
		replaceWith : function( str ){
			var  val = this.obj.domNode.value
			 , range = this.valueOf();

			return val.substr( 0, range[0] ) + str + val.substr( range[1] );
		}
	};

	$.fn.iMask = function(options){
		this.each(function(){
			if(this._imask) {
				// don't re-initialize, just reset the options dynamically
				this._imask.setOptions(options);
			} else {
				this._imask = new iMask($(this), options);
			}
		});
	};
})(jQuery);
