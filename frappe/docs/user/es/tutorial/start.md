# Iniciando el Bench

Ahora podemos acceder y verificar que todo esta funcionando de forma correcta.

Para iniciar el servidor de desarrollo, ejecuta `bench start`.

	$ bench start
	13:58:51 web.1        | started with pid 22135
	13:58:51 worker.1     | started with pid 22136
	13:58:51 workerbeat.1 | started with pid 22137
	13:58:52 web.1        |  * Running on http://0.0.0.0:8000/
	13:58:52 web.1        |  * Restarting with reloader
	13:58:52 workerbeat.1 | [2014-09-17 13:58:52,343: INFO/MainProcess] beat: Starting...

Ahora abre tu navegador y ve a la dirección `http://localhost:8000`. Deberías ver la páagina de inicio de sesión si todo salió bien.:

<img class="screenshot" alt="Login Screen" src="/docs/assets/img/login.png">

Ahora accede con :

Login ID: **Administrator**

Password : **Usa la contraseña que creaste durante la instalación**

Cuando accedas, deberías poder ver la página de inicio (Desk).

<img class="screenshot" alt="Desk" src="/docs/assets/img/desk.png">

Como puedes ver, el sistema básico de Frappé viene con algunas aplicaciones preinstaladas como To Do, File Manager etc. Estas aplicaciones pueden integrarse en el flujo de trabajo de su aplicació a medida que avancemos.

{next}
