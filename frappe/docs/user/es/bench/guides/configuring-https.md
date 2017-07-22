# Configurando HTTPS

### Obtener los archivos requeridos


Puede obtener un certificado SSL de una entidad emisora ​​de certificados de confianza o generar su propio certificado.
Para los certificados auto-firmados, el navegador mostrará una advertencia de que el certificado no es de confianza. [Aquí hay un tutorial para usar Let's Encrypt para obtener un certificado SSL gratuito](lets-encrypt-ssl-setup.html)

Los archivos obligatorios son:

* Certificado (Normalmente con extensión .crt)
* Clave privada descifrada

Si tienes varios certificados (primario e intermedios), tendrás que unirlos. Por ejemplo,

	cat su_certificado.crt CA.crt >> certificate_bundle.crt

También asegúrese que su clave privada no sea legible. Generalmente, solo puede ser leída por root ya que normalmente es el dueño de la misma.

	chown root private.key
	chmod 600 private.key

### Mueva los dos archivos a una ruta confiable

	mkdir /etc/nginx/conf.d/ssl
	mv private.key /etc/nginx/conf.d/ssl/private.key
	mv certificate_bundle.crt /etc/nginx/conf.d/ssl/certificate_bundle.crt

### Establecer configuraciones de nginx

Configura las rutas al certificado y la clave privada de su site.

	bench set-ssl-certificate site1.local /etc/nginx/conf.d/ssl/certificate_bundle.crt
	bench set-ssl-key site1.local /etc/nginx/conf.d/ssl/private.key

### Generar la configuració de nginx

	bench setup nginx

### Reiniciar nginx

	sudo service nginx reload

o

	systemctl reload nginx # for CentOS 7

Ahora que tienes configurado el SSL, todo el tráfico HTTP va a ser redireccionado a HTTPS
