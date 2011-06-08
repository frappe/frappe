/**
 * Python syntax v 1.1 
 * 
 * v1.1 by Andre Roberge (2006/12/27)
 *   
**/
editAreaLoader.load_syntax["python"] = {
	'COMMENT_SINGLE' : {1 : '#'}
	,'COMMENT_MULTI' : {}
	,'QUOTEMARKS' : {1: "'", 2: '"'}
	,'KEYWORD_CASE_SENSITIVE' : true
	,'KEYWORDS' : {
		/*
		** Set 1: reserved words
		** http://python.org/doc/current/ref/keywords.html
		** Note: 'as' and 'with' have been added starting with Python 2.5
		*/
		'reserved' : [
			'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif',
			'else', 'except', 'exec', 'finally', 'for', 'from', 'global', 'if', 
			'import', 'is', 'in', 'lambda', 'not', 'or', 'pass', 'print', 'raise',
			'return', 'try', 'while', 'with', 'yield'
			//the following are *almost* reserved; we'll treat them as such
			, 'False', 'True', 'None'
		]
		/*
		** Set 2: builtins
		** http://python.org/doc/current/lib/built-in-funcs.html
		*/	
		,'builtins' : [
			'__import__', 'abs', 'basestring', 'bool', 'callable', 'chr', 'classmethod', 'cmp', 
			'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'execfile', 
			'file', 'filter', 'float', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help',
			'hex', 'id', 'input', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals',
			'long', 'map', 'max', 'min', 'object', 'oct', 'open', 'ord', 'pow', 'property', 'range',
			'raw_input', 'reduce', 'reload', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
			'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'unichr', 'unicode', 
			'vars', 'xrange', 'zip',
			// Built-in constants: http://www.python.org/doc/2.4.1/lib/node35.html
			//'False', 'True', 'None' have been included in 'reserved'
			'NotImplemented', 'Ellipsis',
			// Built-in Exceptions: http://python.org/doc/current/lib/module-exceptions.html
			'Exception', 'StandardError', 'ArithmeticError', 'LookupError', 'EnvironmentError',
			'AssertionError', 'AttributeError', 'EOFError', 'FloatingPointError', 'IOError',
			'ImportError', 'IndexError', 'KeyError', 'KeyboardInterrupt', 'MemoryError', 'NameError',
			'NotImplementedError', 'OSError', 'OverflowError', 'ReferenceError', 'RuntimeError',
			'StopIteration', 'SyntaxError', 'SystemError', 'SystemExit', 'TypeError',
			'UnboundlocalError', 'UnicodeError', 'UnicodeEncodeError', 'UnicodeDecodeError',
			'UnicodeTranslateError', 'ValueError', 'WindowsError', 'ZeroDivisionError', 'Warning',
			'UserWarning', 'DeprecationWarning', 'PendingDeprecationWarning', 'SyntaxWarning',
			'RuntimeWarning', 'FutureWarning',		
			// we will include the string methods as well
			// http://python.org/doc/current/lib/string-methods.html
			'capitalize', 'center', 'count', 'decode', 'encode', 'endswith', 'expandtabs',
			'find', 'index', 'isalnum', 'isaplpha', 'isdigit', 'islower', 'isspace', 'istitle',
			'isupper', 'join', 'ljust', 'lower', 'lstrip', 'replace', 'rfind', 'rindex', 'rjust',
			'rsplit', 'rstrip', 'split', 'splitlines', 'startswith', 'strip', 'swapcase', 'title',
			'translate', 'upper', 'zfill'
		]
		/*
		** Set 3: standard library
		** http://python.org/doc/current/lib/modindex.html
		*/
		,'stdlib' : [
			'__builtin__', '__future__', '__main__', '_winreg', 'aifc', 'AL', 'al', 'anydbm',
			'array', 'asynchat', 'asyncore', 'atexit', 'audioop', 'base64', 'BaseHTTPServer',
			'Bastion', 'binascii', 'binhex', 'bisect', 'bsddb', 'bz2', 'calendar', 'cd', 'cgi',
			'CGIHTTPServer', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs', 'codeop',
			'collections', 'colorsys', 'commands', 'compileall', 'compiler', 'compiler',
			'ConfigParser', 'Cookie', 'cookielib', 'copy', 'copy_reg', 'cPickle', 'crypt',
			'cStringIO', 'csv', 'curses', 'datetime', 'dbhash', 'dbm', 'decimal', 'DEVICE',
			'difflib', 'dircache', 'dis', 'distutils', 'dl', 'doctest', 'DocXMLRPCServer', 'dumbdbm',
			'dummy_thread', 'dummy_threading', 'email', 'encodings', 'errno', 'exceptions', 'fcntl',
			'filecmp', 'fileinput', 'FL', 'fl', 'flp', 'fm', 'fnmatch', 'formatter', 'fpectl',
			'fpformat', 'ftplib', 'gc', 'gdbm', 'getopt', 'getpass', 'gettext', 'GL', 'gl', 'glob',
			'gopherlib', 'grp', 'gzip', 'heapq', 'hmac', 'hotshot', 'htmlentitydefs', 'htmllib',
			'HTMLParser', 'httplib', 'imageop', 'imaplib', 'imgfile', 'imghdr', 'imp', 'inspect',
			'itertools', 'jpeg', 'keyword', 'linecache', 'locale', 'logging', 'mailbox', 'mailcap',
			'marshal', 'math', 'md5', 'mhlib', 'mimetools', 'mimetypes', 'MimeWriter', 'mimify',
			'mmap', 'msvcrt', 'multifile', 'mutex', 'netrc', 'new', 'nis', 'nntplib', 'operator',
			'optparse', 'os', 'ossaudiodev', 'parser', 'pdb', 'pickle', 'pickletools', 'pipes',
			'pkgutil', 'platform', 'popen2', 'poplib', 'posix', 'posixfile', 'pprint', 'profile',
			'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'Queue', 'quopri', 'random',
			're', 'readline', 'repr', 'resource', 'rexec', 'rfc822', 'rgbimg', 'rlcompleter',
			'robotparser', 'sched', 'ScrolledText', 'select', 'sets', 'sgmllib', 'sha', 'shelve',
			'shlex', 'shutil', 'signal', 'SimpleHTTPServer', 'SimpleXMLRPCServer', 'site', 'smtpd',
			'smtplib', 'sndhdr', 'socket', 'SocketServer', 'stat', 'statcache', 'statvfs', 'string',
			'StringIO', 'stringprep', 'struct', 'subprocess', 'sunau', 'SUNAUDIODEV', 'sunaudiodev',
			'symbol', 'sys', 'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios',
			'test', 'textwrap', 'thread', 'threading', 'time', 'timeit', 'Tix', 'Tkinter', 'token',
			'tokenize', 'traceback', 'tty', 'turtle', 'types', 'unicodedata', 'unittest', 'urllib2',
			'urllib', 'urlparse', 'user', 'UserDict', 'UserList', 'UserString', 'uu', 'warnings',
			'wave', 'weakref', 'webbrowser', 'whichdb', 'whrandom', 'winsound', 'xdrlib', 'xml',
			'xmllib', 'xmlrpclib', 'zipfile', 'zipimport', 'zlib'

		]
		/*
		** Set 4: special methods
		** http://python.org/doc/current/ref/specialnames.html
		*/
		,'special' : [
			// Basic customization: http://python.org/doc/current/ref/customization.html
			'__new__', '__init__', '__del__', '__repr__', '__str__', 
			'__lt__', '__le__', '__eq__', '__ne__', '__gt__', '__ge__', '__cmp__', '__rcmp__',
			'__hash__', '__nonzero__', '__unicode__', '__dict__',
			// Attribute access: http://python.org/doc/current/ref/attribute-access.html
			'__setattr__', '__delattr__', '__getattr__', '__getattribute__', '__get__', '__set__',
			'__delete__', '__slots__',
			// Class creation, callable objects
			'__metaclass__', '__call__', 
			// Container types: http://python.org/doc/current/ref/sequence-types.html
			'__len__', '__getitem__', '__setitem__', '__delitem__', '__iter__', '__contains__',
			'__getslice__', '__setslice__', '__delslice__',
			// Numeric types: http://python.org/doc/current/ref/numeric-types.html
			'__abs__','__add__','__and__','__coerce__','__div__','__divmod__','__float__',
			'__hex__','__iadd__','__isub__','__imod__','__idiv__','__ipow__','__iand__',
			'__ior__','__ixor__', '__ilshift__','__irshift__','__invert__','__int__',
			'__long__','__lshift__',
			'__mod__','__mul__','__neg__','__oct__','__or__','__pos__','__pow__',
			'__radd__','__rdiv__','__rdivmod__','__rmod__','__rpow__','__rlshift__','__rrshift__',
			'__rshift__','__rsub__','__rmul__','__repr__','__rand__','__rxor__','__ror__',
			'__sub__','__xor__'
		]
	}
	,'OPERATORS' :[
		'+', '-', '/', '*', '=', '<', '>', '%', '!', '&', ';', '?', '`', ':', ','
	]
	,'DELIMITERS' :[
		'(', ')', '[', ']', '{', '}'
	]
	,'STYLES' : {
		'COMMENTS': 'color: #AAAAAA;'
		,'QUOTESMARKS': 'color: #660066;'
		,'KEYWORDS' : {
			'reserved' : 'color: #0000FF;'
			,'builtins' : 'color: #009900;'
			,'stdlib' : 'color: #009900;'
			,'special': 'color: #006666;'
			}
		,'OPERATORS' : 'color: #993300;'
		,'DELIMITERS' : 'color: #993300;'
				
	}
};
