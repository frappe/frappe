editAreaLoader.load_syntax["basic"] = {
	'COMMENT_SINGLE' : {1 : "'", 2 : 'rem'}
	,'COMMENT_MULTI' : { }
	,'QUOTEMARKS' : {1: '"'}
	,'KEYWORD_CASE_SENSITIVE' : false
	,'KEYWORDS' : {
		'statements' : [
			'if','then','for','wend','while',
			'else','elseif','select','case','end select',
			'until','next','step','to','end if', 'call'
		]
		,'keywords' : [
			'sub', 'end sub', 'function', 'end function', 'exit',
			'exit function', 'dim', 'redim', 'shared', 'const',
			'is', 'absolute', 'access', 'any', 'append', 'as',
			'base', 'beep', 'binary', 'bload', 'bsave', 'chain',
			'chdir', 'circle', 'clear', 'close', 'cls', 'color',
			'com', 'common', 'data', 'date', 'declare', 'def',
			'defdbl', 'defint', 'deflng', 'defsng', 'defstr',
			'double', 'draw', 'environ', 'erase', 'error', 'field',
			'files', 'fn', 'get', 'gosub', 'goto', 'integer', 'key',
			'kill', 'let', 'line', 'list', 'locate', 'lock', 'long',
			'lprint', 'lset', 'mkdir', 'name', 'off', 'on', 'open',
			'option', 'out', 'output', 'paint', 'palette', 'pcopy',
			'poke', 'preset', 'print', 'pset', 'put', 'random',
			'randomize', 'read', 'reset', 'restore', 'resume',
			'return', 'rmdir', 'rset', 'run', 'screen', 'seg',
			'shell', 'single', 'sleep', 'sound', 'static', 'stop',
			'strig', 'string', 'swap', 'system', 'time', 'timer',
			'troff', 'tron', 'type', 'unlock', 'using', 'view',
			'wait', 'width', 'window', 'write'
	        ]
		,'functions' : [
			'abs', 'asc', 'atn', 'cdbl', 'chr', 'cint', 'clng',
			'cos', 'csng', 'csrlin', 'cvd', 'cvdmbf', 'cvi', 'cvl',
			'cvs', 'cvsmbf', 'eof', 'erdev', 'erl', 'err', 'exp',
			'fileattr', 'fix', 'fre', 'freefile', 'hex', 'inkey',
			'inp', 'input', 'instr', 'int', 'ioctl', 'lbound',
			'lcase', 'left', 'len', 'loc', 'lof', 'log', 'lpos',
			'ltrim', 'mid', 'mkd', 'mkdmbf', 'mki', 'mkl', 'mks',
			'mksmbf', 'oct', 'peek', 'pen', 'play', 'pmap', 'point',
			'pos', 'right', 'rnd', 'rtrim', 'seek', 'sgn', 'sin',
			'space', 'spc', 'sqr', 'stick', 'str', 'tab', 'tan',
			'ubound', 'ucase', 'val', 'varptr', 'varseg'
		]
		,'operators' : [
			'and', 'eqv', 'imp', 'mod', 'not', 'or', 'xor'
		]
	}
	,'OPERATORS' :[
		'+', '-', '/', '*', '=', '<', '>', '!', '&'
	]
	,'DELIMITERS' :[
		'(', ')', '[', ']', '{', '}'
	]
	,'STYLES' : {
		'COMMENTS': 'color: #99CC00;'
		,'QUOTESMARKS': 'color: #333399;'
		,'KEYWORDS' : {
			'keywords' : 'color: #3366FF;'
			,'functions' : 'color: #0000FF;'
			,'statements' : 'color: #3366FF;'
			,'operators' : 'color: #FF0000;'
			}
		,'OPERATORS' : 'color: #FF0000;'
		,'DELIMITERS' : 'color: #0000FF;'

	}
};
