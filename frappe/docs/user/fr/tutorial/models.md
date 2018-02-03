# Définir des modèles

La prochaine étape est de définir les modèles que nous avons présenté en introduction. Dans **Frappé**, les modèles sont appelés
des **DocTypes**. Vous pouvez définir de nouveaux **DocTypes** depuis l'interface. Les **DocTypes** sont faits de **DocField** 
et de permissions appelées **DocPerms**.

Quand un DocType est sauvegardé, une nouvelle table est créée dans la base de données. Cette table est nommée `tab[doctype]`.

Quand vous créez un **DocType**, un nouveau repertoire est créé dans le **Module**, un fichier JSON définissant le modèles
ainsin qu'un template de controleur sont automatiquement créés.
Qaund vous mettez à jour un **DocType**, le modèle JSON est mis à jour et lorsque la commande `bench migrate` est exécutée, 
c'est synchronisé avec la base de données. Cela facilite a mise à jour et la migrations des schemas.

### Le mode développeur

Pour créer des modèles, vous devez définir la valeur de `developer_mode` à 1 dans le fichier `site_config.json` situé dans 
le repertoire /sites/library et executer la commande `bench clear-cache` ou utiliser l'interface et cliquer sur "Recharger" 
pour appliquer les changements. Vous devriez maintenant voir l'application "Developer" sur le bureau.

	{
	 "db_name": "bcad64afbf",
	 "db_password": "v3qHDeVKvWVi7s97",
	 "developer_mode": 1
	}

{next}
