editAreaLoader.load_syntax["js"] = {
	'COMMENT_SINGLE' : {1 : '//'}
	,'COMMENT_MULTI' : {'/*' : '*/'}
	,'QUOTEMARKS' : {1: "'", 2: '"'}
	,'KEYWORD_CASE_SENSITIVE' : false
	,'KEYWORDS' : {
		'statements' : [
			'as', 'break', 'case', 'catch', 'continue', 'decodeURI', 'delete', 'do',
			'else', 'encodeURI', 'eval', 'finally', 'for', 'if', 'in', 'is', 'item',
			'instanceof', 'return', 'switch', 'this', 'throw', 'try', 'typeof', 'void',
			'while', 'write', 'with'
		]
 		,'keywords' : [
			'class', 'const', 'default', 'debugger', 'export', 'extends', 'false',
			'function', 'import', 'namespace', 'new', 'null', 'package', 'private',
			'protected', 'public', 'super', 'true', 'use', 'var', 'window', 'document',		
			// the list below must be sorted and checked (if it is a keywords or a function and if it is not present twice
			'Link ', 'outerHeight ', 'Anchor', 'FileUpload', 
			'location', 'outerWidth', 'Select', 'Area', 'find', 'Location', 'Packages', 'self', 
			'arguments', 'locationbar', 'pageXoffset', 'Form', 
			'Math', 'pageYoffset', 'setTimeout', 'assign', 'Frame', 'menubar', 'parent', 'status', 
			'blur', 'frames', 'MimeType', 'parseFloat', 'statusbar', 'Boolean', 'Function', 'moveBy', 
			'parseInt', 'stop', 'Button', 'getClass', 'moveTo', 'Password', 'String', 'callee', 'Hidden', 
			'name', 'personalbar', 'Submit', 'caller', 'history', 'NaN', 'Plugin', 'sun', 'captureEvents', 
			'History', 'navigate', 'print', 'taint', 'Checkbox', 'home', 'navigator', 'prompt', 'Text', 
			'Image', 'Navigator', 'prototype', 'Textarea', 'clearTimeout', 'Infinity', 
			'netscape', 'Radio', 'toolbar', 'close', 'innerHeight', 'Number', 'ref', 'top', 'closed', 
			'innerWidth', 'Object', 'RegExp', 'toString', 'confirm', 'isFinite', 'onBlur', 'releaseEvents', 
			'unescape', 'constructor', 'isNan', 'onError', 'Reset', 'untaint', 'Date', 'java', 'onFocus', 
			'resizeBy', 'unwatch', 'defaultStatus', 'JavaArray', 'onLoad', 'resizeTo', 'valueOf', 'document', 
			'JavaClass', 'onUnload', 'routeEvent', 'watch', 'Document', 'JavaObject', 'open', 'scroll', 'window', 
			'Element', 'JavaPackage', 'opener', 'scrollbars', 'Window', 'escape', 'length', 'Option', 'scrollBy'			
		]
    	,'functions' : [
			// common functions for Window object
			'alert', 'Array', 'back', 'blur', 'clearInterval', 'close', 'confirm', 'eval ', 'focus', 'forward', 'home',
			'name', 'navigate', 'onblur', 'onerror', 'onfocus', 'onload', 'onmove',
			'onresize', 'onunload', 'open', 'print', 'prompt', 'scroll', 'scrollTo', 'setInterval', 'status',
			'stop' 
		]
	}
	,'OPERATORS' :[
		'+', '-', '/', '*', '=', '<', '>', '%', '!'
	]
	,'DELIMITERS' :[
		'(', ')', '[', ']', '{', '}'
	]
	,'STYLES' : {
		'COMMENTS': 'color: #AAAAAA;'
		,'QUOTESMARKS': 'color: #6381F8;'
		,'KEYWORDS' : {
			'statements' : 'color: #60CA00;'
			,'keywords' : 'color: #48BDDF;'
			,'functions' : 'color: #2B60FF;'
		}
		,'OPERATORS' : 'color: #FF00FF;'
		,'DELIMITERS' : 'color: #0038E1;'
				
	}
	,'AUTO_COMPLETION' :  {
		"default": {	// the name of this definition group. It's posisble to have different rules inside the same definition file
			"REGEXP": { "before_word": "[^a-zA-Z0-9_]|^"	// \\s|\\.|
						,"possible_words_letters": "[a-zA-Z0-9_]+"
						,"letter_after_word_must_match": "[^a-zA-Z0-9_]|$"
						,"prefix_separator": "\\."
					}
			,"CASE_SENSITIVE": true
			,"MAX_TEXT_LENGTH": 100		// the maximum length of the text being analyzed before the cursor position
			,"KEYWORDS": {
				'': [	// the prefix of thoses items
						/**
						 * 0 : the keyword the user is typing
						 * 1 : (optionnal) the string inserted in code ("{@}" being the new position of the cursor, "§" beeing the equivalent to the value the typed string indicated if the previous )
						 * 		If empty the keyword will be displayed
						 * 2 : (optionnal) the text that appear in the suggestion box (if empty, the string to insert will be displayed)
						 */
						 ['Array', '§()', '']
			    		,['alert', '§({@})', 'alert(String message)']
			    		,['document']
			    		,['window']
			    	]
		    	,'window' : [
			    		 ['location']
			    		,['document']
			    		,['scrollTo', 'scrollTo({@})', 'scrollTo(Int x,Int y)']
					]
		    	,'location' : [
			    		 ['href']
					]
			}
		}
	}
};
