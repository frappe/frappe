import frappe
import imaplib
import hashlib
import re
import email, email.utils,email.header
from email.header import decode_header
from frappe.email.receive import get_unique_id

def execute():
	frappe.reload_doctype("Communication")
	frappe.reload_doctype("Unhandled Emails")
	for email_account in frappe.get_list("Email Account", filters={"awaiting_password": 0}):
		email_acc = frappe.get_doc("Email Account", email_account)
		try:
			email_server = email_acc.get_server(in_receive=True)
			email_server.imap.select("Inbox")
			#messages =email_server.imap.uid('fetch', "1:*", '(BODY.PEEK[HEADER.FIELDS (FROM TO ENVELOPE-TO DATE RECEIVED)])')
			messages = email_server.imap.uid('fetch', "1:*",'(BODY.PEEK[HEADER])')
			comms = frappe.db.sql("""select uid,name from `tabCommunication`
					where email_account=%(email_account)s""",{"email_account":email_account.name},as_dict=1 )
			unhandled = frappe.db.sql("""select uid,name from `tabUnhandled Emails`
					where email_account=%(email_account)s""",{"email_account":email_account.name},as_dict=1 )
			count =0;
			for i, item in enumerate(messages[1]):
				if isinstance(item, tuple):

					# check for uid appended to the end
					uid = re.search(r'UID [0-9]*', messages[1][i + 1], re.U | re.I)
					if uid:
						uid = uid.group()[4:]
					else:
						uid = ""

					# check for uid at start
					if not uid:
						# for m in item:
						uid = re.search(r'UID [0-9]*', messages[1][i][0], re.U | re.I)
						if uid:
							uid = uid.group()[4:]
						else:
							uid = ""
							continue
					mail = email.message_from_string(item[1])
					unique_id = get_unique_id(mail)

					#unique_id = hashlib.md5((mail.get("X-Original-From") or mail["From"])+(mail.get("To") or mail.get("Envelope-to"))+(mail.get("Received") or mail["Date"])).hexdigest()
					found =False
					for comm in comms:
						if comm.uid == uid:
							found =True
							frappe.db.sql("""update `tabCommunication`
	                                           set unique_id = %(unique_id)s
	                                       where  name = %(name)s
	                                       """, {"unique_id": unique_id,
					                            "name":comm.name})

					if not found:
						for comm in unhandled:
							if comm.uid == uid:
								found = True
								frappe.db.sql("""update `tabUnhandled Emails`
	                                                   set unique_id = %(unique_id)s
	                                               where  name = %(name)s
	                                               """, {"unique_id": unique_id,
		                                                 "name": comm.name})
					if found:
						count += 1

					#frappe.db.sql("""update `tabCommunication`
                    #                    set unique_id = %(unique_id)s
                    #                where  email_account= %(email_account)s and uid = %(uid)s
                    #                """, {"unique_id": h,
                    #                      "email_account":email_account.name,
                    #                      "uid": uid})
			print email_account.name,count
		except Exception, e:
			print e
		finally:
			try:
				email_server.imap.logout()
			except:
				pass
