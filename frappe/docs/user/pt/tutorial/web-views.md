# Web Views

Frappé tem dois ambientes de usuário principais, o Desk e o Web. Desk é um ambiente UI controlado com uma rica aplicação AJAX e a web usa template HTML tradicional que serve para consumo público. Web Views também podem ser gerados para criar views mais controladas para os usuários que pode fazer o login mas ainda não têm acesso à Desk.

Em Frappé, Web Views são geridas por modelos e eles geralmente estão na pasta `templates`. Existem 2 tipos principais de templates.

1. Pages: Estes são Jinja Templates, onde existe uma única view para uma única rota web, por exemplo, `/blog`.
2. Generators: Estes são templates em que cada instância de um DocType tem uma rota web separada `/blog/a-blog`, `blog/b-blog` etc.
3. Lists and Views: Estas são listas e views padrões com a rota `[doctype]/[name]` e são processadas com base na permissão.

### Standard Web Views

> Esta funcionalidade ainda esta em desenvolvimento.

Vamos dar uma olhada na standard Web Views:

Se você estiver logado como usuário de teste, vá para `/article` e você deverá ver a lista de artigos:

<img class="screenshot" alt="web list" src="/docs/assets/img/web-list.png">

Clique em um artigo e você vai ver uma Web View padrão

<img class="screenshot" alt="web view" src="/docs/assets/img/web-view.png">

Agora, se você quiser fazer uma List View melhor para o artigo, crie um arquivo chamado `row_template.html` na pasta
`library_management/templates/includes/list/`. Aqui está um exemplo de arquivo:

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


Aqui, você vai ter todas as propriedades do artigo no objeto `doc`.

A List View atualizada se parece com isso!

<img class="screenshot" alt="new web list" src="/docs/assets/img/web-list-new.png">

#### Home Page

Frappé também tem um fluxo de trabalho de inscrição built-in que também inclui inscrições de terceiros via Google, Facebook e GitHub. Quando um usuário se inscreve na web, ele não tem acesso à interface Desk por padrão.

> Para permitir o acesso do usuário ao Desk, abra as configurações pelo Setup > User e defina o usuário como "System User"

Agora, para os não usuários do sistema, podemos definir uma home page para quando eles fizerem login via `hooks.py` com baseado na Role.

Para quando os membros da biblioteca entrarem, eles devem ser redirecionado para a página `article`, para abrir o arquivo `library_management/hooks.py` adicione:

	role_home_page = {
		"Library Member": "article"
	}

{next}
