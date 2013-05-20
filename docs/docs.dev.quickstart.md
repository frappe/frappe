---
{
	"_label": "Quickstart"
}
---
### Preamble

wnframework is, a Python based, meta-data driven framework. The framework implements 
its own object-relational model (ORM) and provides a rich client interface based on 
Javascript. It is primararily used to develop [ERPNext](https://github.com/webnotes/erpnext)

To develop on wnframework, you must have a basic understanding of how web applications 
and client-server architectures work. On the server-side, requests are handled by Python 
modules via CGI. So each request is a new thread and there is no state preservation on 
the server. Session data is stored in memcached server.

WNFramework also has way you metadata is defined, called a `DocType`. Everything 
object in the system like a Customer or Journal Voucher is a `DocType`.

Overall, be prepared for a slight learning curve. A lot of the inner code / design 
is not very elegant and you might encounter spaghetti at certain places. We are working 
to reduce all of that.

---

## Meta data

Base model in wnframework is called a `DocType`. A `DocType` represents a database table, 
a web form and a controller to execute business logic. In classical MVC terms it is all 
three model, view and controller to an extent.

`DocType` objects have `DocField`s that are properties of the model.

---

## Client-Server Setup

Let us understand how to setup web folders via ERPNext

An ERPNext setup contains 2 repositories [erpnext](/webnotes/erpnext) and 
[wnframework](/webnotes/wnframework). In the main folder of the erpnext setup there 
are 3 folders:

	+ lib
	+ app
	+ public

The **lib** folder represents *wnframework*, the **app** folder represents *erpnext* and 
the **public** folder is served on the web.

To build the public folder for the first time, run this utility from the base folder:
	
`$ lib/wnf.py -b`

All web pages are served by `public/web.py` and all data requests are served 
by `public/server.py`

The server-side libraries are in `lib/webnotes` and client-side libraries are 
in `lib/public/wn` folders.

### Requests & Routings

There are 2 types of requests, requests for web pages (when the user is not logged in) and 
data requests when the user is logged in. Let us see data requests:

All data requests are made on `public/server.py`. The method and parameters are passed as 
form parameters. 

The `cmd` paramter represents the python method to be executed. This is the "routing" used 
in wnframwork. Use the `@webnotes.whitelist()` decorator to whitelist a particular method 
to be accessible by the web.

For example, the request:

`server.py?cmd=accounts.utils.get_account&account_name=Test`

will call the `get_account` method in `app/accounts/utils.py`. 

#### Repsonse

The return to that will be sent as a JSON object

	{
	  "message": "returned by get_account", 
	  "server_messages":"Any popup messages to be displayed", 
	  "exc": "Any exceptions encountered"
	}

Once the control is passed on to the method, the response is sent back via JSON.

---

## Front End

The front end is a Javascript based client application. You can login by opening the login 
page from your browser. If you have setup your apache routes correctly, just go to  
`localhost/public/login` or equivalent to see the login page. This actually translates 
into `public/web.py?page=login`.

Once you login, you will be redirected to `app.html` that fires up the application front-end.

### URL routing:

Different pages / objects are accessed by url fragments `#`

#### Forms

All objects are accessible via `#Form/[DocType]/[Doument Name]` on the URL.

To open the customer **DocType**, you can go to `#Form/DocType/Customer` or to open 
a Customer, **Customer A**, go to `#Form/Customer/Customer A`

#### Pages

Static pages in the application are accessed by their name. For example, the home 
page called `desktop` can be accessed by `#desktop`

#### Client Application

The client application is bunch of js libraries that help in navigation, rendering 
forms, reports and other components. The application code in `public/js/all-app.js` 
is built by combining files specified in `lib/public/build.json` and `app/public/build.json`.
 To rebuild the client application after making a change, call `lib/wnf.py -b` from the 
command line.

---

## Application / Module Development

### Creating / Editing DocTypes

To create or edit the **DocType** "schema" you will have to fire the front-end via a 
web-browser and login as Administrator. To open a **DocType**, 
go to Document > Search > DocType and select the **DocType** to edit.

The **DocType** form should be self explanatory. It has a list of fields that are 
used for both the database table and form. Special fields like `Column Break` and 
`Section Break` are present to make the form layout that is processed sequentially.

DocType is discovered via permissions (`DocPerm`) and by URL routes. 

Once you save a **DocType**, the database schema is automatically update, while 
developing, you should fire up a mysql command-line or viewer to see the impact 
of your database changes.

### Adding code to DocTypes

You can add business logic by writing event code on both client and server side. 
The server side events are written in Python and client side events are written in 
Javascript.

The files from where these events are picked up are in the module folders in the 
repositories. Apart from the `core` module, all modules are parts 
of **erpnext** (`app` folder). Each DocType has its own folder in the module in a 
folder called `doctype`. If you browse the files of **erpnext**, you should be able 
to locate these files easily.

#### Server-side modules

For example, the server-side script for DocType **Account** in module **Accounts** 
will be present in the folder `app/accounts/doctype/account/account.py`

The events are declared as a part of class called `DocType`. In the `DocType` 
class there are two main useful properties:

- `doc`: Represents the main record.
- `doclist`: Represents list of records (including child records) that are associated 
with this DocType. For example the `doclist` of **Sales Order** will have the main record 
and all **Sales Order Item** records.

The main serverside events are:

- `validate`: Called before the `INSERT` or `UPDATE` method is called.
- `on_update`: Called after saving.
- `on_submit`: Called after submission
- `on_cancel`: Called after cancellation.

See a sample server side file for more info!

---

## Custom UI: Pages

Custom UI like **Chart of Accounts** etc, is made by Pages. Pages are free form virtual 
pages in that are rendered on the client side. A page can have an `.html` (layout), 
`.py` (server calls), `.js` (user interface) and `.css` (style) components.

Understand how pages work, it is best to open an existing page and see how it works.

---

## Patching & Deployment

Data / schema changes are done to wnframwork via patches released in the `app/patches` 
module (see erpnext folder for more details). To run all latest patches that have not 
been executed, run `lib/wnf.py -l`

wnframework deployment is done by the `lib/wnf.py` utility.

See `lib/wnf.py --help` for more help.

_Good luck!_
