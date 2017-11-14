# imports - third-party imports
from bs4 import BeautifulSoup as Soup

# imports - module imports
from   frappe.model.document import Document
from   frappe.exceptions import DoesNotExistError
from   frappe import _, _dict
import frappe

# imports - frappe module imports
from frappe.chat.util import (
	get_user_doc,
	check_url,
	user_exist
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
	meta.links	  = get_message_urls(content)
	meta.mentions = get_message_mentions(content)
	
	return meta

def get_new_chat_message_doc(user, room, content):
	user = get_user_doc(user)
	room = frappe.get_doc('Chat Room', room)

	meta = get_message_meta(content)
	mess = frappe.new_doc('Chat Message')
	mess.user	 = room.user
	mess.room 	 = room.name
	mess.content = content

	return mess

@frappe.whitelist()
def send(user, room, content):
	mess = get_new_chat_message_doc(user, room, content)

@frappe.whitelist()
def send_attachment(user, room, unknown_field):
	pass
	
@frappe.whitelist()
def delete():
	pass