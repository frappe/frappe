# Configurando o site

Vamos criar um novo site e chamá-lo de `library`.

*Nota: Antes de criar um novo site, é necessário ativar o mecanismo de armazenamento Barracuda na instalação do MariaDB.*
*Copie as seguintes configurações de banco de dados ERPNext padrão para o arquivo `my.cnf`.*

    [mysqld]
    innodb-file-format=barracuda
    innodb-file-per-table=1
    innodb-large-prefix=1
    character-set-client-handshake = FALSE
    character-set-server = utf8mb4
    collation-server = utf8mb4_unicode_ci

    [mysql]
    default-character-set = utf8mb4


Você pode instalar um novo site, pelo comando `bench new-site library`

Isto irá criar uma nova pasta para o site e um banco de dados e instalar o `frappe` (que também é uma aplicação!) No novo site. A aplicação `frappe` tem dois módulos embutidos **Core** e **WebSite**. O módulo de Core contém os modelos básicos para a aplicação. Frappé é uma estrutura como as pilhas e vem com um monte de modelos internos. Estes modelos são chamados doctypes **Mais sobre isso mais tarde**.

	$ bench new-site library
	MySQL root password:
	Installing frappe...
	Updating frappe                     : [========================================]
	Updating country info               : [========================================]
	Set Administrator password:
	Re-enter Administrator password:
	Installing fixtures...
	*** Scheduler is disabled ***

### Estrututa do Site

Uma nova pasta chamada `library` será criado na pasta` sites`. Aqui está a estrutura de pastas padrão para um site.

	.
	├── locks
	├── private
	│   └── backups
	├── public
	│   └── files
	└── site_config.json

1. `public/files` é onde os arquivos enviados pelo usuário são armazenados.
1. `private/backups` é onde os backups são despejados
1. `site_config.json` é onde as configurações a nível do site são mantidas.

### Configurações padrão do site

No caso de você ter vários sites em seu bench use `bench use [site_name]` para definir o site padrão.

Exemplo:

	$ bench use library

### Instalar App

Agora vamos instalar nosso app `library_management` no nosso site `library`

1. Instale library_management no library com: `bench --site [site_name] install-app [app_name]`

Exemplo:

	$ bench --site library install-app library_management

{next}
