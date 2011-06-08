:mod:`module` --- Module Module
================================

.. module:: module
   :synopsis: Collection of methods that are used for managing Modules identified by `Module Def`
   
.. method:: get_module_items(module, only_dt=0):

   Returns a list of items that constitute a modules. Returns
   
   * Roles
   * Pages
   * DocTypes
   * DocType Mappers
   * Search Criterias
   
   + custom list of items in `Module Def`