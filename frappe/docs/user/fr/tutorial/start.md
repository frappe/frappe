# Demarrer avec Bench

Maintenant, nous pouvons nous connecter et vérifier que tout fonctionne normalement.

Pour démarrer le serveur de développement, lancez la commande `bench start`

	$ bench start
	13:58:51 web.1        | started with pid 22135
	13:58:51 worker.1     | started with pid 22136
	13:58:51 workerbeat.1 | started with pid 22137
	13:58:52 web.1        |  * Running on http://0.0.0.0:8000/
	13:58:52 web.1        |  * Restarting with reloader
	13:58:52 workerbeat.1 | [2014-09-17 13:58:52,343: INFO/MainProcess] beat: Starting...

Vous pouvez maintenant ouvrir votre navigateur et vous rendre sur `http://localhost:8000`. Si tout se passe bien vous devriez voir:

<img class="screenshot" alt="Login Screen" src="/docs/assets/img/login.png">

Maintenant, connectez vous avec les identifiants suivants: 

Login ID: **Administrator**

Mot de passe: **Le mot de passe que vous avez définis pendant l'installation**

Une fois connecté, vous devriez voir le `Desk`, c'est à dire la page d'accueil

<img class="screenshot" alt="Desk" src="/docs/assets/img/desk.png">

Comme vous pouvez le voir, Frappé fournit quelques applications comme un To Do, un gestionnaire de fichiers etc. Ces applications
peuvent être intégrées par la suite.

{next}
