# Iniciando o Bench

Agora podemos logar e verificar se tudo funcionou.

Para iniciar o servidor de desenvolvimento, digite `bench start`

	$ bench start
	13:58:51 web.1        | started with pid 22135
	13:58:51 worker.1     | started with pid 22136
	13:58:51 workerbeat.1 | started with pid 22137
	13:58:52 web.1        |  * Running on http://0.0.0.0:8000/
	13:58:52 web.1        |  * Restarting with reloader
	13:58:52 workerbeat.1 | [2014-09-17 13:58:52,343: INFO/MainProcess] beat: Starting...

Agora você pode abrir o seu navegador e ir para `http://localhost:8000`. Você deve ver esta página de login, se tudo correu bem:

<img class="screenshot" alt="Login Screen" src="/docs/assets/img/login.png">

Agora logue com :

Login ID: **Administrator**

Senha : **Use a senha que foi criada durante a instalação**

Quando voce logar, voce deverá ver o "Desk" da pagine home

<img class="screenshot" alt="Desk" src="/docs/assets/img/desk.png">

Como você pode ver, o básico do sistema Frappé vem com vários aplicativos pré-carregados como coisas a fazer, o Gerenciador de arquivos etc. Esses aplicativos podem ser integrados no fluxo de trabalho do app à medida que progredimos.

{next}
