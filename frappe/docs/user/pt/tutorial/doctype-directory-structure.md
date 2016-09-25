# Estrutura de diretórios do DocType

Depois de salvar os doctypes, verifique-se de que oo arquivos do modelo `.json` e `.py` foram criados no modulo `apps/library_management/library_management`. A estrutura de diretório após a criação dos modelos deve ficar assim:

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
