# Generating Documentation Website for your App

Frappé version 6.7 onwards includes a full-blown documentation generator so that you can easily create a website for your app that has both user docs and developers docs (auto-generated).

Version 8.7 onwards, these will be generated in a target app.

## Writing Docs

### 1. Setting up docs

The first step is to setup the docs folder. For that you must create a new file in your app `config/docs.py` if it is not auto-generated. In your `docs.py` file, add the following module properties.


    source_link = "https://github.com/[orgname]/[reponame]"
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

### 2. Add User Documentation

To add user documentation, add folders and pages in your `/docs/user` folder in the same way you would build a website pages in the `www` folder.

Some quick tips:

1. Add your pages as `.md` or `.html` pages
2. Optionally add `.css` files with the same name that will be automatically served
3. Add index by adding `{index}`

### 3. Linking

While linking make sure you add `/docs` to all your links.


    {% raw %}<a href="/docs/user/link/to/page.html">Link Description</a>{% endraw %}


### 4. Adding Images

You can add images in the `/docs/assets` folder. You can add links to the images as follows:

    {% raw %}<img src="/docs/assets/img/my-img/gif" class="screenshot">{% endraw %}

---


## Building Docs

You must create a new app that will have the output of the docs, which is called the "target" app. For example, the docs for ERPNext are hosted at erpnext.org, which is based on the app "foundation". You can create a new app just to push docs of any other app.

To output docs to another app,

    bench --site [site] build-docs [app] --target [target_app]

This will create a new folder `/docs` inside the `www` folder of the target app and generate automatic docs (from code), model references and copy user docs and assets.

To view the docs, just go the the `/docs` url on your target app. Example:

    https://erpnext.org/docs
