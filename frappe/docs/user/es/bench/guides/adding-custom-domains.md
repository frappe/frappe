# Agregando dominios personalizados a su Site

Puedes agregar **multiples dominios personalizados** para un site, ejecutando el comando:

	bench setup add-domain [dominio]

Al ejecutar el comando debes especificar para cual site quieres establecer el dominio personalizado.

También, puedes configurar el SSL para su dominio personalizado usando las opciones:

	--ssl-certificate [ruta-al-certificado]
	--ssl-certificate-key [ruta-a-la--clave-certificado]

Ejemplo:

	bench setup add-domain custom.erpnext.com --ssl-certificate /etc/letsencrypt/live/erpnext.cert --ssl-certificate-key /etc/letsencrypt/live/erpnext.key

La configuración el dominio es almacenada en las configuraciones del site en su archivo site_config.json

	 "domains": [
	  {
	   "ssl_certificate": "/etc/letsencrypt/live/erpnext.cert",
	   "domain": "erpnext.com",
	   "ssl_certificate_key": "/etc/letsencrypt/live/erpnext.key"
	  }
	 ],

**Luego debes regenerar las configuraciones de nginx ejecutando el comando `bench setup nginx` y reiniciando el servicio de nginx para que los cambios de los dominios tomen efecto**
