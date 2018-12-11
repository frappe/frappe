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

test_records = frappe.get_test_records('Blog Post')

class TestAuthorizations(unittest.TestCase):
    def setUp(self):
        frappe.set_user('Administrator')
        test_users = [{'doctype': 'User', 'first_name': 'test-user1', 'email': 'test11@b.c', 'send_welcome_email': 0,'gender':'Male'},
                      {'doctype': 'User', 'first_name': 'test-user2', 'email': 'test12@b.c', 'send_welcome_email': 0,'gender':'Female'}]
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
        todo = frappe.get_doc({'doctype': 'ToDo', 'description': 'test-todo1', 'owner': 'test11@b.c'})
        post = frappe.get_doc("Blog Post", "-test-blog-post")
        doctype_todo = frappe.get_doc('DocType', 'ToDo')
        doctype_todo.set('authorization_objects', [])
        doctype_todo.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test_role1', force=1, ignore_permissions=1)
        frappe.db.commit()
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test_role1',
                        'authorization': [{'authorization_object': 's_doctype', 'auth_field': 'act', 'value_from': '*'},
                                          {'authorization_object': 's_doctype', 'auth_field': 's_doctype',
                                           'value_from': 'ToDo'}]}
                       ).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test_role1')
        frappe.set_user('test11@b.c')

        self.assertTrue(todo.has_permission("read"))
        self.assertFalse(post.has_permission("read"))

        frappe.set_user('Administrator')
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test_role1')
        frappe.delete_doc('Role', 'test-role1', ignore_permissions=1, force=1)

    def test_multi_action_authorization(self):
        post = frappe.get_doc("Blog Post", "-test-blog-post")
        post1 = frappe.get_doc("Blog Post", "-test-blog-post-1")
        frappe.delete_doc('Authorization Object', 'test-blog_category', force=1, ignore_permissions=1)
        frappe.db.commit()
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-blog_category',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'blog_category'}]}).insert(ignore_permissions=1)
        doctype_blog = frappe.get_doc('DocType', 'Blog Post')
        doctype_blog.set('authorization_objects', [{'authorization_object': 'test-blog_category'}])
        doctype_blog.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-multi_action', force=1, ignore_permissions=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-multi_action',
                        'authorization': [
                            {'authorization_id': '1', 'authorization_object': 'test-blog_category', 'auth_field': 'act',
                             'value_from': '11'},
                            {'authorization_id': '1', 'authorization_object': 'test-blog_category',
                             'auth_field': 'blog_category', 'value_from': '*'},
                            {'authorization_id': '2', 'authorization_object': 'test-blog_category',
                             'auth_field': 'act', 'value_from': '21'},
                            {'authorization_id': '2', 'authorization_object': 'test-blog_category',
                             'auth_field': 'blog_category', 'value_from': '_Test Blog Category 1'}]}
                       ).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-multi_action')
        frappe.set_user('test11@b.c')

        self.assertTrue(post.has_permission("read"))
        self.assertTrue(post1.has_permission("read"))
        self.assertFalse(post.has_permission("create"))
        self.assertTrue(post1.has_permission("create"))

        frappe.set_user('Administrator')        
        doctype_blog.set('authorization_objects', [])
        doctype_blog.save(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-multi_action')
        frappe.delete_doc('Role', 'test-role-multi_action', ignore_permissions=1, force=1)

    def test_mandatory_auth_obj(self):
        post = frappe.get_doc("Blog Post", "-test-blog-post")
        frappe.delete_doc('Authorization Object', 'test-blog_category', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-blog_category',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'blog_category'}]}).insert(ignore_permissions=1)
        doctype_blog = frappe.get_doc('DocType', 'Blog Post')
        doctype_blog.set('authorization_objects', [{'authorization_object': 'test-blog_category', 'mandatory': '1'}])
        doctype_blog.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-mandatory', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-mandatory',
                        'authorization': [
                            {'authorization_object': 'test-blog_category', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 'test-blog_category', 'auth_field': 'blog_category',
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
        user.add_roles('test-role-mandatory')
        user = frappe.get_doc('User', 'test12@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-s_doctype')

        frappe.set_user('test11@b.c')
        self.assertTrue(post.has_permission("read"))

        frappe.set_user('test12@b.c')        
        self.assertFalse(post.has_permission("read"))

        doctype_blog.set('authorization_objects', [{'authorization_object': 'test-blog_category', 'mandatory': '0'}])
        frappe.clear_cache('test12@b.c')
        doctype_blog.save(ignore_permissions=1)        
        self.assertTrue(post.has_permission("read"))

        frappe.set_user('Administrator')
        doctype_blog.set('authorization_objects', [])
        doctype_blog.save(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-mandatory')
        user = frappe.get_doc('User', 'test12@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-s_doctype')
        frappe.delete_doc('Role', 'test-role-mandatory', ignore_permissions=1, force=1)
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
                             'value_from': '$user.name'},
			    {'authorization_object': 's_doctype', 'auth_field': 'act', 'value_from': '11'},
                               {'authorization_object': 's_doctype', 'auth_field': 's_doctype', 'value_from': 'ToDo'}]
                        }).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-multi_or_fields')

        frappe.set_user('test11@b.c')
        self.assertTrue(todo1.has_permission("read"))
        self.assertTrue(todo2.has_permission("read"))

        frappe.db.sql('delete from tabToDo where owner =%(user)s  or assigned_by=%(user)s', {'user': 'test11@b.c'})
        todo1.insert(ignore_permissions=1)
        todo2.insert(ignore_permissions=1)        
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
        frappe.db.set_value("Blog Category", "_Test Blog Category", "published", 0)
        frappe.db.set_value("Blog Category", "_Test Blog Category 1", "published", 1)        
        post1 = frappe.get_doc("Blog Post", "-test-blog-post")
        post2 = frappe.get_doc("Blog Post", "-test-blog-post-1")

        frappe.delete_doc('Authorization Object', 'test-sub_fields', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-sub_fields',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'blog_category.published'}]}).insert(ignore_permissions=1)
        doctype_blog = frappe.get_doc('DocType', 'Blog Post')
        doctype_blog.set('authorization_objects', [{'authorization_object': 'test-sub_fields'}])
        doctype_blog.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-sub_fields', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-sub_fields',
                        'authorization': [
                            {'authorization_object': 'test-sub_fields', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 'test-sub_fields', 'auth_field': 'blog_category.published',
                             'value_from': '0'},
			     {'authorization_object': 's_doctype', 'auth_field': 'act', 'value_from': '11'},
                                {'authorization_object': 's_doctype', 'auth_field': 's_doctype', 'value_from': '*'}]
                        }).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-sub_fields')

        frappe.set_user('test11@b.c')
        self.assertTrue(post1.has_permission("read"))
        self.assertFalse(post2.has_permission("read"))

        self.assertTrue(len(frappe.get_list('Blog Post')) == 1)
        frappe.set_user('Administrator')
        doctype_blog.set('authorization_objects', [])
        doctype_blog.save(ignore_permissions=1)
        frappe.delete_doc('Authorization Object', 'test-sub_fields', ignore_permissions=1, force=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-sub_fields')
        frappe.delete_doc('Role', 'test-role-sub_fields', ignore_permissions=1, force=1)

    def test_field_level(self):
        frappe.set_user('Administrator')
        post = frappe.get_doc("Blog Post", "-test-blog-post")
        post1 = frappe.get_doc("Blog Post", "-test-blog-post-1")

        frappe.delete_doc('Authorization Object', 'test-field_level', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Authorization Object', 'description': 'test-field_level',
                        'auth_field': [{'fieldname': 'act'},
                                       {'fieldname': 'blog_category'}]}).insert(ignore_permissions=1)
        doctype_blog = frappe.get_doc('DocType', 'Blog Post')
        for field in doctype_blog.get('fields'):
            if field.fieldname in ['blogger', 'content']:
                field.authorization_object = 'test-field_level'
        doctype_blog.save(ignore_permissions=1)
        frappe.delete_doc('Role', 'test-role-field_level', ignore_permissions=1, force=1)
        frappe.get_doc({'doctype': 'Role', 'role_name': 'test-role-field_level',
                        'authorization': [
                            {'authorization_object': 'test-field_level', 'auth_field': 'act', 'value_from': '11'},
                            {'authorization_object': 'test-field_level', 'auth_field': 'blog_category',
                             'value_from': '_Test Blog Category 1'}]
                        }).insert(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.add_roles('test-role-field_level')

        frappe.set_user('test11@b.c')
        self.assertTrue(bool(post1.content))
        post1.apply_fieldlevel_read_permissions()
        self.assertTrue(bool(post1.content))
        self.assertTrue(bool(post.content))
        post.apply_fieldlevel_read_permissions()
        self.assertFalse(bool(post.content))

        frappe.set_user('Administrator')
        for field in doctype_blog.get('fields'):
            if field.fieldname in ['blogger', 'content']:
                field.authorization_object = ''
        doctype_blog.save(ignore_permissions=1)
        user = frappe.get_doc('User', 'test11@b.c')
        user.flags.ignore_permissions = 1
        user.remove_roles('test-role-field_level')
        frappe.delete_doc('Role', 'test-role-field_level', ignore_permissions=1, force=1)
