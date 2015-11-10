# Generating Documentation Website for your App

Frappe version 6.7 onwards includes a full-blown documentation generator so that you can easily create a website for your app that has both user docs and developers docs (auto-generated). These pages are generated as static HTML pages so that you can add them as GitHub pages.

## Writing Docs

### 1. Setting up docs

#### 1.1. Setup `docs.py`

The first step is to setup the docs folder. For that you must create a new file in your app `config/docs.py` if it is not auto-generated. In your `docs.py` file, add the following module properties.


    source_link = "https://github.com/[orgname]/[reponame]"
    docs_base_url = "https://[orgname].github.io/[reponame]"
    headline = "This is what my app does"
    sub_heading = "Slightly more details with key features"
    long_description = """(long description in markdown)"""

    def get_context(context):
        # optional settings

        # context.brand_html = 'Brand info on the top left'
        # context.favicon = 'path to favicon'
        #
        # context.top_bar_items = [
        #   {"label": "About", "url": context.docs_base_url + "/about"},
        # ]

    	pass

#### 1.2. Generate `/docs`

To generate the docs for the `current` version, go to the command line and write

    bench --site sitename make-docs app_name current

If you want to maintain versions of your docs, then you can add a version number instead of `current`

This will create a `/docs` folder in your app.

### 2. Add User Documentation

To add user documentation, add folders and pages in your `/docs/user` folder in the same way you would build a website pages in the `www` folder.

Some quick tips:

1. Add your pages as `.md` or `.html` pages
2. Optionally add `.css` files with the same name that will be automatically served
3. Add index by adding `{index}`

### 3. Linking

While linking make sure you add `{{ docs_base_url }}` to all your links.


    {% raw %}<a href="{{ docs_base_url }}/user/link/to/page.html">Link Description</a>{% endraw %}


### 4. Adding Images

You can add images in the `/docs/assets` folder. You can add links to the images as follows:

    {% raw %}<img src="{{ docs_base_url }}/assets/img/my-img/gif" class="screenshot">{% endraw %}

---

## Viewing Locally

To test your docs locally, add a `--local` option to the `build-docs` command.

    bench --site [site] build-docs [appname] current /home/docs/reponame --local

Then it will build urls so that you can view these files locally. To view them locally in your browser, you can use the Python SimpleHTTPServer

    python -m SimpleHTTPServer 8080

---

## Publishing to GitHub Pages

To publish your docs on GitHub pages, you will have to create an empty and orphan branch in your repository called `gh-pages` and write yours there

Go to new folder (outside your bench) and clone your repo again

    $ git clone git@github.com:[orgname]/[reponame]
    $ cd reponame
    $ git checkout --orphan gh-pages
    $ git rm -rf .

Now go back to your bench folder and write these docs to this branch. For example if your path to the `gh-pages` repo is `/home/docs/reponame`

    bench --site [site] build-docs [appname] current /home/docs/reponame

To check your documentation online go to: https://[orgname].github.io/[reponame]
