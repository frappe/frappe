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
from frappe.chat.util import (
	assign_if_empty,
	check_url,
	dictify,
	get_emojis,
	safe_json_loads,
	get_user_doc
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

def get_new_chat_message_doc(user, room, content, link = True):
	user = get_user_doc(user)
	room = frappe.get_doc('Chat Room', room)

	meta = get_message_meta(content)
	mess = frappe.new_doc('Chat Message')
	mess.type     = room.type
	mess.room 	  = room.name
	mess.content  = sanitize_message_content(content)
	mess.user	  = user.name

	mess.mentions = json.dumps(meta.mentions)
	mess.urls     = ','.join(meta.urls)
	mess.save(ignore_permissions = True)

	if link:
		room.update(dict(
			last_message = mess.name
		))
		room.save(ignore_permissions = True)

	return mess

def get_new_chat_message(user, room, content):
	mess = get_new_chat_message_doc(user, room, content)

	resp = dict(
		name     = mess.name,
		user     = mess.user,
		room     = mess.room,
		content  = mess.content,
		urls     = mess.urls,
		mentions = json.loads(mess.mentions),
		creation = mess.creation,
		seen     = json.loads(mess._seen) if mess._seen else [ ],
	)

	return resp

@frappe.whitelist()
def send(user, room, content):
	mess = get_new_chat_message(user, room, content)
	
	frappe.publish_realtime('frappe.chat.message:create', mess, room = room,
		after_commit = True)

@frappe.whitelist()
def seen(message, user = None):
	mess = frappe.get_doc('Chat Message', message)
	mess.add_seen(user)

	room = mess.room
	resp = dict(message = message, data = dict(seen = json.loads(mess._seen)))
	
	frappe.publish_realtime('frappe.chat.message:update', resp, room = room, after_commit = True)

# This is fine for now. If you're "ReST"-ing it,
# make sure you don't let the user see them.
# Come again, Why are we even passing user?
def get_messages(room, user = None, fields = None, pagination = 20):
	user = get_user_doc(user)

	room = frappe.get_doc('Chat Room', room)
	mess = frappe.get_all('Chat Message',
		filters = [
			('Chat Message', 'room', '=', room.name),
			('Chat Message', 'type', '=', room.type)
		],
		fields  = fields if fields else [
			'name', 'type',
			'room', 'content',
			'user', 'mentions', 'urls',
			'creation'
		]
	)

	return mess

@frappe.whitelist()
def get(name, rooms = None, fields = None):
	rooms, fields = safe_json_loads(rooms, fields)

	dmess = frappe.get_doc('Chat Message', name)
	data  = dict(
		name     = dmess.name,
		user     = dmess.user,
		room     = dmess.room,
		content  = dmess.content,
		urls     = dmess.urls,
		mentions = dmess.mentions,
		creation = dmess.creation,
		seen     = assign_if_empty(dmess._seen, [ ])
	)

	return data