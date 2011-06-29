:mod:`doclist` --- Doclist Module
=================================

.. module:: doclist
   :synopsis: Collection of functions that are used on a list of Document objects (doclist)

.. function:: getlist(doclist, field)

   Filter a list of records for a specific field from the full doclist
   
   Example::
   
     # find all phone call details     
     dl = getlist(self.doclist, 'contact_updates')
     pl = []
     for d in dl:
       if d.type=='Phone':
         pl.append(d)

.. function:: copy(doclist, no_copy = [])

      Save & return a copy of the given doclist
      Pass fields that are not to be copied in `no_copy`

.. function:: to_html(doclist)

   Return a simple HTML format of the doclist

functions for internal use
---------------------------

.. function:: expand(docs)

   Expand a doclist sent from the client side. (Internally used by the request handler)

.. function:: compress(doclist)

   Compress a doclist before sending it to the client side. (Internally used by the request handler)

.. function:: validate_links_doclist(doclist)

   Validate link fields and return link fields that are not correct.
   Calls the `validate_links` function on the Document object
	
.. function:: getvaluelist(doclist, fieldname)

   Returns a list of values of a particualr fieldname from all Document object in a doclist

.. function:: getchildren(name, childtype, field='', parenttype='')
	
   Returns the list of all child records of a particular record (used internally)

