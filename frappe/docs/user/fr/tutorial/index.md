# Tutoriel Frappé

Dans ce guide nous allons vous montrer comment créer une application de A à Z en utilisant **Frappé**. Avec un 
exemple de gestion de bibliothèque, nous allons aborder les sujets suivants:

1. Installation
1. Créer une nouvelle application
1. Créer des modèles
1. Créer des utilisateurs et des enregristrements
1. Créer des contrôleurs
1. Créer des vues web
1. Configurer des Hooks et des tâches

## A qui s'adresse ce tutoriel ?

Ce guide est à destination des développeurs familiers avec la création d'applications web. Le framework Frappé est développé
avec Python, utilise le système de base de données MariaDB et HTML/CSS/Javascript pour le rendu des pages. 
Il est donc nécessaire d'être familier avec ces technologies. Si vous n'avez jamais utilisé Python auparavant, vous devriez
suivre un tutoriel rapide avant de suivre ce guide.

Frappé utilise le système de gestion de version git sur Github. Il est donc important que vous connaissiez les bases de
l'utilisation de git et que vous ayez un compte sur Github pour gérer vos applications.

## Exemple

Dans ce guide, nous allons développer une application simple de **gestion de bibliothèque**. Dans cette applications nous aurons
les modèles suivants:

1. Article (un livre ou tout autre objet qui peut être emprunté)
1. Library Member (membre de la bibliothèque)
1. Library Transaction (prêt ou retour d'un article)
1. Library Membership (période pendant laquelle un membre peut emprunter)
1. Library Management Setting (configuration générale)

L'interface utilisateur (UI) pour le bibliothécaire sera **Frappé Desk**, un système de rendu d'interface où les formulaires sont
automatiquement générés depuis les modèles en appliquant rôles et permissions.

Nous allons aussi créer des vues pour la bibliothèque afin que les utilisateurs puissent parcourir la liste des livres depuis un site internet.

{next}
