# DocType

Après avoir créé les roles, créons des **DocTypes**

Pour créer un nouveau **DocType**, rendez-vous sur:

> Developer > Documents > Doctype > New

<img class="screenshot" alt="New Doctype" src="/docs/assets/img/doctype_new.png">

Dans un premier temps, saisissez le module, dans notre cas, **Library Managment**

#### Ajouter des champs

Dans le tableau des champs, vous pouvez ajouter des champs (propriétés) du **DocType** (Article).

Les champs sont bien plus que des colonnes d'une base de données, ils peuvent être:

1. Des colonnes d'une base de données
1. Des aides pour la mise en page (section / saut de lignes)
1. Des tableaux enfants (Champs de type tableau)
1. HTML
1. Des actions (button)
1. Des pièces jointes ou des images

Ajoutons des champs pour l'article.

<img class="screenshot" alt="Adding Fields" src="/docs/assets/img/doctype_adding_field.png">

Quand vous ajoutez des champs, vous devez entrer le **Type**. Le **Label** est optionnel pour les retours de sections et de colonnes. 
Le **Name** (`fieldname`) ets le nom de la colonne dans la base de données et aussi la propriété du controleur. Les définitions
doivent être *code friendly*, (par exemple insérer des underscores (_) à la place de espaces. Si vous laissez le champs `fieldname`
vide, il sera automatiquement complété à la sauvegarde.

Vous pouvez aussi définir d'autres propriétés comme par exemple prciser que le champs est requis ou en lecture seule etc.

Nous pouvons ajouter les champs suivants:

1. Article Name (Data)
2. Author (Data)
3. Description
4. ISBN
5. Status (Select): Pour les champs de type select, vous devez compléter les options. entrer **Issued** et **Available** 
sur chacune des lignes comme ci-dessous
6. Publisher (Data)
7. Language (Data)
8. Image (Attach Image)


#### Ajouter des permissins

Après avoir ajouté les champs, validez et ajoutez un nouveau rôle dans la section des règles de permissions. Pour le moment
ajoutons les droits le lecture, écriture, création et suppression au modèle **Librarian**. Frappé à une gestion fine des 
permissions sur les modèles. Vous pouvez aussi changer les permissions plus tard en utilisant le gestionnaire de permissions
dans la configuration.

<img class="screenshot" alt="Adding Permissions" src="/docs/assets/img/doctype_adding_permission.png">

#### Sauvegarde

Cliquez sur le bouton **Save**. Quand le bouton est cliqué, une popup vous demandera le nom. Donnez le nom **Article** et 
sauvegardez le **DocType**.

Maintenant, connectez vous à MySQL et vérifiez la base de données créée:

	$ bench mysql
	Welcome to the MariaDB monitor.  Commands end with ; or \g.
	Your MariaDB connection id is 3931
	Server version: 5.5.36-MariaDB-log Homebrew

	Copyright (c) 2000, 2014, Oracle, Monty Program Ab and others.

	Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

	MariaDB [library]> DESC tabArticle;
	+--------------+--------------+------+-----+---------+-------+
	| Field        | Type         | Null | Key | Default | Extra |
	+--------------+--------------+------+-----+---------+-------+
	| name         | varchar(255) | NO   | PRI | NULL    |       |
	| creation     | datetime(6)  | YES  |     | NULL    |       |
	| modified     | datetime(6)  | YES  |     | NULL    |       |
	| modified_by  | varchar(40)  | YES  |     | NULL    |       |
	| owner        | varchar(60)  | YES  |     | NULL    |       |
	| docstatus    | int(1)       | YES  |     | 0       |       |
	| parent       | varchar(255) | YES  | MUL | NULL    |       |
	| parentfield  | varchar(255) | YES  |     | NULL    |       |
	| parenttype   | varchar(255) | YES  |     | NULL    |       |
	| idx          | int(8)       | YES  |     | NULL    |       |
	| article_name | varchar(255) | YES  |     | NULL    |       |
	| status       | varchar(255) | YES  |     | NULL    |       |
	| description  | text         | YES  |     | NULL    |       |
	| image        | varchar(255) | YES  |     | NULL    |       |
	| publisher    | varchar(255) | YES  |     | NULL    |       |
	| isbn         | varchar(255) | YES  |     | NULL    |       |
	| language     | varchar(255) | YES  |     | NULL    |       |
	| author       | varchar(255) | YES  |     | NULL    |       |
	+--------------+--------------+------+-----+---------+-------+
	18 rows in set (0.00 sec)


Comme vous pouvez le voir, en plus de nos **DocFields**, d'autres colonnes ont été ajoutées dans notre table. Notez les 
changement, la clé primaire sur, `name`, `owner`(l'utilisateur quia créer l'enregistrement), `creation` et `modified` (des timestamps pour enregistrer les dates de creation et de modification).

{next}

