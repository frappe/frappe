# 制作新的应用

一旦安装了 bench，你会看到两个主要的文件夹，`apps` 和 `sites`。 所有的应用将安装在 apps 中。

要制作新的应用，请转到您的 bench 文件夹，然后运行 `bench new-app {app_name}`，填写有关该应用的详细信息。 这将为您创建样板应用。

	$ bench new-app library_management
	App Title (defaut: Lib Mgt): Library Management
	App Description:  App for managing Articles, Members, Memberships and Transactions for Libraries
	App Publisher: Frappé
	App Email: info@frappe.io
	App Icon (default 'octicon octicon-file-directory'): octicon octicon-book
	App Color (default 'grey'): #589494
	App License (default 'MIT'): GNU General Public License

### 应用结构

该应用将创建在一个名为 `library_management` 的文件夹中，并具有以下结构：

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

1. `config` 文件夹包含应用配置信息。
1. `desktop.py` 是可以添加到工作台 (Desk) 的桌面图标。
1. `hooks.py` 是指与环境和其他应用进行集成的地方。

1. `library_management` (内部) 是引导**模块**。 在 Frappé 中，**模块**是模型和控制器文件所在的地方。
1. `modules.txt` 包含应用中**模块**的列表。 当您创建新模块时，需要在该文件中更新它。
1. `patches.txt` 是编写迁移补丁的地方。 它们是使用点表示法的 Python 模块引用。
1. `templates` 是维护 Web 视图模板的文件夹。 **登录**以及其他标准页面的模板由 Frappé 处理。
1. `generators` 是维护模型模板的地方，其中每个模型实例都有一个分离的 web 路由，例如**博客帖子**每个帖子都有其唯一的 Web URL。 在 Frappé 中，使用的模板引擎是 Jinja2。
1. `pages` 是维护单个路由模板的位置。 例如 "/blog" 类型的页面。

{next}
