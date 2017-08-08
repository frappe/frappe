# Vistas Web (Web Views)

Frappé tiene dos entornos principales, El escritorio y la Web. El escritorio es una interfaz de usuario controlada con una excelente aplicación AJAX y la web es mas plantillas de HTML tradicionales dispuestas para consumo público. Vistas Web pueden también ser generadas para crear vistas controladas para los usuarios que puedes acceder al sistema pero aún así no tener acceso al escritorio.

En Frappé, Las vistas web son manejadas por plantillas que estan usualmente en el directorio `templates`. Hay dos tipos principales de plantillas.

1. Pages: Estos son plantillas Jinja donde una vista existe solo para una ruta. ejemplo. `/blog`.
2. Generators: Estas son plantiallas donde cada instancia de un DocType tiene una ruta diferente `/blog/a-blog`, `blog/b-blog` etc.
3. Lists and Views: Estos son listas y vistan estandares con la ruta `[doctype]/[name]` y son renderizadas basándose en los permisos.

### Vista Web Estandar

> Esta funcionalidad sigue bajo desarrollo.

Vamos a ver las Vistas web estandar:

Si estas logueado como el usuario de prueba, ve a `/article` y deberías ver la lista de artículos.

<img class="screenshot" alt="web list" src="/docs/assets/img/web-list.png">

Da click en uno de los artículos y vas a ver una vista web por defecto

<img class="screenshot" alt="web view" src="/docs/assets/img/web-view.png">

Si deseas hacer una mejor vista para la lista de artículos, crea un archivo llamado `row_template.html` en el directorio `library_management/templates/includes/list/`.
 Aquí hay un archivo de ejemplo:

	{% raw %}<div class="row">
		<div class="col-sm-4">
			<a href="/Article/{{ doc.name }}">
				<img src="{{ doc.image }}"
					class="img-responsive" style="max-height: 200px">
			</a>
		</div>
		<div class="col-sm-4">
			<a href="/Article/{{ doc.name }}"><h4>{{ doc.article_name }}</h4></a>
			<p>{{ doc.author }}</p>
			<p>{{ (doc.description[:200] + "...")
				if doc.description|len > 200 else doc.description }}</p>
			<p class="text-muted">Publisher: {{ doc.publisher }}</p>
		</div>
	</div>{% endraw %}

Aquí, vas a tener todas las propiedades de un artículo en el objeto `doc`.

La lista actualizada debe lucir de esta manera!

<img class="screenshot" alt="new web list" src="/docs/assets/img/web-list-new.png">

#### Página de Inicio

Frappé también tiene vistas para el registro de usuarios que incluye opciones de registro usando Google, Facebook y GitHub. Cuando un usuario se registra vía la web, no tiene acceso a la interfaz del Escritorio por defecto.

> Para permitirles a los usuarios acceso al Escritorio, debes especificar que el usuario es de tipo "System User" en Setup > User

Para usuario que no son de tipo System User, podemos especificar una página de inicio por defecto a traves de `hooks.py` basándonos en Role.

Cuando miembros acceden al sistema, deben ser redireccionados a la página `article`, para configurar esto modifica el archivo `library_management/hooks.py` y agrega lo siguiente:

	role_home_page = {
		"Library Member": "article"
	}

{next}
