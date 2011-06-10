editAreaLoader.load_syntax["cpp"] = {
	'COMMENT_SINGLE' : {1 : '//'}
	,'COMMENT_MULTI' : {'/*' : '*/'}
	,'QUOTEMARKS' : {1: "'", 2: '"'}
	,'KEYWORD_CASE_SENSITIVE' : true
	,'KEYWORDS' : {
		'constants' : [
			'NULL', 'false', 'std', 'stdin', 'stdout', 'stderr',
			'true'
		]
		,'types' : [
			'FILE', 'auto', 'char', 'class', 'const', 'double',
			'extern', 'float', 'friend', 'inline', 'int',
			'iterator', 'long', 'map', 'operator', 'queue',
			'register', 'short', 'signed', 'size_t', 'stack',
			'static', 'string', 'struct', 'time_t', 'typedef',
			'union', 'unsigned', 'vector', 'void', 'volatile'
		]
		,'statements' : [
			'catch', 'do', 'else', 'enum', 'for', 'goto', 'if',
			'sizeof', 'switch', 'this', 'throw', 'try', 'while'
		]
 		,'keywords' : [
			'break', 'case', 'continue', 'default', 'delete',
			'namespace', 'new', 'private', 'protected', 'public',
			'return', 'using'
		]
	}
	,'OPERATORS' :[
		'+', '-', '/', '*', '=', '<', '>', '%', '!', '?', ':', '&'
	]
	,'DELIMITERS' :[
		'(', ')', '[', ']', '{', '}'
	]
	,'REGEXPS' : {
		'precompiler' : {
			'search' : '()(#[^\r\n]*)()'
			,'class' : 'precompiler'
			,'modifiers' : 'g'
			,'execute' : 'before'
		}
/*		,'precompilerstring' : {
			'search' : '(#[\t ]*include[\t ]*)([^\r\n]*)([^\r\n]*[\r\n])'
			,'class' : 'precompilerstring'
			,'modifiers' : 'g'
			,'execute' : 'before'
		}*/
	}
	,'STYLES' : {
		'COMMENTS': 'color: #AAAAAA;'
		,'QUOTESMARKS': 'color: #6381F8;'
		,'KEYWORDS' : {
			'constants' : 'color: #EE0000;'
			,'types' : 'color: #0000EE;'
			,'statements' : 'color: #60CA00;'
			,'keywords' : 'color: #48BDDF;'
		}
		,'OPERATORS' : 'color: #FF00FF;'
		,'DELIMITERS' : 'color: #0038E1;'
		,'REGEXPS' : {
			'precompiler' : 'color: #009900;'
			,'precompilerstring' : 'color: #994400;'
		}
	}
};
