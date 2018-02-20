# Setup Multitenancy

Asumiento que tiene su primer site corriendo y ha realizado los
 [pasos para producción](setup-production.html), esta sección explica como montar su segundo site (y más).
 Su primer site se configuró como el site por defecto de forma automática. Puedes cambiarlo ejecutando el comando,

	bench use nombre_site




Multitenancy basada en puertos
-----------------------

Puedes crear un nuevo site y ponerlo a escuchar por otro puerto (mientras que el primero corre en el puerto 80)

* Desactivar el multitenancy basada en DNS (una vez)

	`bench config dns_multitenant off`

* Crea un nuevo site

	`bench new-site site2name`

* Configura el puerto

	`bench set-nginx-port site2name 82`

* Regenera las configuraciones de nginx

	`bench setup nginx`

* Recarga el servicio de nginx

	`sudo service nginx reload`


Multitenancy basada en DNS
----------------------

Puedes nombrar sus sites como los los nombre de dominio que van a rederigirse a ellos. Así, todos los sites agregados al bench van a correr en el mismo puerto y van a ser automáticamente seleccionados basados en el nombre del host.

Para convertir un site nuevo dentro de la multitenancy basada en DNS, realiza los siguientes pasos.

* Desactivar el multitenancy basada en DNS (una vez)

	`bench config dns_multitenant on`

* Crea un nuevo site

	`bench new-site site2name`

* Regenera las configuraciones de nginx

	`bench setup nginx`

* Recarga el servicio de nginx

	`sudo service nginx reload`
