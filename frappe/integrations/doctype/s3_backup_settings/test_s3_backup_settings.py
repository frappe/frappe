# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestS3BackupSettings(unittest.TestCase):
	pass



# class BasicConnectionTest(unittest.TestCase):
#     def test_connection_works(self):
#         # Please add some credentials if necessary
#         connection = boto.connect_s3()
#         # when using unittest, I'm trying to stick to helper methods
#         # because they are more verbose
#         self.assertIsNotNone(connection)


# class AdvancedConnectionTest(unittest.TestCase):
#     def setUp(self):
#         self.connection = boto.connect_s3()

#     def test_bucket_can_be_created(self):
#         bucket = self.create_bucket()
#         self.assertIsNotNone(bucket)
#         self.assertEqual(len(bucket.get_all_keys()), 0)

#     def test_keys_can_be_created(self):
#         bucket = self.create_bucket()
#         key = self.create_key(bucket, "mykey")
#         key.set_contents_from_string("Hello World!")
#         sleep(2)
#         contents = key.get_contents_as_string()
#         self.assertEqual(contents, "Hello World!")

#     def create_bucket(self):
#         bucket = self.connection.create_bucket('boto-demo-%s' % int(time()))
#         self.addCleanup(bucket.delete)
#         return bucket

#     def create_key(self, bucket, name):
#         key = bucket.new_key('mykey')
#         self.addCleanup(key.delete)
#         return key