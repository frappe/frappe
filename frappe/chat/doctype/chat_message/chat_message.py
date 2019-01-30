from __future__ import unicode_literals

# imports - standard imports
import json

# imports - third-party imports
import requests
from bs4 import BeautifulSoup as Soup

# imports - module imports
from   frappe.model.document import Document
from   frappe import _, _dict
import frappe

# imports - frappe module imports
from frappe.chat 	  import authenticate
from frappe.chat.util import (
	get_if_empty,
	check_url,
	dictify,
	get_emojis,
	safe_json_loads,
	get_user_doc,
	squashify
)

session = frappe.session

class ChatMessage(Document):
	pass

def get_message_urls(content):
	soup     = Soup(content, 'html.parser')
	anchors  = soup.find_all('a')
	urls     = [ ]

	for anchor in anchors:
		text = anchor.text

		if check_url(text):
			urls.append(text)

	return urls

def get_message_mentions(content):
	mentions = [ ]
	tokens   = content.split(' ')

	for token in tokens:
		if token.startswith('@'):
			what = token[1:]
			if frappe.db.exists('User', what):
				mentions.append(what)
		else:
			if frappe.db.exists('User', token):
				mentions.append(token)

	return mentions

def get_message_meta(content):
	'''
		Assumes content to be HTML. Sanitizes the content
		into a dict of metadata values.
	'''
	meta = _dict(
		links 	 = [ ],
		mentions = [ ]
	)

	meta.content  = content
	meta.urls	  = get_message_urls(content)
	meta.mentions = get_message_mentions(content)

	return meta

def sanitize_message_content(content):
	emojis = get_emojis()

	tokens = content.split(' ')
	for token in tokens:
		if token.startswith(':') and token.endswith(':'):
			what = token[1:-1]

			# Expensive, I know.
			for emoji in emojis:
				for alias in emoji.aliases:
					if what == alias:
						content = content.replace(token, emoji.emoji)

	return content

def get_new_chat_message_doc(user, room, content, type = "Content", link = True):
	user = get_user_doc(user)
	room = frappe.get_doc('Chat Room', room)

	meta = get_message_meta(content)
	mess = frappe.new_doc('Chat Message')
	mess.room 	   = room.name
	mess.room_type = room.type
	mess.content   = sanitize_message_content(content)
	mess.type      = type
	mess.user	   = user.name

	mess.mentions  = json.dumps(meta.mentions)
	mess.urls      = ','.join(meta.urls)
	mess.save(ignore_permissions = True)

	if link:
		room.update(dict(
			last_message = mess.name
		))
		room.save(ignore_permissions = True)

	return mess

def get_new_chat_message(user, room, content, type = "Content"):
	mess = get_new_chat_message_doc(user, room, content, type)

	resp = dict(
		name      = mess.name,
		user      = mess.user,
		room      = mess.room,
		room_type = mess.room_type,
		content   = json.loads(mess.content) if mess.type in ["File"] else mess.content,
		urls      = mess.urls,
		mentions  = json.loads(mess.mentions),
		creation  = mess.creation,
		seen      = json.loads(mess._seen) if mess._seen else [ ],
	)

	return resp

@frappe.whitelist(allow_guest = True)
def send(user, room, content, type = "Content"):
	mess = get_new_chat_message(user, room, content, type)

	frappe.publish_realtime('frappe.chat.message:create', mess, room = room,
		after_commit = True)

@frappe.whitelist(allow_guest = True)
def seen(message, user = None):
	authenticate(user)

	mess = frappe.get_doc('Chat Message', message)
	mess.add_seen(user)

	room = mess.room
	resp = dict(message = message, data = dict(seen = json.loads(mess._seen)))

	frappe.publish_realtime('frappe.chat.message:update', resp, room = room, after_commit = True)

def history(room, fields = None, limit = 10, start = None, end = None):
	room = frappe.get_doc('Chat Room', room)
	mess = frappe.get_all('Chat Message',
		filters  = [
			('Chat Message', 'room', 	  '=', room.name),
			('Chat Message', 'room_type', '=', room.type)
		],
		fields   = fields if fields else [
			'name', 'room_type', 'room', 'content', 'type', 'user', 'mentions', 'urls', 'creation', '_seen'
		],
		order_by = 'creation'
	)

	if not fields or 'seen' in fields:
		for m in mess:
			m['seen'] = json.loads(m._seen) if m._seen else [ ]
			del m['_seen']
	if not fields or 'content' in fields:
		for m in mess:
			m['content'] = json.loads(m.content) if m.type in ["File"] else m.content

	frappe.enqueue('frappe.chat.doctype.chat_message.chat_message.mark_messages_as_seen',
		message_names=[m.name for m in mess], user=frappe.session.user)

	return mess

def mark_messages_as_seen(message_names, user):
	'''
	Marks chat messages as seen, updates the _seen for each message
	(should be run in background process)
	'''
	for name in message_names:
		seen = frappe.db.get_value('Chat Message', name, '_seen') or '[]'
		seen = json.loads(seen)
		seen.append(user)
		seen = json.dumps(seen)
		frappe.db.set_value('Chat Message', name, '_seen', seen, update_modified=False)

	frappe.db.commit()


@frappe.whitelist()
def get(name, rooms = None, fields = None):
	rooms, fields = safe_json_loads(rooms, fields)

	dmess = frappe.get_doc('Chat Message', name)
	data  = dict(
		name      = dmess.name,
		user      = dmess.user,
		room      = dmess.room,
		room_type = dmess.room_type,
		content   = json.loads(dmess.content) if dmess.type in ["File"] else dmess.content,
		type      = dmess.type,
		urls      = dmess.urls,
		mentions  = dmess.mentions,
		creation  = dmess.creation,
		seen      = get_if_empty(dmess._seen, [ ])
	)

	return data