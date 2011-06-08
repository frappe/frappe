Creating Pages
==============

Pages can be used to make custom interfaces. A Page is a container where you can add custom HTML.

A Page has full access to the Client APIs and you can build very rich interfaces using Pages

Page Elements
-------------

A page is where you can add 

* Content - that goes in the container div
* Client Script - functions, events
* CSS - style
* Static Content - content for search engines
* Roles - roles that are allowed to view the page

Scripting Pages
---------------

User defined page functions can be added to the "pscript" namespace.

When a page is loaded, the function "pscript.onload_" + the page name is called if it is declared. On refresh,
the function "pscript.refresh_" + the page name is called.

For example for a page called "MyHome", the function called onload is pscript.onload_MyHome();

For more ideas, see the cookbook

   
