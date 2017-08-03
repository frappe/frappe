# DocType

Depois de criar as Roles, vamos criar os **DocTypes**

Para criar um novo **DocType**, vá para:

> Developer > Documents > Doctype > New

<img class="screenshot" alt="New Doctype" src="/docs/assets/img/doctype_new.png">

No DocType, criamos o módulo, que no nosso caso é **Library Managment**

#### Adicionando Campos

Na Tabela, você pode adicionar os campos (fields) do DocType (Article).

Os campos são muito mais do que colunas de banco de dados, eles podem ser:

1. Colunas no banco de dados
1. Layout helpers (Seção / quebras de coluna)
1. Tabelas filho (Tabela como tipo de uma propriedade)
1. HTML
1. Ações (botões)
1. Anexos ou imagens

Vamos adicionar os campos do artigo.

<img class="screenshot" alt="Adding Fields" src="/docs/assets/img/doctype_adding_field.png">

Quando você adiciona campos, você precisa digitar o **Type**. **Label** é opcional para quebra de seção e quebra de coluna. **Name** (`fieldname`) é o nome da coluna da tabela de banco de dados e também a propriedade do controlador. Isso tem que ser um *código amigável*, ou seja, ele tem que ter caracteres minusculos e _ em vez de "". Se você deixar o nome do campo em branco, ele será ajustado automaticamente quando você salvá-lo.

Você também pode definir outras propriedades do campo como se é obrigatório, apenas para leitura etc.

Nós podemos adicionar os seguintes campos:

1. Article Name (Data)
2. Author (Data)
3. Description
4. ISBN
5. Status (Select): Para Selecionar campos, você vai entrar nas opções. Digite **Issued** e **Available** cada um em uma nova linha na caixa de Opções. Consulte o diagrama abaixo
6. Publisher (Data)
7. Language (Data)
8. Image (Attach Image)


#### Adicionando permissões

Depois de adicionar os campos, finalize e adicione uma nova linha na seção Regras de permissão. Por enquanto, vamos dar permissão de Read, Write, Create, Delete and Report, a **Librarian**. Frappé tem uma Role baseado nas permissões do modelo. Você também pode alterar as permissões posteriormente usando o **Role Permissions Manager** do **Setup**.

<img class="screenshot" alt="Adding Permissions" src="/docs/assets/img/doctype_adding_permission.png">

#### Salvando

Click no botão **Save**. Quando o botão for clicado, um popup irá te pedir um nome. De o nome de **Article** e salve o DocType.

Agora logue no mysql e verifique se a tabela do banco de dados foi criada:

	$ bench mysql
	Welcome to the MariaDB monitor.  Commands end with ; or \g.
	Your MariaDB connection id is 3931
	Server version: 5.5.36-MariaDB-log Homebrew

	Copyright (c) 2000, 2014, Oracle, Monty Program Ab and others.

	Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

	MariaDB [library]> DESC tabArticle;
	+--------------+--------------+------+-----+---------+-------+
	| Field        | Type         | Null | Key | Default | Extra |
	+--------------+--------------+------+-----+---------+-------+
	| name         | varchar(255) | NO   | PRI | NULL    |       |
	| creation     | datetime(6)  | YES  |     | NULL    |       |
	| modified     | datetime(6)  | YES  |     | NULL    |       |
	| modified_by  | varchar(40)  | YES  |     | NULL    |       |
	| owner        | varchar(60)  | YES  |     | NULL    |       |
	| docstatus    | int(1)       | YES  |     | 0       |       |
	| parent       | varchar(255) | YES  | MUL | NULL    |       |
	| parentfield  | varchar(255) | YES  |     | NULL    |       |
	| parenttype   | varchar(255) | YES  |     | NULL    |       |
	| idx          | int(8)       | YES  |     | NULL    |       |
	| article_name | varchar(255) | YES  |     | NULL    |       |
	| status       | varchar(255) | YES  |     | NULL    |       |
	| description  | text         | YES  |     | NULL    |       |
	| image        | varchar(255) | YES  |     | NULL    |       |
	| publisher    | varchar(255) | YES  |     | NULL    |       |
	| isbn         | varchar(255) | YES  |     | NULL    |       |
	| language     | varchar(255) | YES  |     | NULL    |       |
	| author       | varchar(255) | YES  |     | NULL    |       |
	+--------------+--------------+------+-----+---------+-------+
	18 rows in set (0.00 sec)


Como você pode ver, junto com os DocFields, várias colunas padrão também foram adicionados à tabela. Importante notar aqui que, a chave primária, `name`,` owner` (o usuário que criou o registro), `creation` e` modified` (timestamps para a criação e última modificação).

{next}
