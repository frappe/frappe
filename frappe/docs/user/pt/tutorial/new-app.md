# Crie um novo aplicativo

Uma vez que o banco ja estiver instalado, você verá duas pastas principais, `apps` e` sites`. Todos os aplicativos serão instalados em apps.

Para criar uma nova aplicação, vá para a pasta do bench e execute, `bench new-app {app_name}` e preencha os detalhes sobre o aplicativo. Isto irá criar uma aplicação base para você.

	$ bench new-app library_management
	App Title (defaut: Lib Mgt): Library Management
	App Description:  App for managing Articles, Members, Memberships and Transactions for Libraries
	App Publisher: Frappé
	App Email: info@frappe.io
	App Icon (default 'octicon octicon-file-directory'): octicon octicon-book
	App Color (default 'grey'): #589494
	App License (default 'MIT'): GNU General Public License

### Estrutura do aplicativo

O aplicativo será criado em uma pasta chamada `library_management` e terá a seguinte estrutura::

	.
	├── MANIFEST.in
	├── README.md
	├── library_management
	│   ├── __init__.py
	│   ├── config
	│   │   ├── __init__.py
	│   │   └── desktop.py
	│   ├── hooks.py
	│   ├── library_management
	│   │   └── __init__.py
	│   ├── modules.txt
	│   ├── patches.txt
	│   └── templates
	│       ├── __init__.py
	│       ├── generators
	│       │   └── __init__.py
	│       ├── pages
	│       │   └── __init__.py
	│       └── statics
	├── license.txt
	├── requirements.txt
	└── setup.py

1. `config` pasta que contém as informações de configuração do aplicativo
1. `desktop.py` é onde os ícones da área de trabalho pode ser adicionado ao Desk
1. `hooks.py` é onde integrações com o ambiente da aplicação e outras aplicações é mencionada.
1. `library_management` (Interior) é um **módulo** que foi criado. Em Frappé, um **módulo** é onde os arquivos do modelo e do controlador residem.
1. `modules.txt` contém a lista dos **módulos** do aplicativo. Quando você cria um novo módulo, é necessário que você atualize este arquivo.
1. `patches.txt` é o lugar onde os patches de migração são escritos. Eles são referências de módulos Python utilizando a notação de ponto.
1. `templates` é a pasta onde os modelos de web view são mantidos. Modelos para **Login** e outras páginas padrão são criadas pelo frappe.
1. `generators` é onde os templates para os modelos são mantidas, onde cada instância de modelo tem uma rota web separada, por exemplo, um **Post de um Blog**, onde cada post tem a sua única url web. Em Frappé, o mecanismo de modelagem utilizada é o Jinja2
1. `pages` É onde uma única rota para os modelos são mantidas. Por exemplo, para um "/blog" tipo da página.

{next}
