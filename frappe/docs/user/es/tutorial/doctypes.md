# DocType

Despues de crear los Roles, vamos a crear los **DocTypes**

Para crear un nuevo **DocType**, ir a:

> Developer > Documents > Doctype > New

<img class="screenshot" alt="New Doctype" src="/docs/assets/img/doctype_new.png">

En el DocType, primero el módulo, lo que en nuestro caso es **Library Management**

#### Agregando Campos

En la tabla de campos, puedes agregar los campos (propiedades) de el DocType (Article).

Los campos son mucho más que solo columnas en la base de datos, pueden ser:
Fields are much more than database columns, they can be:

1. Columnas en la base de datos
1. Ayudantes de diseño (definidores de secciones / columnas)
1. Tablas hijas (Tipo de dato Table)
1. HTML
1. Acciones (botones)
1. Adjuntos o Imagenes

Vamos a agregar los campos de el Article.

<img class="screenshot" alt="Adding Fields" src="/docs/assets/img/doctype_adding_field.png">

Cuando agredas los campos, necesitas llenar el campo **Type**. **Label** es opcional para los Section Break y Column Break. **Name** (`fieldname`) es el nombre de la columna en la tabla de la base de datos y tambien el nombre de la propiedad para el controlador. Esto tiene que ser *code friendly*, i.e. Necesitas poner _ en lugar de " ". Si dejas en blanco este campo, se va a llenar automáticamente al momento de guardar.

Puedes establecer otras propiedades al campo como si es obligatorio o no, si es de solo lectura, etc.

Podemos agregar los siguientes campos:

1. Article Name (Data)
2. Author (Data)
3. Description
4. ISBN
5. Status (Select): Para los campos de tipo Select, vas a escribir las opciones. Escribe **Issued** y **Available** cada una en una linea diferente en la caja de texto de Options. Ver el diagrama más abajo.
6. Publisher (Data)
7. Language (Data)
8. Image (Adjuntar Imagen)


#### Agregar permisos

Despues de agregar los campos, dar click en hecho y agrega una nueva fila en la sección de Permission Roles. Por ahora, vamos a darle accesos Lectura, Escritura, Creación y Reportes al Role **Librarian**. Frappé cuenta con un sistema basados en el modelo de Roles finamente granulado. Puedes cambiar los permisos más adealante usando el **Role Permissions Manager** desde **Setup**.

<img class="screenshot" alt="Adding Permissions" src="/docs/assets/img/doctype_adding_permission.png">

#### Guardando

Dar click en el botón de **Guardar**. Cuando el botón es clickeado, una ventana emergente le va a preguntar por el nombre. Vamos a darle el nombre de **Article** y guarda el DocType.

Ahora accede a mysql y verifica que en la base de datos que se ha creado una nueva tabla llamada tabArticle.

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

Como puedes ver, junto con los DocFields, algunas columnas fueron agregadas a la tabla. Las importantes a notar son, la clave primaria, `name`, `owner`(El usuario que creo el registro),
`creation` y `modified` (timestamps para la creación y última modificación).

{next}
