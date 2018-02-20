# Setup Production

Puedes configurar el bench para producción configurando dos parametros, Supervisor y nginx. Si quieres volver a ponerlo en desarrollo debes ver [estos comandos](https://github.com/frappe/bench/wiki/Stopping-Production-and-starting-Development)

####Configuración para producción facíl
Estos pasos son automátizados si ejecutas `sudo bench setup production`


####Configuración manual para producción
Supervisor
----------
Supervisor se asegura de mantener el proceso que inició Frappé corriendo y lo reinicia en caso de cualquier inconveniente.
 Puedes generar la configuración necesaria para supervisor ejecutando el comando `bench setup supervisor`.
 La configuración va a estar disponible en la carpeta `config/supervisor.conf`. Luego puedes copiar/enlazar este archivo al directorio de configuración  
 de supervisor y reiniciar el servicio para que tome efecto de los cambios realizados.

Ejemplo,

```
bench setup supervisor
sudo ln -s `pwd`/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.conf
```

Nota: Para CentOS 7, la extensión debería ser `ini`, por lo que el comando sería
```
bench setup supervisor
sudo ln -s `pwd`/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.ini #para CentOS 7 solamente
```

El bench también necesita reiniciar el proceso manejado por supervisor cuando actualizar cualquier aplicación.
Para automatizarlo, vas a tener que agregar el usuario a sudoers ejecutando `sudo bench setup sudoers $(whoami)`.

Nginx
-----


Nginx es un servidor web y lo usamos para servir archivos estáticos y aponderar el resto de la
peticiones a frappe. Puedes generar las configuraciones necesarias para nginx usando el comando `bench setup nginx`.
La configuración va a estar almacenada en el archivo `config/nginx.conf`. Entonces puedes copiar/enlazar este archivo al directorio de
configuración de nginx y reiniar el servicio para poder ver si se han aplicado los cambios.

Ejemplo,

```
bench setup nginx
sudo ln -s `pwd`/config/nginx.conf /etc/nginx/conf.d/frappe-bench.conf
```

Nota: Cuando reinicias nginx despues de cualquier cambio en la configuración, podría fallar si tienes otra configuración con el bloque server para el puerto 80 (En la mayoría de veces la página princial de nginx). Vas a tener que deshabilitar esta configuración. Las rutas más probables donde podemos encontrarlo son `/etc/nginx/conf.d/default.conf` y
`/etc/nginx/conf.d/default`.
