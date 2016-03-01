# Tutoriel Frappe

Dans ce guide nous allons vous montrer comment créer une application de A à Z en utilisant **Frappe**. Avec un 
exemple de gestion d'une librairie, nous allons aborder les sujets suivants:

1. Installation
1. Créer une nouvelle application
1. Créer des modèles
1. Créer des utilisateurs et des enregristrements
1. Créer des contrôleurs
1. Créer des vues web
1. Configurer des Hooks et des tâches

## A qui s'adresse ce tutoriel ?

Ce guide est à destination des développeurs familiers avec la création d'applications web. Le framework Frappe est développé
avec Python, utilise le système de base de données MariaDB et database and HTML/CSS/Javascript pour le rendu des pages. 
Il est donc necessaire d'être familier avec ces technologies. Si vous n'avez jamais utilisé Python auparavant, vous devriez
suivre un tutoriel rapide avant de suivre ce guide.

Frappe utilise le système de gestion de version git sur Github. Il est donc imporant que vous connaissiez les basiques de
l'utilisation de git et que vous ayez un compte sur Github pour gérer vos applications.

## Exemple

Dans ce guide, nous allons développer une simple application de **gestion de librairie**. Dans cette applications nous aurons
les modèles suivants:

1. Article (un livre ou tout autre produit qui peut être emprunté)
1. Library Member (membre de la librairie)
1. Library Transaction (prêt ou retour d'un article)
1. Library Membership (Periode pendant laquelle un membre peut emprunter)
1. Library Management Setting (configuration générale)

L'interace utilisateur (UI) pour le libraire sera **Frappe Desk**, un système de rendu d'interface où les formulaires sont
automatiquement générés depuis les modèles en appliquant rôles et permissions.

Nous allons aussi créer des vues pour la lirairie afin que les utilisateurs puissent parcourir les articles depuis un site
internet.

{index}
