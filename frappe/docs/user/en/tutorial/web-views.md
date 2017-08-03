# Web Views

Frappé has two main user environments, the Desk and Web. Desk is a controlled UI environment with a rich AJAX application and the web is more traditional HTML templates served for public consumption. Web views can also be generated to create more controlled views for users who may login but still do not have access to the Desk.

In Frappé, Web Views are managed by templates and they are usually in the `templates` folder. There are 2 main types of templates.

1. Pages: These are Jinja templates where a single view exists for a single web route e.g. `/blog`.
2. Generators: These are templates where each instance of a DocType has a separate web route `/blog/a-blog`, `blog/b-blog` etc.
3. Lists and Views: These are standard lists and views with the route `[doctype]/[name]` and are rendered based on permission.

### Standard Web Views

> This features is still under development.

Let us look at the standard Web Views:

If you are logged in as the test user, go to `/article` and you should see the list of articles:

<img class="screenshot" alt="web list" src="/docs/assets/img/web-list.png">

Click on one article and you will see the default web view

<img class="screenshot" alt="web view" src="/docs/assets/img/web-view.png">

Now if you want to make a better list view for the article, drop a file called `row_template.html` in the
`library_management/templates/includes/list/` folder. Here is an example file:

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


Here, you will get all the properties of the article in the `doc` object.

The updated list view looks like this!

<img class="screenshot" alt="new web list" src="/docs/assets/img/web-list-new.png">

#### Home Page

Frappé also has a built-in signup workflow which also includes 3rd party signups via Google, Facebook and GitHub. When a user signs up on the web, she does not have access to the desk interface by default.

> To allow user access into the Desk, open set the user from Setup > User and set the User Type as "System User"

Now for the non system users, we can set a home page when they login via `hooks.py` based on the role.

To when library members sign in, they must be redirected to the `article` page, to set this open `library_management/hooks.py` and add this:

	role_home_page = {
		"Library Member": "article"
	}

{next}
