"""
Server side methods for the follower pattern (Follow button used in forms)
"""

import webnotes
form = webnotes.form

#
# Follow
#
def follow(dt=None, dn=None, user=None, verbose=0):
	"Add as follower to a particular record. If no parameteres, then take from the http request (form)"
	
	if not dt: 
		dt, dn, user = form.get('dt'), form.get('dn'), form.get('user')
		verbose = 1

	if not user: return

	if not is_follower(dt, dn, user):
		make_follower(dt, dn, user, verbose)
	else:
		if verbose: webnotes.msgprint("%s is already a follower!" % user)

	return load_followers(dt, dn)

def make_follower(dt, dn, user, verbose):
	"Add the user as a follower"
	if has_permission(dt, user):
		from webnotes.model.doc import Document
		d = Document('Follower')
		d.doc_type = dt
		d.doc_name = dn
		d.owner = user
		d.save(1)
	else:
		if verbose: webnotes.msgprint('%s does not have sufficient permission to follow' % user)
		
def has_permission(dt, user):
	"Check to see if the user has permission to follow"

	return webnotes.conn.sql("select name from tabDocPerm where parent=%s and ifnull(`read`,0)=1 and role in ('%s') limit 1" \
		% ('%s', ("', '".join(webnotes.user.get_roles()))), dt)
	
def is_follower(dt, dn, user):
	"returns true if given user is a follower"
	
	return webnotes.conn.sql("""
		select name from tabFollower 
		where ifnull(doc_type,'')=%s 
		and ifnull(doc_name,'')=%s 
		and owner=%s""", (dt, dn, user))
#
# Unfollow
#
def unfollow(dt=None, dn=None, user=None):
	"Unfollow a particular record. If no parameteres, then take from the http request (form)"

	if not dt:
		dt, dn, user = form.get('dt'), form.get('dn'), form.get('user')

	webnotes.conn.sql("delete from tabFollower where doc_name=%s and doc_type=%s and owner=%s", (dn, dt, user))

	return load_followers(dt, dn)

#
# Load followers
#
def load_followers(dt=None, dn=None):
	"returns list of followers (Full Names) for a particular object"

	if not dt: dt, dn = form.get('dt'), form.get('dn')
		
	try:
		return [t[0] for t in webnotes.conn.sql("""
			SELECT IFNULL(CONCAT(t1.first_name, if(t1.first_name IS NULL, '', ' '), t1.last_name), t1.name)
			FROM tabProfile t1, tabFollower t2 WHERE t2.doc_type=%s AND t2.doc_name=%s 
			AND t1.name = t2.owner""", (dt, dn))]
			
	except Exception, e:
		if e.args[0] in (1146, 1054): 
			setup()
			return []
		else:
			raise e

#
# Email followers
#
def email_followers(dt, dn, msg_html=None, msg_text=None):
	"Send an email to all followers of this object"
	pass

#
# Update feed
#
def on_docsave(doc):
	"Add the owner and all linked Profiles as followers"
	follow(doc.doctype, doc.name, doc.owner)
	for p in get_profile_fields(doc.doctype):
		follow(doc.doctype, doc.name, doc.fields.get(p))

	update_followers(doc = doc)

#
# update the follower record timestamp and subject
#
def update_followers(dt=None, dn=None, subject=None, update_by=None, doc=None):
	"Updates the timestamp and subject in follower table (for feed generation)"
	from webnotes.utils import now
	webnotes.conn.sql("update tabFollower set modified=%s, subject=%s, modified_by=%s where doc_type=%s and doc_name=%s", \
		(now(), 
		subject or doc.fields.get('subject'), \
		update_by or webnotes.session['user'],\
		dt or doc.doctype, 
		dn or doc.name))

#
# get type of "Profile" fields
#
def get_profile_fields(dt):
	"returns a list of all profile link fields from the doctype"
	return [f[0] for f in \
		webnotes.conn.sql("select fieldname from tabDocField where parent=%s and fieldtype='Link' and options='Profile'", dt)]

#
# setup - make followers table
#
def setup():
	"Make table for followers - if missing"
	webnotes.conn.commit()
	from webnotes.modules.module_manager import reload_doc
	reload_doc('core', 'doctype', 'follower')
	webnotes.conn.begin()	
