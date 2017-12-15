# Estableciendo límites para su sitio

La versión 7 de Frappé ha agregado soporte para la configuración de límites y restricciones para su site.
Estas restricciones están en el archivo `site_config.json` dentro de la carpeta del site.

	{
	 "db_name": "xxxxxxxxxx",
	 "db_password": "xxxxxxxxxxxx",
	 "limits": {
	  "emails": 1500,
	  "space": 0.157,
	  "expiry": "2016-07-25",
	  "users": 1
		}
	}

Puedes establecer un límite ejecutando:

	bench --site [nombre_sitio] set-limit [limite] [valor]

Puedes establecer varios límites al mismo tiempo ejecutando:

	bench --site [nombre_sitio] set-limits --limit [limite] [valor] --limit [limite-2] [valor-2]

Los límites que puedes configurar son:

- **users** - Limita el número de usuarios por site.
- **emails** - Limita el número de correos enviados por mes desde un site.
- **space** - Limita el máximo número de espacio en GB que el site puede usar.
- **email_group** - Limia el número máximo de miembros en un grupo de correos.
- **expiry** - Fecha de expiración para el site. (YYYY-MM-DD en de comillas)

Ejemplo:

	bench --site site1.local set-limit users 5

Puedes verificar el uso abriendo la página de "Usage Info" ubicada en el toolbar / AwesomeBar. Un límite solo va a mostrarse en la página si ha sido configurado.

<img class="screenshot" alt="Doctype Saved" src="/docs/assets/img/usage_info.png">
