# Controllers

Next step would be adding methods and event handlers to models. In your app, we sould like to ensure that if a Library Tranasction is made, the Artilce in question must be in stock and the member loaning the Article must have a valid membership.

For this, we can write a validation just before the Library Transaction object is saved. To do this, open the `library_management/doctype/library_transaction/library_transaction.py` template.

This file is the controller for the Library Transaction object. In this you can write methods for:

1. `before_insert`
1. `validate` (before inserting or updating)
1. `on_update` (after saving)
1. `on_submit` (when document is set as submitted)
1. `on_cancel`
1. `on_trash` (before it is about to be deleted)

You can write methods for these events and they will be called by the framework when the document is saved etc.

Here is the finished controller:

	from __future__ import unicode_literals
	import frappe
	from frappe import _
	from frappe.model.document import Document

	class LibraryTransaction(Document):
		def validate(self):
			last_transaction = frappe.get_list("Library Transaction",
				fields=["transaction_type", "transaction_date"],
				filters = {
					"article": self.article,
					"transaction_date": ("<=", self.transaction_date),
					"name": ("!=", self.name)
				})
			if self.transaction_type=="Issue":
				msg = _("Article {0} {1} has not been recorded as returned since {2}")
				if last_transaction and last_transaction[0].transaction_type=="Issue":
					frappe.throw(msg.format(self.article, self.article_name,
						last_transaction[0].transaction_date))
			else:
				if not last_transaction or last_transaction[0].transaction_type!="Issue":
					frappe.throw(_("Cannot return article not issued"))

In this script:

1. We get the last trasaction before the current transaction date using the query function `frappe.get_list`
1. If the last transaction is something we don't like we throw an exception using `frappe.throw`
1. We use `_("text")` method to identify translatable strings.

Check if your validations work by creating new records

<img class="screenshot" alt="Transaction" src="{{url_prefix}}/assets/img/lib_trans.png">

#### Debugging

To Debug, always keep your JS Console open. Lookout for both Javascript and server tracebacks.

Also check your terminal window for exceptions. Any **500 Internal Server Errors** will get printed in your terminal where on which your server is running.

{next}
