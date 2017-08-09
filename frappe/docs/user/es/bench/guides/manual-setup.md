# Manual Setup

Instalación Manual
--------------

Prerrequisitos,

* [Python 2.7](https://www.python.org/download/releases/2.7/)
* [MariaDB](https://mariadb.org/)
* [Redis](http://redis.io/topics/quickstart)
* [WKHTMLtoPDF con QT parcheado](http://wkhtmltopdf.org/downloads.html) (Requerido para la generación de pdf)

[Instalando los Prerrequisitos en OSX](https://github.com/frappe/bench/wiki/Installing-Bench-Pre-requisites-on-MacOSX)

Instalar el bench como usuario normal, **no root**

		git clone https://github.com/frappe/bench bench-repo
		sudo pip install -e bench-repo

Nota: Favor de no remover el directorio bench que el comando va a crear

Migrando desde una instalación existente
------------------------------------

Si deseas migrar desde ERPNext v3, sigue las siguientes instrucciones [aquí](https://github.com/frappe/bench/wiki/Migrating-from-ERPNext-version-3)

Si deseas migrar de una versión vieja del bench, sigue las instrucciones [aquí](https://github.com/frappe/bench/wiki/Migrating-from-old-bench)


Uso básico
===========

* Crea un nuevo bench

	El comando init va a crear un directorio conteniendo el framework Frappé instalado.
	Va a ser configurado para copias de seguridad periódicas y actualizaciones automáticas una vez por día.

		bench init frappe-bench && cd frappe-bench

* Agregar aplicaciones

	El comando get-app descarga e instala aplicaciones hechas en frappe. Ejemplos:

	- [erpnext](https://github.com/frappe/erpnext)
	- [erpnext_shopify](https://github.com/frappe/erpnext_shopify)
	- [paypal_integration](https://github.com/frappe/paypal_integration)

	bench get-app erpnext https://github.com/frappe/erpnext

* Agregar Site

	Las aplicaciones Frappé son montadas en los Sites y por tanto tendras que crear por lo menos un site.
	El comando new-site te permite crearlos.

		bench new-site site1.local

* Iniciar bench

	Para comenzar a utilizar el bench, usa el comando `bench start`

		bench start

	Para acceder a Frappé / ERPNext, abra su navegador favorito y escriba la ruta `localhost:8000`

	El usuario por defecto es "Administrator" y la contraseña es la que específicaste al momento de crear el nuevo site.


Configurando ERPNext
==================

Para instalar ERPNext, ejecuta:
```
bench install-app erpnext
```

Ahora puedes usar `bench start` o [configurar el bench para uso en producción](setup-production.html)
