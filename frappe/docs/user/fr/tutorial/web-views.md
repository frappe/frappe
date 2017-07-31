# Les vues web

Frappé a deux principaux environnements, le **bureau** et **le web**. Le **bureau** est un environnement riche AJAX alors
que **le web** est une collection plus traditionnelle de fichiers HTML pour la consultation publique. Les vues web peuvent
aussi être générées pour créer des vues plus controllées pour les utilisateurs qui peuvent se connecter mais qui n'ont pas
accès au desk.

Dans Frappé, les vues sont gérées par des templates et sont tout naturellement placés dans le repertoire `templates`. Il 
y a 2 principaux types de templates.

1. Pages: Ce sont des templates Jinja ou une vue unique existe pour une route (exemple:`/blog`).
2. Générateurs: Ce sont des templates ou chaque instance représente un **DocType** réprésenté par une url unique. (exemple:`/blog/a-blog`, `blog/b-blog` etc.)
3. Les listes et les vues: Ce sont des listes standards et des vues avec l'url `[doctype]/[name]` et sont affichées en fonction des permissions.

### Les vues web standards

> Cette fonctionnalité est encore en développement.

Jettons un oeil aux vues standards:

Si vous êtes connecté avec votre utilisateur de test, rendez-vous sur`/article` et vous devriez voir la liste des articles:

<img class="screenshot" alt="web list" src="/docs/assets/img/web-list.png">

Cliquez sur un article et vous devriez voir une vue par défaut.

<img class="screenshot" alt="web view" src="/docs/assets/img/web-view.png">

Maintenant, si vous voulez une meilleur liste pour vos articles, créez un fichier appelé `row_template.html` dans le
repertoire `library_management/templates/includes/list/`. Voici un exemple du contenu de ce fichier:

	{% raw %}<div class="row">
		<div class="col-sm-4">
			<a href="/Article/{{ doc.name }}">
				<img src="{{ doc.image }}"
					class="img-responsive" style="max-height: 200px">
			</a>
		</div>
		<div class="col-sm-4">
			<a href="/Article/{{ doc.name }}"><h4>{{ doc.article_name }}</h4></a>
			<p>{{ doc.author }}</p>
			<p>{{ (doc.description[:200] + "...")
				if doc.description|length > 200 else doc.description }}</p>
			<p class="text-muted">Publisher: {{ doc.publisher }}</p>
		</div>
	</div>{% endraw %}


Ici, vous aurez toutes les propriétés d'un article dans l'object `doc`.

La mise à jour de la liste ressemble à ca !

<img class="screenshot" alt="new web list" src="/docs/assets/img/web-list-new.png">

#### La page d'accueil

Frappé permet l'inscription et inclut les inscriptions via Google, Facebook et Github. Quand un utilisateur s'inscrit via
le web, il n'a pas accès à l'interface du desk par defaut.

> Pour autoriser les utilisateurs à accéder au `Desk`, ouvrez la configuration de l'utilisateur (Setup > User) et définissez
 le type d'utilisatuer à "System User".

Pour les utilisateurs qui n'ont pas accès au `Desk`, nous pouvons définir une page d'accueil ou ils peuvent se connecter via
`hooks.py` le tout en respectant les rôles.

Quand un membre de la librairie se connecte, il doit être redirigé vers la page `article` donc ouvrez le fichier `library_management/hooks.py` et ajoutez:

	role_home_page = {
		"Library Member": "article"
	}

{next}
