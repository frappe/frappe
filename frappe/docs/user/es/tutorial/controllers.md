# Controladores (Controllers)

El siguiente paso va a ser agregar métodos y eventos a los modelos. En la aplicación, debemos asegurar que si una Library Transaction es creada, el Article que se solicita debe estar en disponibilidad y el miembro que lo solicita debe tener una membresía (membership) válida.

Para esto, podemos escribir una validación que se verifique justo en el momento que una Library Transaction es guardada. Para lograrlo, abre el archivo `library_management/doctype/library_transaction/library_transaction.py`.

Este archivo es el controlador para el objeto Library Transaction. En este archivo puedes escribir métodos para:

1. `before_insert`
1. `validate` (Antes de insertar o actualizar)
1. `on_update` (Despues de guardar)
1. `on_submit` (Cuando el documento es presentado como sometido o presentado)
1. `on_cancel`
1. `on_trash` (antes de ser eliminado)

Puedes escribir métodos para estos eventos y estos van a ser llamados por el framework automóticamente cuando el documento pase por uno de esos estados.

Aquí les dejo el controlador completo:

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
				msg = _("Article {0} {1} no ha sido marcado como retornado desde {2}")
				if last_transaction and last_transaction[0].transaction_type=="Issue":
					frappe.throw(msg.format(self.article, self.article_name,
						last_transaction[0].transaction_date))
			else:
				if not last_transaction or last_transaction[0].transaction_type!="Issue":
					frappe.throw(_("No puedes retornar un Article que no ha sido prestado."))

En este script:

1. Obtenemos la última transacción antes de la fecha de la transacción actual usando la funcion `frappe.get_list`
1. Si la última transacción es algo que no nos gusta, lanzamos una excepción usando `frappe.throw`
1. Usamos el método `_("texto")` para identificar las cadenas que pueden ser traducidas.

Verifica si sus validaciones funcionan creando nuevos registros.

<img class="screenshot" alt="Transaction" src="/docs/assets/img/lib_trans.png">

#### Depurando

Para depurar, siempre mantener abierta su consola JS. Verifíca rastros de Javascript y del Servidor.

Siempre verifica su terminal para las excepciones. Cualquier **500 Internal Server Errors** va a ser mostrado en la terminal en la que está corriendo el servidor.

{next}
