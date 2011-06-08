:mod:`page` --- Page Module
=============================

.. module:: page
   :synopsis: Contains the Page class and other methods related to :term:`Page`

.. class:: Page(name)

   A page class helps in loading a Page in the system. On loading
   
   * Page will import Client Script from other pages where specified by `$import(page_name)`
   * Execute dynamic HTML if the `content` starts with `#python`

   .. method:: load()

      Returns :term:`doclist` of the `Page`

Internal Methods
----------------

.. method:: get(name)

   Return the :term:`doclist` of the `Page` specified by `name`

.. method:: getpage()

   Load the page from `webnotes.form` and send it via `webnotes.response`