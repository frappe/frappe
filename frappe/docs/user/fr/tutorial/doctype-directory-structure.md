# Structure du repertoire d'un DocType

Après avoir sauvegardé vos DocTypes, vérifiez que les modèles dans les fichiers `.json` et `.py` soient créés dans le module
`apps/library_management/library_management`. La structure du repertoire devrait ressembler à:

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
