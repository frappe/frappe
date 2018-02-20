# Configurer le site

Créons un site et appelons le `library`.

*Remarque: Avant de créer un nouveau site, vous devez activer le moteur de stockage Barracuda sur votre installation MariaDB.*
*Copiez les paramètres de base de données ERPNext par défaut suivants dans votre fichier `my.cnf`.*

    [mysqld]
    innodb-file-format=barracuda
    innodb-file-per-table=1
    innodb-large-prefix=1
    character-set-client-handshake = FALSE
    character-set-server = utf8mb4
    collation-server = utf8mb4_unicode_ci

    [mysql]
    default-character-set = utf8mb4


Vous pouvez installer un nouveau site avec la commande `bench new-site library`

Cette commande va créer une nouvelle base de données, un repertoire et installer `frappe` (qui est aussi une application!) 
dans le nouveau site. L'application `frappe` a deux modules par défaut, **Core** et **Website**. Le module **Core**
contient les modèles basiques pour l'application. En effet, Frappé contient des modèles par défaut qui sont appelés **DocTypes**
mais nous en reparlerons plus tard.

	$ bench new-site library
	MySQL root password:
	Installing frappe...
	Updating frappe                     : [========================================]
	Updating country info               : [========================================]
	Set Administrator password:
	Re-enter Administrator password:
	Installing fixtures...
	*** Scheduler is disabled ***

### Structure du site

Un nouveau repertoires appelé `library` sera créé dans le repertoire `sites`. Voici la structure standard pour un site.

	.
	├── locks
	├── private
	│   └── backups
	├── public
	│   └── files
	└── site_config.json

1. `public/files` contient les fichiers uploadés.
1. `private/backups` contient les backups.
1. `site_config.json` contient la configuration du site.

### COnfiguration par défaut

Dans le cas où vous avez plusieurs sites, utilisez la commande `bench use [site_name]` pour définir le site par défaut.

Exemple:

	$ bench use library

### Installer une application

Maintenant installons notre application `library_management` dans notre site `library`

1. Installer library_management avec la commande: `bench --site [site_name] install-app [app_name]`

Exemple:

	$ bench --site library install-app library_management

{next}
