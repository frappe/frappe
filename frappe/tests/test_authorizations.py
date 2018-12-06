# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import frappe.defaults
import unittest
import json
import frappe.model.meta
from frappe.utils import nowdate
from frappe.authorizations import (get_user_authorizations, get_authorizations, get_auth_objs,
                                   auth_check, get_match_conditions, check_field, match)
from frappe.test_runner import make_test_records_for_doctype


class TestAuthorizations(unittest.TestCase):
    def setUp(self):
        frappe.set_user('Administrator')
        test_users = [{'doctype': 'User', 'first_name': 'test-user1', 'email': 'test11@b.c'},
                      {'doctype': 'User', 'first_name': 'test-user2', 'email': 'test12@b.c'}]
        for user in test_users:
            try:
                frappe.delete_doc('User', user.get('email'), force=1, ignore_permissions=1)
                frappe.get_doc(user).insert(ignore_permissions=1)
            except:
                pass              
        frappe.delete_doc('Authorization Object', 's_doctype', force=1, ignore_permissions=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 's_doctype',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 's_doctype'}]}).insert(ignore_permissions=1)      

    def tearDown(self):
        frappe.delete_doc('User', 'test11@b.c', force=1, ignore_permissions=1)
        frappe.delete_doc('User', 'test12@b.c', force=1, ignore_permissions=1)
        frappe.delete_doc('Authorization Object', 's_doctype', force=1, ignore_permissions=1)

    def test_basic_authorization(self):
        item = frappe.get_doc({'doctype': 'Item', 'item_code': 'test-item1', 'item_group': 'Products'})
        task = frappe.get_doc({'doctype': 'Task', 'name': 'test-task1', 'subject': 'test-task'})
        doctype_item = frappe.get_doc('DocType', 'Item')
        doctype_item.set('authorization_objects', [])
        doctype_item.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test_role1', force=1, ignore_permissions=1)
        frappe.db.commit()
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test_role1',
                        'authorization': [{'authorization_object': 's_doctype', 'auth_field': 'act', 'value_from': '*'},
                                          {'authorization_object': 's_doctype', 'auth_field': 's_doctype',
                                           'value_from': 'Item'}]}
                       ).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test_role1')
        frappe.set_user('test11@b.c')
        print('test_basic authorizations-----')
        print('item read')
        self.assertTrue(item.has_permission("read"))

        print('task read')
        self.assertFalse(task.has_permission("read"))

        frappe.set_user('Administrator')
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test_role1')
        frappe.delete_doc('Role', 'test-role1', ignore_permissions=1, force=1)

    def test_multi_action_authorization(self):
        item1 = frappe.get_doc({'doctype': 'Item', 'item_code': 'test-item1', 'item_group': 'Products'})
        item2 = frappe.get_doc({'doctype': 'Item', 'item_code': 'test-item1', 'item_group': 'Services'})
        frappe.delete_doc('Authorization Object', 'test-item-by-group', force=1, ignore_permissions=1)
        frappe.db.commit()
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-item-by-group',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'item_group'}]}).insert(ignore_permissions=1)
        doctype_item = frappe.get_doc('DocType', 'Item')
        doctype_item.set('authorization_objects', [{'authorization_object': 'test-item-by-group'}])
        doctype_item.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-multi_action', force=1, ignore_permissions=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-multi_action',
                        'authorization': [
                            {'authorization_id': '1', 'authorization_object': 'test-item-by-group', 'auth_field': 'act',
                             'value_from': '11'},
                            {'authorization_id': '1', 'authorization_object': 'test-item-by-group',
                             'auth_field': 'item_group', 'value_from': '*'},
                            {'authorization_id': '2', 'authorization_object': 'test-item-by-group',
                             'auth_field': 'act', 'value_from': '21'},
                            {'authorization_id': '2', 'authorization_object': 'test-item-by-group',
                             'auth_field': 'item_group', 'value_from': 'Services'}]}
                       ).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-multi_action')
        frappe.set_user('test11@b.c')
        print('test multi action atuhorization---')
        print('item1 read:')
        self.assertTrue(item1.has_permission("read"))

        print('item2 read:')
        self.assertTrue(item2.has_permission("read"))
        print('item1 create:')
        self.assertFalse(item1.has_permission("create"))
        print('item2 create:')
        self.assertTrue(item2.has_permission("create"))

        frappe.set_user('Administrator')
        doctype_item = frappe.get_doc('DocType', 'Item')
        doctype_item.set('authorization_objects', [])
        doctype_item.save(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-multi_action')
        frappe.delete_doc('Role', 'test-role-multi_action', ignore_permissions=1, force=1)

    def test_mandatory_auth_obj(self):
        item1 = frappe.get_doc({'doctype': 'Item', 'item_code': 'test-item1', 'item_group': 'Products'})
        frappe.delete_doc('Authorization Object', 'test-item_mandatory', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-item_mandatory',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'item_group'}]}).insert(ignore_permissions=1)
        doctype_item = frappe.get_doc('DocType', 'Item')
        doctype_item.set('authorization_objects', [{'authorization_object': 'test-item_mandatory', 'mandatory': '1'}])
        doctype_item.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-item_mandatory', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-item_mandatory',
                        'authorization': [
                            {'authorization_object': 'test-item_mandatory', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 'test-item_mandatory', 'auth_field': 'item_group',
                             'value_from': '*'}]
                        }).insert(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-s_doctype', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-s_doctype',
                        'authorization': [
                            {'authorization_object': 's_doctype', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 's_doctype', 'auth_field': 's_doctype', 'value_from': '*'}]
                        }).insert(ignore_permissions=1)
        frappe.set_user('Administrator')
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-item_mandatory')
        user = frappe.get_doc('User', 'test12@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-s_doctype')

        frappe.set_user('test11@b.c')
        print('test mandatory authorization---')
        print('item1 read:')
        self.assertTrue(item1.has_permission("read"))

        frappe.set_user('test12@b.c')
        print('user 2 read item1 mandatory object:')
        self.assertFalse(item1.has_permission("read"))

        doctype_item.set('authorization_objects', [{'authorization_object': 'test-item_mandatory', 'mandatory': '0'}])
        frappe.clear_cache('test12@b.c')
        doctype_item.save(ignore_permissions=1)
        print('user2 read item1 optional obj:')
        self.assertTrue(item1.has_permission("read"))

        frappe.set_user('Administrator')
        doctype_item.set('authorization_objects', [])
        doctype_item.save(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-item_mandatory')
        user = frappe.get_doc('User', 'test12@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-s_doctype')
        frappe.delete_doc('Role', 'test-role-item_mandatory', ignore_permissions=1, force=1)
        frappe.delete_doc('Role', 'test-role-s_doctype', ignore_permissions=1, force=1)

    def test_multi_or_fields(self):
        frappe.set_user('Administrator')
        todo1 = frappe.get_doc({'doctype': 'ToDo', 'description': 'test-todo1', 'owner': 'test11@b.c'})
        todo2 = frappe.get_doc({'doctype': 'ToDo', 'description': 'test-todo2', 'assigned_by': 'test11@b.c'})

        frappe.delete_doc('Authorization Object', 'test-multi_or_fields', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-multi_or_fields',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'owner|assigned_by'}]}).insert(ignore_permissions=1)
        doctype_todo = frappe.get_doc('DocType', 'ToDo')
        doctype_todo.set('authorization_objects', [{'authorization_object': 'test-multi_or_fields'}])
        doctype_todo.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-multi_or_fields', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-multi_or_fields',
                        'authorization': [
                            {'authorization_object': 'test-multi_or_fields', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 'test-multi_or_fields', 'auth_field': 'owner|assigned_by',
                             'value_from': '$user.name'}]
                        }).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-multi_or_fields')

        frappe.set_user('test11@b.c')
        print('test multi_or_fields---')
        print('todo1 read:')
        self.assertTrue(todo1.has_permission("read"))

        print('todo2 read:')
        self.assertTrue(todo2.has_permission("read"))

        frappe.db.sql('delete from tabToDo where owner =%(user)s  or assigned_by=%(user)s', {'user': 'test11@b.c'})
        todo1.insert(ignore_permissions=1)
        todo2.insert(ignore_permissions=1)
        print('user1 get_list return 2 records:')
        self.assertTrue(len(frappe.get_list('ToDo')) == 2)
        frappe.db.sql('delete from tabToDo where owner =%(user)s  or assigned_by=%(user)s', {'user': 'test11@b.c'})

        frappe.set_user('Administrator')
        doctype_todo.set('authorization_objects', [])
        doctype_todo.save(ignore_permissions=1)
        frappe.delete_doc('Authorization Object', 'test-multi_or_fields', ignore_permissions=1, force=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-multi_or_fields')
        frappe.delete_doc('Role', 'test-role-multi_or_fields', ignore_permissions=1, force=1)

    def test_sub_fields(self):
        frappe.set_user('Administrator')
        frappe.get_doc(
            {'doctype': 'Customer', 'customer_name': 'test-customer1', 'customer_group': 'Commercial'}).insert(
            ignore_permissions=1)
        frappe.get_doc(
            {'doctype': 'Customer', 'customer_name': 'test-customer2', 'customer_group': 'Individual'}).insert(
            ignore_permissions=1)
        frappe.db.sql('delete from tabItem where name=%(item)s', {'item': 'test-item1'})
        frappe.get_doc(
            {'doctype': 'Item', 'item_code': 'test-item1', 'item_group': 'Services', 'is_stock_item': 0}).insert(
            ignore_permissions=1)
        so1 = frappe.get_doc({'doctype': 'Sales Order', 'customer': 'test-customer1', 'delivery_date': nowdate(),
                              'items': [{'item_code': 'test-item1'}]})
        so2 = frappe.get_doc({'doctype': 'Sales Order', 'customer': 'test-customer2', 'delivery_date': nowdate(),
                              'items': [{'item_code': 'test-item1'}]})
        frappe.get_doc({'doctype': 'Sales Order', 'customer': 'test-customer2', 'delivery_date': nowdate(),
                        'items': [{'item_code': 'test-item1'}]})

        frappe.delete_doc('Authorization Object', 'test-sub_fields', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-sub_fields',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'customer.customer_group'}]}).insert(ignore_permissions=1)
        doctype_so = frappe.get_doc('DocType', 'Sales Order')
        doctype_so.set('authorization_objects', [{'authorization_object': 'test-sub_fields'}])
        doctype_so.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-sub_fields', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-sub_fields',
                        'authorization': [
                            {'authorization_object': 'test-sub_fields', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 'test-sub_fields', 'auth_field': 'customer.customer_group',
                             'value_from': 'Commercial'}]
                        }).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-sub_fields')

        frappe.set_user('test11@b.c')
        print('test sub_fields---')
        print('sales order 1 read:')
        self.assertTrue(so1.has_permission("read"))

        print('sales order 2 read:')
        self.assertFalse(so2.has_permission("read"))

        frappe.db.sql('delete from `tabSales Order` where customer =%(customer1)s  or customer=%(customer2)s',
                      {'customer1': 'test-customer1', 'customer2': 'test-customer2'})
        so1.insert(ignore_permissions=1)
        so2.insert(ignore_permissions=1)
        print('get_list return 1 record:')
        self.assertTrue(len(frappe.get_list('Sales Order')) == 1)
        frappe.db.sql('delete from `tabSales Order` where customer =%(customer1)s  or customer=%(customer2)s',
                      {'customer1': 'test-customer1', 'customer2': 'test-customer2'})

        frappe.set_user('Administrator')
        doctype_so.set('authorization_objects', [])
        doctype_so.save(ignore_permissions=1)
        frappe.delete_doc('Authorization Object', 'test-sub_fields', ignore_permissions=1, force=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-sub_fields')
        frappe.delete_doc('Role', 'test-role-sub_fields', ignore_permissions=1, force=1)

    def test_field_level(self):
        frappe.set_user('Administrator')
        emp1 = frappe.get_doc(
            {'doctype': 'Employee', 'date_of_birth': nowdate(), 'cell_number': '111', 'user_id': 'test11@b.c'})
        emp2 = frappe.get_doc(
            {'doctype': 'Employee', 'date_of_birth': nowdate(), 'cell_number': '222', 'user_id': 'test12@b.c'})

        frappe.delete_doc('Authorization Object', 'test-field_level', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-field_level',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'user_id'}]}).insert(ignore_permissions=1)
        doctype_emp = frappe.get_doc('DocType', 'Employee')
        for field in doctype_emp.get('fields'):
            if field.fieldname in ['date_of_birth', 'cell_number']:
                field.authorization_object = 'test-field_level'
        doctype_emp.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-field_level', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-field_level',
                        'authorization': [
                            {'authorization_object': 'test-field_level', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 'test-field_level', 'auth_field': 'user_id',
                             'value_from': '$user.name'}]
                        }).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-field_level')

        frappe.set_user('test11@b.c')
        print('test field level---')
        print('get employee 1:')
        self.assertTrue(bool(emp1.cell_number))
        emp1.apply_fieldlevel_read_permissions()
        self.assertTrue(bool(emp1.cell_number))
        print('get employee 2:')
        self.assertTrue(bool(emp2.cell_number))
        emp2.apply_fieldlevel_read_permissions()
        self.assertFalse(bool(emp2.cell_number))

        frappe.set_user('Administrator')
        for field in doctype_emp.get('fields'):
            if field.fieldname in ['date_of_birth', 'cell_number']:
                field.authorization_object = ''
        doctype_emp.save(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-field_level')
        frappe.delete_doc('Role', 'test-role-field_level', ignore_permissions=1, force=1)
