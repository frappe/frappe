# Criando modelos

O próximo passo é criar os modelos como discutimos na introdução. Em Frappé, os modelos são chamados **DocTypes**. Você pode criar novos doctypes atravez da interface do Desk. **DocTypes** são feitos de campos chamados **DocField** e de permissões com base nas permissões que são integrados nos modelos, estes são chamados **DocPerms**.

Quando um DocType é salvo, uma nova tabela é criada no banco de dados. Esta tabela é nomeado como `tab[doctype]`.

Quando você cria um **DocType** uma nova pasta é criada no **Módulo** e um arquivo JSON do modelo e um controlador template em Python são criados automaticamente. Quando você atualizar o DocType, o arquivo modelo JSON é atualizado e quando o `bench migrate` é executado, ele é sincronizado com o banco de dados. Isto torna mais fácil para propagar alterações de schema e migrar.

### Modo Desenvolvedor

Para criar modelos, você deve definir `developer_mode` como 1 no arquivo `site_config.json` localizado em /sites/library e executar o comando `bench clear-cache` ou use o menu de usuário na interface do usuário e clique em "Atualizar" para que as alterações entrem em vigor. Agora você deve ver o aplicativo "Developer" em sua Desk

	{
	 "db_name": "bcad64afbf",
	 "db_password": "v3qHDeVKvWVi7s97",
	 "developer_mode": 1
	}

{next}
