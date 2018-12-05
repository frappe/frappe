# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.authorizations import validate_auth_field
from frappe import _

class AuthorizationObject(Document):
	
	def on_update(self):
		if not hasattr(self,'_doc_before_save') or (hasattr(self,'_doc_before_save') and 
				self._doc_before_save and self._doc_before_save.auth_field != self.auth_field):
			auth_key = 'get_auth_objs|%s|%s' % ('auth_obj', self.name)
			frappe.cache().hdel('auth_objs', auth_key)

			for user in frappe.db.sql_list("""select distinct role.parent	from `tabHas Role` role 
        		 	inner join `tabRole Authorization` auth on role.role = auth.parent  	        	
	       			where auth.authorization_object = %s and role.parenttype="User" """, self.name):
				print('auth obj on update, user:', user, ' cacahe cleared')
				frappe.clear_cache(user=user)

	def validate(self):
		for doctype in frappe.db.sql_list("""select distinct parent from `tabDoctype Authorization Object` 
	        	 where authorization_object = %s """, self.name):
			invalid_fields = validate_auth_field(doctype, self)
			if invalid_fields:
				frappe.throw(_('auth fields: %s is not valid field in assigned doctype'
					 %(','.join(invalid_fields), doctype)))


		if len(self.auth_field)>4:
			frappe.throw(_('For performance and easy maintenane consideration, no more than 4 auth fields'))

