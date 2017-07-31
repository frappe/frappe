# Créer des utilisateurs et des enregistrements

Maintenant que nous avons définis des modèles, nous pouvons créér des enregistrements directement depuis l'interface. Vous
n'avez pas à créer des vues ! Les vues dans Frappé sont automatiquements créées à partir des propriétés de vos **DocTypes**.

### 4.1 Créer des utilisateurs

Afin de créer des enregistrements, nous avons tout d'abord besoin de créer un utilisateur. Rendez-vous sur:

> Setup > Users > User > New

Saisissez un nom, un prénom ainsi qu'un mot de passe à votre utilisateur pour le créer et donnez lui les rôles  `Librarian`
 et `Library Member`.

<img class="screenshot" alt="Add User Roles" src="/docs/assets/img/add_user_roles.png">

Maintenant déconnectez-vous puis connectez-vous avec l'utilisateur que vous venez de créer.

### 4.2 Créer des enregistrements

Vous allez désormais voir une icone pour notre module de gestion de librairie. Cliquez sur cette icone et vous apercevrez
la page du module:

<img class="screenshot" alt="Library Management Module" src="/docs/assets/img/lib_management_module.png">

Vous pouvez donc voir les **DocTypes** que nous avons créés pour l'application. Créons quelques enregistrements.

Définissons un nouvel Article:

<img class="screenshot" alt="New Article" src="/docs/assets/img/new_article_blank.png">

Le **DocType** que vous avons définis est transformé en formulaire. Les règles de validation seront appliquées selon nos
définitions. Remplissons le formulaire pour créer notre premier article.

<img class="screenshot" alt="New Article" src="/docs/assets/img/new_article.png">

Vous pouvez aussi ajouter une image.

<img class="screenshot" alt="Attach Image" src="/docs/assets/img/attach_image.gif">

Maintenant créons un nouveau membre.

<img class="screenshot" alt="New Library Member" src="/docs/assets/img/new_member.png">

Après cela, définissons un nouvel abonnement pour ce membre.

Ici, si vous vous souvenez, nous avons définis que les noms et prénoms doivent automatiquement être renseignés dès que nous
avons selectionné l'ID du membre.

<img class="screenshot" alt="New Library Membership" src="/docs/assets/img/new_lib_membership.png">

Comme vous pouvez le voir, la date est formattée en années-mois-jour qui est le format du système. Pour configurer / changer 
le format de la date et de l'heure, rendez-vous sur:

> Setup > Settings > System Settings

<img class="screenshot" alt="System Settings" src="/docs/assets/img/system_settings.png">

{suite}
