# Form Client Scripting

## Codes des formulaires

Jusqu'a maintenant, nous avons développé un système basique qui fonctionne parfaitement sans avoir eu besoin d'écrire une
 seule ligne de code. Ajoutons donc quelques scripts pour rendre l'applications plus professionnelle et ajoutons des validations
 pour éviter que les utilisateurs n'enregistrent des données invalides.


### Les scripts coté client

Dans le **DocType** **Library Transaction**, nous n'avons qu'un seul champ `Member Name`. Nous n'avons pas fait 2 champs. 
Ca pourrait être bien d'avoir deux champs, mais juste pour l'exemple, considérons que nous avons à implémenter cela. Pour ce
faire, nous allons devoir écrire un gestionnaire d'évenements pour lorsque l'utilisateur sélectionne le champs `library_member` et accède aux données de l'utilisateur depuis le serveur en utilisant une API REST, remplisse les données dans le formaulaire.

Pour commencer ce script, dans le repertoire `library_management/doctype/library_transaction`, créez un nouveau fichier 
`library_transaction.js`. Ce fichier sera automatiquement executé lorsque le modèle `Library Transaction` est appelé par l'utilisateur. 
Donc, dans ce fichier nous pouvons lier des actions à des événemenents mais aussi écrire d'autres fonctions.

#### library_transaction.js

	frappe.ui.form.on("Library Transaction", "library_member",
		function(frm) {
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Library Member",
					name: frm.doc.library_member
				},
				callback: function (data) {
					frappe.model.set_value(frm.doctype,
						frm.docname, "member_name",
						data.message.first_name
						+ (data.message.last_name ?
							(" " + data.message.last_name) : ""))
				}
			})
		});

1. **frappe.ui.form.on(*doctype*, *fieldname*, *handler*)** est utilisé pour lier un évenement au gestionnaire d'évenements
 quand la propriété `library_member` est complétée.
1. Dans le gestionnaire, nous déclenchons un appel AJAX vers `frappe.client.get`. En réponse, nous avons l'ojet demandé sous forme d'une JSON. [En savoir plus sur l'API](/frappe/user/fr/guides/integration/rest_api).
1. En utilisant **frappe.model.set_value(*doctype*, *name*, *fieldname*, *value*)** nous définissons la valeur dans le formulaire.

**Note:** Pour vérifier que votre script fonctionne, n'oubliez pas de recharger votre page avant de tester. 
Les changements dans les scripts côté client ne sont pas automatiquement pris en compte quand vous êtes en mode développeur.

{next}
