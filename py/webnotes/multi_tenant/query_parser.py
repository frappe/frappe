import sqlparse
import webnotes
import webnotes.query_parser

def get_tables(parsed):
	start = 0
	for t in parsed[0].tokens:
		if str(t.ttype)=='Token.Keyword' and t.value.lower()=='from':
			start = 1
		if start and type(t).__name__=='Identifier':
			return [(str(t.get_real_name())),]
			
		if start and type(t).__name__=='IdentifierList':
			return [str(i.get_real_name()) for i in t.get_identifiers()]
	
	return tl
				
def add_condition(query):
	parsed = sqlparse.parse(query)
	
	# get the tables
	tl = get_tables(parsed)
	
	# rebuild the query till the where clause
	q = ''
	for t in parsed[0].tokens:
		q += str(t)
		
		# where clause comes here
		if type(t).__name__=='Where':
		
			# add the conditions for the tables
			for t in tl:
				if t not in webnotes.query_parser.shared_tables:
					q += ' and %s._tenant_id=%s' % (t, webnotes.tenant_id)
	
	return q
		
