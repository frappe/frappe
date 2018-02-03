# Nombrando y Asociando DocType

Vamos a crear otro DocType y guardarlo:

1. Library Member (First Name, Last Name, Email Address, Phone, Address)

<img class="screenshot" alt="Doctype Saved" src="/docs/assets/img/naming_doctype.png">


#### Nombrando DocTypes

Los DocTypes pueden ser nombrados en diferentes maneras:

1. Basados en un campo
1. Basados en una serie
1. A traves del controlador (vía código)
1. Con un promt

Esto puede ser seteado a traves del campo **Autoname**. Para el controlador, dejar en blanco.

> **Search Fields**: Un DocType puede ser nombrado por serie pero seguir teniendo la necesidad de ser buscado por nombre. En nuestro caso, el Article va ser buscado por el título o el nombre del autor. Por lo que vamos a poner esos campos en el campo de search.

<img class="screenshot" alt="Autonaming and Search Field" src="/docs/assets/img/autoname_and_search_field.png">

#### Campo de Enlace y Campo Select

Las claves foraneas son específicadas en Frappé como campos **Link** (Enlace). El DocType debe ser mencionado en el area de texto de Options.

En nuestro ejemplo, en el DocType de Library Transaction,tenemos que enlazar los dos DocTypes de Library Member and the Article.

**Nota:** Recuerda que los campos de Enlace no son automáticamente establecidos como claves foraneas en la base de datos MariaDB, porque esto crearía un indice en la columna. Las validaciones de claves foraneas son realizadas por el Framework.

<img class="screenshot" alt="Link Field" src="/docs/assets/img/link_field.png">

Por campos de tipo Select, como mencionamos antes, agrega varias opciones en la caja de texto **Options**, cada una en una nueva linea.

<img class="screenshot" alt="Select Field" src="/docs/assets/img/select_field.png">

De manera similar continua haciendo los otros modelos.

#### Valores enlazados

Un patrón estandar es que cuando seleccionas un ID, dice **Library Member** en **Library Membership**, entonces el nombre y apellido del miembro deberian ser copiados en campos relevantes de el Doctype  Library Membership Transaction.

Para hacer esto, podemos usar campos de solo lectura y en opciones, podemos especificar el nombre del link (enlace) y el campo o propiedad que deseas obtener. Para este ejempo en **Member First Name** podemos especificar `library_member.first_name`.

<img class="screenshot" alt="Fetch values" src="/docs/assets/img/fetch.png">

### Completar los modelos

En la misma forma, puedes completar todos los modelos, todos los campos deben verse de esta manera

#### Article

<img class="screenshot" alt="Article" src="/docs/assets/img/doctype_article.png">

#### Library Member

<img class="screenshot" alt="Library Member" src="/docs/assets/img/doctype_lib_member.png">

#### Library Membership

<img class="screenshot" alt="Library Membership" src="/docs/assets/img/doctype_lib_membership.png">

#### Library Transaction

<img class="screenshot" alt="Library Transaction" src="/docs/assets/img/doctype_lib_trans.png">

> Asegurate de dar permiso a **Librarian** en cada DocType

{next}
