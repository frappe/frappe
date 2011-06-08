/***************************************************************************
 * (c) 2008 - file created by Christoph Pinkel, MTC Infomedia OHG.
 *
 * You may choose any license of the current release or any future release
 * of editarea to use, modify and/or redistribute this file.
 *
 * This language specification file supports for syntax checking on
 * a large subset of Perl 5.x.
 * The basic common syntax of Perl is fully supported, but as for
 * the highlighting of built-in operations, it's mainly designed
 * to support for hightlighting Perl code in a Safe environment (compartment)
 * as used by CoMaNet for evaluation of administrative scripts. This Safe
 * compartment basically allows for all of Opcode's :default operations,
 * but little others. See http://perldoc.perl.org/Opcode.html to learn
 * more.
 ***************************************************************************/

editAreaLoader.load_syntax["perl"] = {

	'COMMENT_SINGLE' : {1 : '#'},
	'QUOTEMARKS' : {1: "'", 2: '"'},
	'KEYWORD_CASE_SENSITIVE' : true,
	'KEYWORDS' :
	{
		'core' :
			[ "if", "else", "elsif", "while", "for", "each", "foreach",
				"next", "last", "goto", "exists", "delete", "undef",
				"my", "our", "local", "use", "require", "package", "keys", "values",
				"sub", "bless", "ref", "return" ],
		'functions' :
			[
				//from :base_core
				"int", "hex", "oct", "abs", "substr", "vec", "study", "pos",
				"length", "index", "rindex", "ord", "chr", "ucfirst", "lcfirst",
				"uc", "lc", "quotemeta", "chop", "chomp", "split", "list", "splice",
				"push", "pop", "shift", "unshift", "reverse", "and", "or", "dor",
				"xor", "warn", "die", "prototype",
				//from :base_mem
				"concat", "repeat", "join", "range",
				//none from :base_loop, as we'll see them as basic statements...
				//from :base_orig
				"sprintf", "crypt", "tie", "untie", "select", "localtime", "gmtime",
				//others
				"print", "open", "close"
			]
	},
	'OPERATORS' :
		[ '+', '-', '/', '*', '=', '<', '>', '!', '||', '.', '&&',
			' eq ', ' ne ', '=~' ],
	'DELIMITERS' :
		[ '(', ')', '[', ']', '{', '}' ],
	'REGEXPS' :
	{
		'packagedecl' : { 'search': '(package )([^ \r\n\t#;]*)()',
			'class' : 'scopingnames',
			'modifiers' : 'g', 'execute' : 'before' },
		'subdecl' : { 'search': '(sub )([^ \r\n\t#]*)()',
			'class' : 'scopingnames',
			'modifiers' : 'g', 'execute' : 'before' },
		'scalars' : { 'search': '()(\\\$[a-zA-Z0-9_:]*)()',
			'class' : 'vars',
			'modifiers' : 'g', 'execute' : 'after' },
		'arrays' : { 'search': '()(@[a-zA-Z0-9_:]*)()',
			'class' : 'vars',
			'modifiers' : 'g', 'execute' : 'after' },
		'hashs' : { 'search': '()(%[a-zA-Z0-9_:]*)()',
			'class' : 'vars',
			'modifiers' : 'g', 'execute' : 'after' },
	},

	'STYLES' :
	{
		'COMMENTS': 'color: #AAAAAA;',
		'QUOTESMARKS': 'color: #DC0000;',
		'KEYWORDS' :
		{
			'core' : 'color: #8aca00;',
			'functions' : 'color: #2B60FF;'
		},
		'OPERATORS' : 'color: #8aca00;',
		'DELIMITERS' : 'color: #0038E1;',
		'REGEXPS':
		{
			'scopingnames' : 'color: #ff0000;',
			'vars' : 'color: #00aaaa;',
		}
	} //'STYLES'
};
