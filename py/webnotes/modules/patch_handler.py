"""
	Execute Patch Files

	Patch files usually lie in the "patches" module specified by "modules_path" in defs.py

	To run directly
	
	python lib/wnf.py patch patch1, patch2 etc
	python lib/wnf.py patch -f patch1, patch2 etc
	
	where patch1, patch2 is module name
"""
import unittest
import sys
import os
import traceback
import webnotes
import webnotes.defs
import webnotes.utils
import webnotes.utils.email_lib
from webnotes.db import Database


class PatchHandler:
	def __init__(self, **kwargs):
		"""
			Gets connection to database

			Arguments can be:
				* db_name
				* verbose --> to enabled printing
		"""
		self.verbose = kwargs.get('verbose')
		try:
			self.db_name = kwargs.get('db_name')
			webnotes.conn = Database(user=self.db_name)
			webnotes.conn.use(self.db_name)
			if not (webnotes.session and webnotes.session['user']):
				webnotes.session = {'user': 'Administrator'}
		except Exception, e:
			self.log(log_type='error', msg=webnotes.getTraceback())
			raise e


	def run_patch(self, **kwargs):
		"""
			Run a patch on a db

			Arguments can be:
				* patch_module
				* patch_file
				* force

			* It gets a connection to the db having name db_name
			  and assigns the connection to webnotes.conn
			* If force == 0, it checks if the patch is already executed or not
			* It imports patch_file from patch_module
			* It runs the execute function of patch_file
		"""
		try:
			patch_module = kwargs.get('patch_module', 'patches')
			patch_file = kwargs.get('patch_file')			
			module_file = str(patch_module) + "." + str(patch_file)
			executed_patches = [p['patch'] for p in self.get_executed_patch_list()]
			
			if kwargs.get('force') or module_file not in executed_patches:
				webnotes.conn.begin()
				
				patch = __import__(module_file, fromlist=True)
				getattr(patch, 'execute')()

				webnotes.conn.commit()
				self.log(log_type='success', patch_module=patch_module, patch_file=patch_file)
		
		except Exception, e:
			webnotes.conn.rollback()
			self.log(log_type='error', patch_module=patch_module, patch_file=patch_file)


	def reload(self, **kwargs):
		"""
			Reloads a particular doc in the system

			Arguments can be:
				* module
				* doc_type
				* doc_name
		"""
		try:
			self.block_user(True, msg="Patches are being executed in the system. Please try again in a few minutes.")
			module = kwargs.get('module')
			doc_type, doc_name = kwargs.get('doc_type'), kwargs.get('doc_name')
			reload_string = 'Module: %s, DocType: %s, DocName: %s' % (module, doc_type, doc_name)
			
			from webnotes.modules.module_manager import reload_doc
			reload_doc(module, doc_type, doc_name)
			
			self.log(log_type='info', msg='Reload successful. ' + reload_string)
		except Exception, e:
			self.log(log_type='error', msg='Reload error. ' + reload_string)
		finally:
			self.block_user(False)


	def get_executed_patch_list(self):
		"""
			Gets a list of dict of patches already executed in a db
			The list is in chronological order
		"""
		try:
			return webnotes.conn.sql("""\
				SELECT * from __PatchLog
				ORDER BY applied_on ASC""", as_dict=1)
		except Exception, e:
			try:
				if e.args[0]==1146:
					self.create_patch_log_table()
					return []
				else:
					self.log(log_type='error')
			except Exception, e:
				self.log(log_type='error')


	def run(self, **kwargs):
		"""
			Runs a patch on a db

			Arguments can be:
				* Either one of 
					* patch_list
						--> List of dict containing:
							+ patch_module
							+ patch_file (!Mandatory)
					* force --> True/False (Only application if patch_list)
				* run_latest --> True/False

			Before beginning, block user
			After completion, unblock user
		"""
		self.block_user(True, msg="Patches are being executed in the system. Please try again in a few minutes.")

		if kwargs.get('patch_list'):
			for patch in kwargs.get('patch_list'):
				self.run_patch(patch_module=patch.get('patch_module', 'patches'), patch_file=patch.get('patch_file'), force=kwargs.get('force'))

		elif kwargs.get('run_latest'):
			try:
				from patches.patch_list import patch_list
				for patch in patch_list:
					self.run_patch(patch_module=patch.get('patch_module', 'patches'), patch_file=patch.get('patch_file'))
			except Exception, e:
				self.log(log_type='error')


		self.block_user(False)

		webnotes.conn.close()

	
	def log(self, **kwargs):
		"""
			Logs successful patches in the database table __PatchLog
			
			Logs exceptions in patches.patch.log

			Also, if self.verbose is true, then it prints what gets logged

			Arguments can be:
				* log_type = success/error/info
				* patch_module
				* patch_file
				* msg
		"""
		log_type = kwargs.get('log_type')
		patch_module = kwargs.get('patch_module')
		patch_file = kwargs.get('patch_file')
		patch = str(patch_module) + "." + str(patch_file)

		if log_type == 'success':
			webnotes.conn.begin()
			webnotes.conn.sql("""\
				INSERT INTO `__PatchLog`
				VALUES (%s, now())""", patch)
			webnotes.conn.commit()
			if self.verbose: print 'Patch: %s applied successfully on %s' % (patch, str(self.db_name))
	
		elif log_type == 'error' or log_type == 'info':
			args = {
				'log_type': log_type,
				'patch_module': patch_module,
				'patch_file': patch_file,
				'msg': kwargs.get('msg')
			}
			patch_msg = self.write_log(**args)
			if self.verbose: print patch_msg
		


	def write_log(self, **kwargs):
		"""
			Write error/info details into patch.log file

			Arguments can be:
				* log_type = error/info
				* patch_module
				* patch_file
				* msg
		"""

		log_type = kwargs.get('log_type')
		patch_module = kwargs.get('patch_module')
		patch_file = kwargs.get('patch_file')
		msg = kwargs.get('msg')
		try:
			company = str(webnotes.utils.get_defaults().get('company'))
		except Exception, e:
			company = None

		patch_log = open(os.path.join(webnotes.defs.modules_path, 'patches', 'patch.log'), 'a')
		patch_msg = "\n" + (log_type=='error' and "[Error] " or "[Info] ") + \
			(company and ('Company: ' + company + " | ") or "Company: Unknown | ") + \
			'DB Name: ' + str(self.db_name) + "\n" + \
			(patch_module and \
				("Patch Module: " + patch_module + " | Patch File: " + patch_file + "\n") \
				or "") + \
			(msg and ("Message: " + str(msg) + "\n") or "") + \
			(log_type=='error' and ("\n" + webnotes.getTraceback() + "\n") or "")
		patch_log.write(patch_msg)
		patch_log.close()
		try:
			if log_type=='error' and getattr(webnotes.defs, 'admin_email_notification', 0):
				webnotes.utils.email_lib.sendmail(\
					recipients=getattr(webnotes.defs, 'admin_email_address', 'developers@erpnext.com'), \
					sender='exception+patches@erpnext.com', \
					subject='Patch Error' + \
						(patch_module and (": " + patch_module + "." + patch_file) or ""), \
					msg=patch_msg,
					reply_to='support@erpnext.com',
					from_defs=1
				)
		except Exception, e:
			print e
		finally:
			return patch_msg


	def create_patch_log_table(self):
		"""
			Create __PatchLog table
		"""
		webnotes.conn.sql("""\
			CREATE TABLE IF NOT EXISTS `__PatchLog` (
				patch TEXT,
				applied_on DATETIME
			)""")
		self.log(log_type='info', msg='Table __PatchLog created successfully')


	def block_user(self, block, **kwargs):
		"""
			Block user when patches are being applied

			Arguments can be:
				* block --> True/False (Mandatory!)
				* msg --> Message to be displayed to user
		"""
		webnotes.conn.begin()

		if block:
			webnotes.conn.set_global('__session_status', 'stop')
			webnotes.conn.set_global('__session_status_message', kwargs.get('msg'))
		else:
			webnotes.conn.set_global('__session_status', None)
			webnotes.conn.set_global('__session_status_message', None)

		webnotes.conn.commit()


class TestPatchHandler(unittest.TestCase):
	"""
		Tests patch handler functions
	"""
	def setUp(self):
		self.patch_module = 'patches'
		self.patch_file = 'reload_print_format'
		webnotes.conn = None
		self.patch_list = [
			{
				'patch_module': 'patches',
				'patch_file': 'reload_project_task'
			},
			{
				'patch_module': 'patches',
				'patch_file': 'reload_print_format'
			}
		]

	
	def tearDown(self):
		pass

	
	def test_run_patch(self):
		self.ph = PatchHandler(db_name='frappe', verbose=1)
		#self.ph.run_patch(patch_module=self.patch_module, patch_file=self.patch_file, force=1)


	def test_run(self):
		self.ph = PatchHandler(db_name='frappe', verbose=1)
		self.ph.run(patch_list=self.patch_list)
		self.ph.run(run_latest=True)

	
	def test_reload(self):
		self.ph = PatchHandler(db_name='frappe', verbose=1)
		self.ph.reload(module='Core', doc_type='DocType', doc_name='Print Format')


