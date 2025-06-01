import click

import nts


def execute():
	nts.delete_doc_if_exists("DocType", "Chat Message")
	nts.delete_doc_if_exists("DocType", "Chat Message Attachment")
	nts.delete_doc_if_exists("DocType", "Chat Profile")
	nts.delete_doc_if_exists("DocType", "Chat Token")
	nts.delete_doc_if_exists("DocType", "Chat Room User")
	nts.delete_doc_if_exists("DocType", "Chat Room")
	nts.delete_doc_if_exists("Module Def", "Chat")

	click.secho(
		"Chat Module is moved to a separate app and is removed from nts in version-13.\n"
		"Please install the app to continue using the chat feature: https://github.com/nts/chat",
		fg="yellow",
	)
