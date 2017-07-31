# Creando Modelos

El siguiente paso es crear los modelos que discutimos en la introducción. En Frappé, los modelos son llamados **DocTypes**. Puedes crear nuevos DocTypes desde el UI Escritorio de Frappé.  **DocTypes** son creados de campos llamados **DocField** y los permisos basados en roles son integrados dentro de los modelos, estos son llamados **DocPerms**.

Cuando un DocType es guardado, se crea una nueva tabla en la base de datos. Esta tabla se nombra `tab[doctype]`.

Cuando creas un **DocType** una nueva carpeta es creada en el **Module** y un archivo JSON y una platilla de un controlador en Python son creados automáticamente. Cuando modificas un DocType, el archivo JSON es modificado y cada vez que se ejecuta `bench migrate`, sincroniza el archivo JSON con la tabla en la base de datos. Esto hace que sea más facíl reflejar los cambios hechos al esquema y migrarlo.

### Modo desarrollador

Para crear modelos, debes setear `developer_mode` a 1 en el archivo `site_config.json` ubicados en /sites/library y ejecuta el comando `bench clear-cache` o usa el menú de usuario en el Escritorio y da click en "Recargar/Reload" para que los cambios tomen efecto. Deberías poder ver la aplicación llamada "Developer" en su escritorio.

	{
	 "db_name": "bcad64afbf",
	 "db_password": "v3qHDeVKvWVi7s97",
	 "developer_mode": 1
	}

{next}
