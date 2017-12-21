# imports - third-party imports
from bs4 import BeautifulSoup as Soup

# imports - module imports
from   frappe.model.document import Document
from   frappe import _, _dict
import frappe

# imports - frappe module imports
from frappe.chat.util import (
	get_user_doc,
	check_url,
	dictify,
	user_exist
)

session = frappe.session

# TODO
# [ ] Link Timestamp to Chat Room

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
	soup     = Soup(content, 'html.parser')
	anchors  = soup.find_all('a')
	mentions = [ ]

	for anchor in anchors:
		text = anchor.text
	
		if text.startswith('@'):
			username = text[1:]

			if user_exist(user):
				mentions.append(user)

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

def get_new_chat_message_doc(user, room, content, link = True):
	user = get_user_doc(user)
	room = frappe.get_doc('Chat Room', room)

	meta = get_message_meta(content)
	mess = frappe.new_doc('Chat Message')
	mess.type     = room.type
	mess.room 	  = room.name
	mess.content  = content
	mess.user	  = user.name

	mess.mentions = meta.mentions
	mess.urls     = ','.join(meta.urls)
	mess.save()

	if link:
		room.update(dict(
			last_message = mess.name
		))
		room.save()

	return mess

def get_new_chat_message(user, room, content):
	mess = get_new_chat_message_doc(user, room, content)

	resp = dict(
		name     = mess.name,
		user     = mess.user,
		room     = mess.room,
		content  = mess.content,
		urls     = mess.urls,
		mentions = mess.mentions,
		creation = mess.creation,
		seen     = mess._seen,
	)

	return resp

@frappe.whitelist()
def send(user, room, content):
	mess = get_new_chat_message(user, room, content)
	
	frappe.publish_realtime('frappe.chat.message:create', mess, room = room,
		after_commit = True)

# This is fine for now. If you're "ReST"-ing it,
# make sure you don't let the user see them.
# Come again, Why are we even passing user?
def get_messages(room, user = None, fields = None, pagination = 20):
	user = get_user_doc(user)

	room = frappe.get_doc('Chat Room', room)
	mess = frappe.get_list('Chat Message',
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