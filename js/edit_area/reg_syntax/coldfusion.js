editAreaLoader.load_syntax["coldfusion"] = {
	'COMMENT_SINGLE' : {1 : '//', 2 : '#'}
	,'COMMENT_MULTI' : {'<!--' : '-->'}
	,'COMMENT_MULTI2' : {'<!---' : '--->'}
	,'QUOTEMARKS' : {1: "'", 2: '"'}
	,'KEYWORD_CASE_SENSITIVE' : false
		,'KEYWORDS' : {
		'statements' : [
			'include', 'require', 'include_once', 'require_once',
			'for', 'foreach', 'as', 'if', 'elseif', 'else', 'while', 'do', 'endwhile',
            'endif', 'switch', 'case', 'endswitch',
			'return', 'break', 'continue'
		]
		,'reserved' : [
			'AND', 'break', 'case', 'CONTAIN', 'CONTAINS', 'continue', 'default', 'do', 
			'DOES', 'else', 'EQ', 'EQUAL', 'EQUALTO', 'EQV', 'FALSE', 'for', 'GE', 
			'GREATER', 'GT', 'GTE', 'if', 'IMP', 'in', 'IS', 'LE', 'LESS', 'LT', 'LTE', 
			'MOD', 'NEQ', 'NOT', 'OR', 'return', 'switch', 'THAN', 'TO', 'TRUE', 'var', 
			'while', 'XOR'
		]
		,'functions' : [
			'Abs', 'ACos', 'ArrayAppend', 'ArrayAvg', 'ArrayClear', 'ArrayDeleteAt', 'ArrayInsertAt', 
			'ArrayIsEmpty', 'ArrayLen', 'ArrayMax', 'ArrayMin', 'ArrayNew', 'ArrayPrepend', 'ArrayResize', 
			'ArraySet', 'ArraySort', 'ArraySum', 'ArraySwap', 'ArrayToList', 'Asc', 'ASin', 'Atn', 'AuthenticatedContext', 
			'AuthenticatedUser', 'BitAnd', 'BitMaskClear', 'BitMaskRead', 'BitMaskSet', 'BitNot', 'BitOr', 
			'BitSHLN', 'BitSHRN', 'BitXor', 'Ceiling', 'Chr', 'CJustify', 'Compare', 'CompareNoCase', 'Cos', 
			'CreateDate', 'CreateDateTime', 'CreateODBCDate', 'CreateODBCDateTime', 'CreateODBCTime', 
			'CreateTime', 'CreateTimeSpan', 'DateAdd', 'DateCompare', 'DateConvert', 'DateDiff', 
			'DateFormat', 'DatePart', 'Day', 'DayOfWeek', 'DayOfWeekAsString', 'DayOfYear', 'DaysInMonth', 
			'DaysInYear', 'DE', 'DecimalFormat', 'DecrementValue', 'Decrypt', 'DeleteClientVariable', 
			'DirectoryExists', 'DollarFormat', 'Duplicate', 'Encrypt', 'Evaluate', 'Exp', 'ExpandPath', 
			'FileExists', 'Find', 'FindNoCase', 'FindOneOf', 'FirstDayOfMonth', 'Fix', 'FormatBaseN', 
			'GetBaseTagData', 'GetBaseTagList', 'GetBaseTemplatePath', 'GetClientVariablesList', 
			'GetCurrentTemplatePath', 'GetDirectoryFromPath', 'GetException', 'GetFileFromPath', 
			'GetFunctionList', 'GetHttpTimeString', 'GetHttpRequestData', 'GetLocale', 'GetMetricData', 
			'GetProfileString', 'GetTempDirectory', 'GetTempFile', 'GetTemplatePath', 'GetTickCount', 
			'GetTimeZoneInfo', 'GetToken', 'Hash', 'Hour', 'HTMLCodeFormat', 'HTMLEditFormat', 'IIf', 
			'IncrementValue', 'InputBaseN', 'Insert', 'Int', 'IsArray', 'IsAuthenticated', 'IsAuthorized', 
			'IsBoolean', 'IsBinary', 'IsCustomFunction', 'IsDate', 'IsDebugMode', 'IsDefined', 'IsLeapYear', 
			'IsNumeric', 'IsNumericDate', 'IsProtected', 'IsQuery', 'IsSimpleValue', 'IsStruct', 'IsWDDX', 
			'JavaCast', 'JSStringFormat', 'LCase', 'Left', 'Len', 'ListAppend', 'ListChangeDelims', 
			'ListContains', 'ListContainsNoCase', 'ListDeleteAt', 'ListFind', 'ListFindNoCase', 'ListFirst', 
			'ListGetAt', 'ListInsertAt', 'ListLast', 'ListLen', 'ListPrepend', 'ListQualify', 'ListRest', 
			'ListSetAt', 'ListSort', 'ListToArray', 'ListValueCount', 'ListValueCountNoCase', 'LJustify', 
			'Log', 'Log10', 'LSCurrencyFormat', 'LSDateFormat', 'LSEuroCurrencyFormat', 'LSIsCurrency', 
			'LSIsDate', 'LSIsNumeric', 'LSNumberFormat', 'LSParseCurrency', 'LSParseDateTime', 'LSParseNumber', 
			'LSTimeFormat', 'LTrim', 'Max', 'Mid', 'Min', 'Minute', 'Month', 'MonthAsString', 'Now', 'NumberFormat', 
			'ParagraphFormat', 'ParameterExists', 'ParseDateTime', 'Pi', 'PreserveSingleQuotes', 'Quarter', 
			'QueryAddRow', 'QueryNew', 'QuerySetCell', 'QuotedValueList', 'Rand', 'Randomize', 'RandRange', 
			'REFind', 'REFindNoCase', 'RemoveChars', 'RepeatString', 'Replace', 'ReplaceList', 'ReplaceNoCase', 
			'REReplace', 'REReplaceNoCase', 'Reverse', 'Right', 'RJustify', 'Round', 'RTrim', 'Second', 'SetLocale', 
			'SetProfileString', 'SetVariable', 'Sgn', 'Sin', 'SpanExcluding', 'SpanIncluding', 'Sqr', 'StripCR', 
			'StructAppend', 'StructClear', 'StructCopy', 'StructCount', 'StructDelete', 'StructFind', 'StructFindKey', 
			'StructFindValue', 'StructGet', 'StructInsert', 'StructIsEmpty', 'StructKeyArray', 'StructKeyExists', 
			'StructKeyList', 'StructNew', 'StructSort', 'StructUpdate', 'Tan', 'TimeFormat', 'ToBase64', 'ToBinary', 
			'ToString', 'Trim', 'UCase', 'URLDecode', 'URLEncodedFormat', 'Val', 'ValueList', 'Week', 'WriteOutput', 
			'XMLFormat', 'Year', 'YesNoFormat'
		]
	}
	,'OPERATORS' :[
		'+', '-', '/', '*', '%', '!', '&&', '||'
	]
	,'DELIMITERS' :[
		'(', ')', '[', ']', '{', '}'
	]
	,'REGEXPS' : {
		'doctype' : {
			'search' : '()(<!DOCTYPE[^>]*>)()'
			,'class' : 'doctype'
			,'modifiers' : ''
			,'execute' : 'before' // before or after
		}
		,'cftags' : {
			'search' : '(<)(/cf[a-z][^ \r\n\t>]*)([^>]*>)'
			,'class' : 'cftags'
			,'modifiers' : 'gi'
			,'execute' : 'before' // before or after
		}
		,'cftags2' : {
			'search' : '(<)(cf[a-z][^ \r\n\t>]*)([^>]*>)'
			,'class' : 'cftags2'
			,'modifiers' : 'gi'
			,'execute' : 'before' // before or after
		}
		,'tags' : {
			'search' : '(<)(/?[a-z][^ \r\n\t>]*)([^>]*>)'
			,'class' : 'tags'
			,'modifiers' : 'gi'
			,'execute' : 'before' // before or after
		}
		,'attributes' : {
			'search' : '( |\n|\r|\t)([^ \r\n\t=]+)(=)'
			,'class' : 'attributes'
			,'modifiers' : 'g'
			,'execute' : 'before' // before or after
		}
	}
	,'STYLES' : {
		'COMMENTS': 'color: #AAAAAA;'
		,'QUOTESMARKS': 'color: #6381F8;'
		,'KEYWORDS' : {
			'reserved' : 'color: #48BDDF;'
			,'functions' : 'color: #0000FF;'
			,'statements' : 'color: #60CA00;'
			}
		,'OPERATORS' : 'color: #E775F0;'
		,'DELIMITERS' : ''
		,'REGEXPS' : {
			'attributes': 'color: #990033;'
			,'cftags': 'color: #990033;'
			,'cftags2': 'color: #990033;'
			,'tags': 'color: #000099;'
			,'doctype': 'color: #8DCFB5;'
			,'test': 'color: #00FF00;'
		}	
	}		
};

 	  	 
