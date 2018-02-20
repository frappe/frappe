# Qu'est ce qu'une application ?

Dans Frappé, une application est juste une application Python standard. Vous pouvez structurer une application Frappé de 
la même facon que vous structurez une application Python standard. Pour le déploiement, Frappé utilise Setuptools donc 
vous pouvez facilement déployer votre application sur n'importe quelle machine.

Frappé fournit une interface WSGI et pendant vos développements vous pouvez utiliser le serveur Werkzeug embarqué. Pour le
déploiement en production, nous recommandons d'utiliser nginx et gunicorn.

Frappé, c'est aussi une une architecture multi-tenant ce qui signifie que vous pouvez lancer plusieurs sites sur une même
configuration, chaque site utilisant ses propres applications et utilisateurs. La base de données de chaque site est indépendante.

{next}
