# Qué es una aplicación

Una aplicación en Frappé es una aplicación estandar en Python. Puedes estructurar una aplicación hecha en Frappé de la misma forma que estructuras una aplicación en Python.
Para implementación, Frappé usa los  Python Setuptools, lo que nos permite facilmente instalar la aplicación en cualquier computadora.

El Framework Frappé provee una interfaz WSGI y para el desarrollo puedes usar el servidor interno de frappe llamado Werkzeug. Para implementación en producción, recomendamos usar nginx y gunicorn.

Frappé tambien soporta la architectura multi-tenant. Esto significa que puedes correr varios "sitios" en su instalación, cada uno de ellos estará poniendo a disposición un conjunto de aplicaciones y usuarios. La base de datos para cada sitio es separada.

{next}
