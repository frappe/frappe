# Estructura de directorios de un DocType

Despues de guardar los DocTypes, revisa que los archivos `.json` y `.py` fuueron creados en módulo `apps/library_management/library_management`. La estructura de directorios despues de crear los modelos debería ser similar a la siguiente:

	.
	├── MANIFEST.in
	├── README.md
	├── library_management
	..
	│   ├── library_management
	│   │   ├── __init__.py
	│   │   └── doctype
	│   │       ├── __init__.py
	│   │       ├── article
	│   │       │   ├── __init__.py
	│   │       │   ├── article.json
	│   │       │   └── article.py
	│   │       ├── library_member
	│   │       │   ├── __init__.py
	│   │       │   ├── library_member.json
	│   │       │   └── library_member.py
	│   │       ├── library_membership
	│   │       │   ├── __init__.py
	│   │       │   ├── library_membership.json
	│   │       │   └── library_membership.py
	│   │       └── library_transaction
	│   │           ├── __init__.py
	│   │           ├── library_transaction.json
	│   │           └── library_transaction.py

{next}
