/**
 * Ruby syntax v 1.0 
 * 
 * v1.0 by Patrice De Saint Steban (2007/01/03)
 *   
**/
editAreaLoader.load_syntax["ruby"] = {
	'COMMENT_SINGLE' : {1 : '#'}
	,'COMMENT_MULTI' : {}
	,'QUOTEMARKS' : {1: "'", 2: '"'}
	,'KEYWORD_CASE_SENSITIVE' : true
	,'KEYWORDS' : {
		'reserved' : [
			'alias', 'and', 'BEGIN', 'begin', 'break', 'case', 'class', 'def', 'defined', 'do', 'else',
			'elsif', 'END', 'end', 'ensure', 'false', 'for', 'if', 
			'in', 'module', 'next', 'not', 'or', 'redo', 'rescue', 'retry',
			'return', 'self', 'super', 'then', 'true', 'undef', 'unless', 'until', 'when', 'while', 'yield'
		]
	}
	,'OPERATORS' :[
		'+', '-', '/', '*', '=', '<', '>', '%', '!', '&', ';', '?', '`', ':', ','
	]
	,'DELIMITERS' :[
		'(', ')', '[', ']', '{', '}'
	]
	,'REGEXPS' : {
		'constants' : {
			'search' : '()([A-Z]\\w*)()'
			,'class' : 'constants'
			,'modifiers' : 'g'
			,'execute' : 'before' 
		}
		,'variables' : {
			'search' : '()([\$\@\%]+\\w+)()'
			,'class' : 'variables'
			,'modifiers' : 'g'
			,'execute' : 'before' 
		}
		,'numbers' : {
			'search' : '()(-?[0-9]+)()'
			,'class' : 'numbers'
			,'modifiers' : 'g'
			,'execute' : 'before' 
		}
		,'symbols' : {
			'search' : '()(:\\w+)()'
			,'class' : 'symbols'
			,'modifiers' : 'g'
			,'execute' : 'before'
		}
	}
	,'STYLES' : {
		'COMMENTS': 'color: #AAAAAA;'
		,'QUOTESMARKS': 'color: #660066;'
		,'KEYWORDS' : {
			'reserved' : 'font-weight: bold; color: #0000FF;'
			}
		,'OPERATORS' : 'color: #993300;'
		,'DELIMITERS' : 'color: #993300;'
		,'REGEXPS' : {
			'variables' : 'color: #E0BD54;'
			,'numbers' : 'color: green;'
			,'constants' : 'color: #00AA00;'
			,'symbols' : 'color: #879EFA;'
		}	
	}
};
