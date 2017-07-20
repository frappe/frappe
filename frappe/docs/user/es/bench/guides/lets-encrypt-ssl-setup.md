# Uso de Let's Encrypt para configurar HTTPS

##Prerrequisitos

1. Necesitas tener una configuración Multitenant
2. Su sitio debería ser accesible a traves de un dominio válido
3. Necesitas permisos de administrados en el servidor

**Nota : Los certificados de Let's Encrypt expiran cada 3 meses**

## Usando el comando bench

Ejecutar:

    sudo -H bench setup lets-encrypt [site-name]

Van a aparecer varios prompts, responde a todo. Este comando también va a agregar una entrada a crontab del usuario que esta intentando renovar el certificado cada mes.

### Dominios personalizados

Puedes configurar Let's Encrypt para [dominios personalizados](adding-custom-domains.html). Solo usando la opción `--custom-domain`

    sudo -H bench setup lets-encrypt [site-name] --custom-domain [custom-domain]

### Renovar Certificados

Para la renovación manual de certificados puedes usar:

    sudo bench renew-lets-encrypt

<hr>

## Método Manual
### Descarga el script apropiado de Certbot-auto en el directorio /opt

    https://certbot.eff.org/

### Detener el servicio / proceso nginx

    $ sudo service nginx stop

### Ejecutar Certbot

    $ ./opt/certbot-auto certonly --standalone

Despues que letsencrypt se inicializa, vas a tener que llenar algunas informaciones. Los prompts pueden variar de si haz usado o no Let's Encrypt antes, pero vamos a guiarte en su primera vez.

En el prompt, ingresar la dirección de correo eléctronico que será usada para notificaciones y recuperación de claves perdidas:

![](https://assets.digitalocean.com/articles/letsencrypt/le-email.png)

Debes aceptar el acuerdo de subscripción de Let's Encrypt, selecciona Agree:

![](https://assets.digitalocean.com/articles/letsencrypt/le-agreement.png)

Luego ingresa el nombre de su dominio(s). Nota que si deseas un simple certificado para trabajar con
varios nombres de dominios (ejemplo: example.com y www.example.com), asegurate de incluirlos todos:

![](https://assets.digitalocean.com/articles/letsencrypt/le-domain.png)

### Archivos de certificados

Despues de obtener el certificado, va a tener los siguientes archivos PEM-encoded:

* **cert.pem**: El certificado de su dominio
* **chain.pem**: La cadena del certificado de Let's Encrypt
* **fullchain.pem**: cert.pem y chain.pem combinados
* **privkey.pem**: La clave privada de su certificado.

Estos certificados estan almacenados en el directorio `/etc/letsencrypt/live/example.com`

### Configurar los certificados para su site(s)

Vaya al archivo site_config.json del site donde tiene erpnext

    $ cd frappe-bench/sites/{{nombre_sitio}}

Agrega las siguientes lineas al archivo site_config.json

    "ssl_certificate": "/etc/letsencrypt/live/example.com/fullchain.pem",
    "ssl_certificate_key": "/etc/letsencrypt/live/example.com/privkey.pem"


Regenerar las configuraciones de nginx

    $ bench setup nginx

Reiniciar el servidor nginx

    $ sudo service nginx restart

---

### Renovació Automática (experimental)

Accede como root o como un usuario con privileges de administrador, ejecuta `crontab -e` y presiona enter:


    # renovar el certificado de letsencrypt todos los días primero de cada mes y recibe un email si el comando ha sido ejecutado
    MAILTO="mail@example.com"
    0 0 1-7 * * [ "$(date '+\%a')" = "Mon" ] && sudo service nginx stop && /opt/certbot-auto renew && sudo service nginx start
