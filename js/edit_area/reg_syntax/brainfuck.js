editAreaLoader.load_syntax["brainfuck"] = {
	'COMMENT_SINGLE' : {}
	,'COMMENT_MULTI' : {}
	,'QUOTEMARKS' : {}
	,'KEYWORD_CASE_SENSITIVE' : true
	,'OPERATORS' :[
		'+', '-'
	]
	,'DELIMITERS' :[
		'[', ']'
	]
	,'REGEXPS' : {
		'bfispis' : {
			'search' : '()(\\.)()'
			,'class' : 'bfispis'
			,'modifiers' : 'g'
			,'execute' : 'before'
		}
		,'bfupis' : {
			'search' : '()(\\,)()'
			,'class' : 'bfupis'
			,'modifiers' : 'g'
			,'execute' : 'before'
		}
		,'bfmemory' : {
			'search' : '()([<>])()'
			,'class' : 'bfmemory'
			,'modifiers' : 'g'
			,'execute' : 'before'
		}
	}
	,'STYLES' : {
		'COMMENTS': 'color: #AAAAAA;'
		,'QUOTESMARKS': 'color: #6381F8;'
		,'OPERATORS' : 'color: #88AA00;'
		,'DELIMITERS' : 'color: #00C138;'
		,'REGEXPS' : {
			'bfispis' : 'color: #EE0000;'
			,'bfupis' : 'color: #4455ee;'
			,'bfmemory' : 'color: #DD00DD;'
		}
	}
};

