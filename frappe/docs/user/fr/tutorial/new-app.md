# Créer une nouvelle application

Une fois que Bench est installé, vous apercevrez deux répertoires, `apps` and `sites`. Toutes les applications seront 
installées dans `apps`.

Pour créer une nouvelle application, allez dans votre répertoire et lancer la commande, `bench new-app {app_name}` et 
remplissez les informations à propos de votre application. Cela va créer un template d'application pour vous.

	$ bench new-app library_management
	App Title (defaut: Lib Mgt): Library Management
	App Description:  App for managing Articles, Members, Memberships and Transactions for Libraries
	App Publisher: Frappé
	App Email: info@frappe.io
	App Icon (default 'octicon octicon-file-directory'): octicon octicon-book
	App Color (default 'grey'): #589494
	App License (default 'MIT'): GNU General Public License

### Structure d'une application

L'application sera créée dans un répertoire appelé `library_management` et aura la structure suivante:

	.
	├── MANIFEST.in
	├── README.md
	├── library_management
	│   ├── __init__.py
	│   ├── config
	│   │   ├── __init__.py
	│   │   └── desktop.py
	│   ├── hooks.py
	│   ├── library_management
	│   │   └── __init__.py
	│   ├── modules.txt
	│   ├── patches.txt
	│   └── templates
	│       ├── __init__.py
	│       ├── generators
	│       │   └── __init__.py
	│       ├── pages
	│       │   └── __init__.py
	│       └── statics
	├── license.txt
	├── requirements.txt
	└── setup.py

1. `config` contient les configurations de l'application 
1. `desktop.py` est l'endroit ou les icones peuvent être ajoutées au bureau
1. `hooks.py` contient les définitions de la facon dont l'intégration avec l'environnement et les autres applications est faite.
1. `library_management` (interne) est un **module** bootstrappé. Dans Frappé, un **module** est l'endroit où sont les controlleurs et les modeles.
1. `modules.txt` contient la liste des **modules** dans l'application. Quand vous créez un nouveau module, c'est obligatoire de l'ajouter dans ce fichier.
1. `patches.txt` contient les patchs de migration. Ce sont des références Python utilisant la notation par point.
1. `templates` est le repertoire qui contient les templates des vues. Les templates pour **Login** et autres pages par défaut sont déjà contenus dans Frappé.
1. `generators` est l'endroit où sont stockés les templates des modèles. Chaque instance du modèle a une route web comme par exemple les **articles de blog** ou chaque article a une adresse unique. Dans Frappé, Jinj2 est utilisé pour les templates.
1. `pages` contient les routes uniques pour les templates. Par exemple "/blog" ou "/article"

{next}
