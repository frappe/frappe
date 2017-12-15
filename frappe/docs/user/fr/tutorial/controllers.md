# Les controleurs

La prochaine étape est d'ajouter quelques méthodes et événements à nos modèles. Dans l'application, nous devons nous 
assurer que si une opération est faite, l'article concerné doit être disponible en stock et que le membre qui souhaite
faire le prêt à un abonnement valide.

Pour cela, nous pouvons écrire une règle de validation au moment de la sauvegarde du prêt. Ouvrez le template `library_management/doctype/library_transaction/library_transaction.py`.

Ce fichier est le controleur qui gère les opérations de la librairie, vous pouvez y écrire des méthodes pour:

1. `before_insert`
1. `validate` (avant l'insertion ou la mise à jour)
1. `on_update` (après la sauvegarde)
1. `on_submit` (quand le document est soumis)
1. `on_cancel`
1. `on_trash` (avant qu'il ne soit sur le point d'être supprimé)

Vous pouvez écrire des méthodes pour ces événements et elles seront appelées par le framework au bon moment.

Voici pour finir le controleur:

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

Dans ce script:

1. Nous récuperons la dernière opération, avant la date de l'opération en cours en utilisant la méthode `frappe.get_list`
1. Si la dernière opération est quelque chose qui n'est pas attendu, alors nous levons une exception en utilisant `frappe.throw`
1. Nous utilisons la méthode  `_("text")` pour identifier une chaine traduisible.

Vérifiez vos validations en créant de nouveaux enregistrements.

<img class="screenshot" alt="Transaction" src="/docs/assets/img/lib_trans.png">

#### Debogage

Pour debugger, gardez toujours votre console JS ouverte, vérifier les erreurs à la fois de Javascript mais aussi du serveur.

Regardez aussi votre fenêtre de terminal pour les exceptions. Chaque **erreur 500 pour des problèmes internes** seront affichées dans le terminal du serveur en cours d'utilisation.

{next}
