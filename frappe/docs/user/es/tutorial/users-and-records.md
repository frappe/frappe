# Creando Usuarios y Registros

Teniendo los modelos creados, podemos empezar a crear registros usando la interfaz gráfica de usuario de Frappé. No necesitas crear vistas! Las vistas en Frappé son automáticamente creadas basadas en las propiedades del DocType.

### 4.1 Creando Usuarios

Para crear registros, primero vamos a crear un Usuario. Para crear un usuario, ir a:

> Setup > Users > User > New

Crea un nuevo Usuario y llena los campos de nombre, primer nombre y nueva contraseña.

Luego dale los Roles de Librarian y de Library Member a este usuario.

<img class="screenshot" alt="Add User Roles" src="/docs/assets/img/add_user_roles.png">

Ahora cierra sesión y accede usando las credenciales del nuevo usuario.

### 4.2 Creando Registros

Debes ver un ícono del módulo de Library Management. Dar click en el ícono para entrar a la página del módulo:

<img class="screenshot" alt="Library Management Module" src="/docs/assets/img/lib_management_module.png">

Aquí puedes ver los DocTypes que fueron creados para la aplicación. Vamos a comenzar a crear nuevos registros.

Primero vamos a crear un nuevo Article:

<img class="screenshot" alt="New Article" src="/docs/assets/img/new_article_blank.png">

Aquí vas a ver que los DocTypes que haz creado han sido renderizados como un formulario. Las validaciones y las otras restricciones también están aplicadas según se diseñaron. Vamos a llenar los datos de un Article.

<img class="screenshot" alt="New Article" src="/docs/assets/img/new_article.png">

Puedes agregar una imagen si deseas.

<img class="screenshot" alt="Attach Image" src="/docs/assets/img/attach_image.gif">

Ahora vamos a crear un nuevo miembro:

<img class="screenshot" alt="New Library Member" src="/docs/assets/img/new_member.png">

Despues de esto, crearemos una nueva membresía (membership) para el miembro.

Si recuerdas, aquí hemos específicado los valores del nombre y apellido del miembro directamente desde el registro del miembro tan pronto selecciones el miembro id, los nombres serán actualizados.

<img class="screenshot" alt="New Library Membership" src="/docs/assets/img/new_lib_membership.png">

Como puedes ver la fecha tiene un formato de año-mes-día lo cual es una fecha del sistema. Para seleccionar o cambiar la fecha, tiempo y formatos de números, ir a:

> Setup > Settings > System Settings

<img class="screenshot" alt="System Settings" src="/docs/assets/img/system_settings.png">

{next}
