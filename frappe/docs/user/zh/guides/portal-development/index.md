# Making Portals

Frappé has powerful tools to build portals where pages can be dynamically generated using templates (Jinja) and users can be shown records after login

#### Adding Pages

You can make your website by adding pages to the `/www` folder of your website. The urls of your site will match the path of your pages within the `/www` folder.

Pages must be `.html` or `.md` (Markdown) files. Basic HTML template is provided in frappe in `frappe/templates/base_template.html`

#### Views after Login

After logging in, the user sees a "My Account" page `/me` where user can access certain documents that are shown via a menu

The user can view records based on permissions and also add / edit them with **Web Forms**

{index}
