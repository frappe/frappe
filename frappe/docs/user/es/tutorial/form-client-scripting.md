# Form Client Scripting

## Añadir Scripts a nuestros formularios

Ya que tenemos creado el sistema básico que funciona sin problemas sin escribir una linea de código. Vamos a escribir algunos scripts
para hablar la aplicación más interactiva y agregar validaciones para que el usuario no pueda introducir información erronea.

### Scripts del lado del Cliente

En el DocType **Library Transaction**, solo tenemos campo para el Nombre del miembro. No hemos creado dos campos. Esto podría ser dos campos (y probablemente debería), pero para los motivos del ejemplo, vamos a considerar que tenemos que implementarlo así. Para hacerlo vamos a tener que escribir un manejador de eventos para el evento que ocurre cuando el usuario selecciona el campo `library_member` y luego accede a la información del miembro desde el servidor usando el REST API y cambia los valores en el formulario.

Para empezar el script, en el directorio `library_management/doctype/library_transaction`, crea un nuevo archivo `library_transaction.js`.
Este archivo va a ser ejecutado automáticamente cuando la primer  Library Transaction es abierta por el usuario. En este archivo, podemos establecer eventos y escribir otras funciones.

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

1. **frappe.ui.form.on(*doctype*, *fieldname*, *handler*)** es usada para establecer un manejador de eventos cuando la propiedad library_member es seleccionada.
1. En el manejador, vamos a disparar una llamada AJAX a `frappe.client.get`. En respuesta obtenemos el objeto consultado en formato JSON. [Aprende más acerca del API](/frappe/user/en/guides/integration/rest_api).
1. Usando **frappe.model.set_value(*doctype*, *name*, *fieldname*, *value*)** cambiamos el valor en el formulario.

**Nota:**  Para verificar si su script funciona, recuerda Recargar/Reload la página antes de probar el script. Los cambios realizados a los script del lado del Cliente no son automáticamente cargados nuevamente cuando estas en modo desarrollador.

{next}
