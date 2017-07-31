# Nommage et relation entre DocType

Définissons un nouveau **DocType**:

1. Library Member (First Name, Last Name, Email Address, Phone, Address)

<img class="screenshot" alt="Doctype Saved" src="/docs/assets/img/naming_doctype.png">


#### Le nommage des DocTypes

Les **DocTypes** peuvent être nommés de différentes facons:

1. Sur la base d'un champ
1. Sur la base d'une série
1. Par le controlleur (code)
1. Par la console

Cela peut être configuré par le champs **Autoname**. Pour le controleur, laissez vide.

> **Search Fields**: Un **DocType** peut être nommé sur la base d'une serie mais nous devons toujours pouvoir le chercher par un nom. 
Dans notre cas, l'arcicle peut etre cherché par un titre ou par l'auteur. Remplissons donc le champs **Search Fields**.

<img class="screenshot" alt="Autonaming and Search Field" src="/docs/assets/img/autoname_and_search_field.png">

#### Relation et champs select

Les clés étrangères sont, dans Frappé, traduits par un champs de type **Link**. Le **DocType** ciblé doit être mentionné
 dans le champs **Options**.

Dans notre exemple, pour le **doctype** `Library Transaction`, nous avons un lien vers `Library Member` et vers `Article`.

**Note:** Souvenez vous que les champs **Link** ne sont pas automatiquement enregistré comme clé étrangère afin d'éviter 
d'indexer la colonne. Cela pourrait ne pas être optimum, c'est pour cela que la validation de la clé étrangère est faite 
par le framework.

<img class="screenshot" alt="Link Field" src="/docs/assets/img/link_field.png">

Pour les champs **select**, comme mentionné plus tôt, ajoutez chacune des options dans le champs **Options**, chaque 
option sur une nouvelle ligne.

<img class="screenshot" alt="Select Field" src="/docs/assets/img/select_field.png">

faites de même pour les autres modèles.

#### Valeurs liées

Un modèle standard c'est lorsque vous selectionnez un ID, admettons **Library Member** dans **Library Membership**, alors, 
les noms et prénoms du membre doivent être copiés dans le champs adequat lors d'enregistrements dans `Library Membership Transaction`.

Pour cela, nous pouvons utiliser des champs en lecture seules et, dans les options, nous pouvons définir le nom du lien 
et le nom du champs de la propriété que nous voulons parcourir. Dans cet exemple, dans **Member First Name** nous pouvons 
définir `library_member.first_name`

<img class="screenshot" alt="Fetch values" src="/docs/assets/img/fetch.png">

### Completer les Modeles

De la même facon, vous pouvez compléter les autres modèles pour qu'au final le résultat soit:

#### Article

<img class="screenshot" alt="Article" src="/docs/assets/img/doctype_article.png">

#### Library Member

<img class="screenshot" alt="Library Member" src="/docs/assets/img/doctype_lib_member.png">

#### Library Membership

<img class="screenshot" alt="Library Membership" src="/docs/assets/img/doctype_lib_membership.png">

#### Library Transaction

<img class="screenshot" alt="Library Transaction" src="/docs/assets/img/doctype_lib_trans.png">

> Vérifiez que le modèles **Librarian** aient les permissions sur chaque **DocType**.

{next}
