# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
import unittest
from frappe.utils import random_string
from frappe.model.workflow import apply_workflow, WorkflowTransitionError, WorkflowPermissionError, get_common_transition_actions
from frappe.test_runner import make_test_records
from frappe.query_builder import DocType


class TestWorkflow(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		make_test_records("User")

	def setUp(self):
		self.workflow = create_todo_workflow()
		frappe.set_user('Administrator')
		if self._testMethodName == "test_if_workflow_actions_were_processed_using_user":
			if not frappe.db.has_column('Workflow Action', 'user'):
				# mariadb would raise this statement would create an implicit commit
				# if we do not commit before alter statement
				# nosemgrep
				frappe.db.commit()
				frappe.db.multisql({
					'mariadb': 'ALTER TABLE `tabWorkflow Action` ADD COLUMN user varchar(140)',
					'postgres': 'ALTER TABLE "tabWorkflow Action" ADD COLUMN "user" varchar(140)'
				})
				frappe.cache().delete_value('table_columns')

	def tearDown(self):
		frappe.delete_doc('Workflow', 'Test ToDo')
		if self._testMethodName == "test_if_workflow_actions_were_processed_using_user":
			if frappe.db.has_column('Workflow Action', 'user'):
				# mariadb would raise this statement would create an implicit commit
				# if we do not commit before alter statement
				# nosemgrep
				frappe.db.commit()
				frappe.db.multisql({
					'mariadb': 'ALTER TABLE `tabWorkflow Action` DROP COLUMN user',
					'postgres': 'ALTER TABLE "tabWorkflow Action" DROP COLUMN "user"'
				})
				frappe.cache().delete_value('table_columns')

	def test_default_condition(self):
		'''test default condition is set'''
		todo = create_new_todo()

		# default condition is set
		self.assertEqual(todo.workflow_state, 'Pending')

		return todo

	def test_approve(self, doc=None):
		'''test simple workflow'''
		todo = doc or self.test_default_condition()

		apply_workflow(todo, 'Approve')
		# default condition is set
		self.assertEqual(todo.workflow_state, 'Approved')
		self.assertEqual(todo.status, 'Closed')

		return todo

	def test_wrong_action(self):
		'''Check illegal action (approve after reject)'''
		todo = self.test_approve()

		self.assertRaises(WorkflowTransitionError, apply_workflow, todo, 'Reject')

	def test_workflow_condition(self):
		'''Test condition in transition'''
		self.workflow.transitions[0].condition = 'doc.status == "Closed"'
		self.workflow.save()

		# only approve if status is closed
		self.assertRaises(WorkflowTransitionError, self.test_approve)

		self.workflow.transitions[0].condition = ''
		self.workflow.save()

	def test_get_common_transition_actions(self):
		todo1 = create_new_todo()
		todo2 = create_new_todo()
		todo3 = create_new_todo()
		todo4 = create_new_todo()

		actions = get_common_transition_actions([todo1, todo2, todo3, todo4], 'ToDo')
		self.assertSetEqual(set(actions), set(['Approve', 'Reject']))

		apply_workflow(todo1, 'Reject')
		apply_workflow(todo2, 'Reject')
		apply_workflow(todo3, 'Approve')

		actions = get_common_transition_actions([todo1, todo2, todo3], 'ToDo')
		self.assertListEqual(actions, [])

		actions = get_common_transition_actions([todo1, todo2], 'ToDo')
		self.assertListEqual(actions, ['Review'])

	def test_if_workflow_actions_were_processed_using_role(self):
		frappe.db.delete("Workflow Action")
		user = frappe.get_doc('User', 'test2@example.com')
		user.add_roles('Test Approver', 'System Manager')
		frappe.set_user('test2@example.com')

		doc = self.test_default_condition()
		workflow_actions = frappe.get_all('Workflow Action', fields=['*'])
		self.assertEqual(len(workflow_actions), 1)

		# test if status of workflow actions are updated on approval
		self.test_approve(doc)
		user.remove_roles('Test Approver', 'System Manager')
		workflow_actions = frappe.get_all('Workflow Action', fields=['status'])
		self.assertEqual(len(workflow_actions), 1)
		self.assertEqual(workflow_actions[0].status, 'Completed')
		frappe.set_user('Administrator')

	def test_if_workflow_actions_were_processed_using_user(self):
		frappe.db.delete("Workflow Action")

		user = frappe.get_doc('User', 'test2@example.com')
		user.add_roles('Test Approver', 'System Manager')
		frappe.set_user('test2@example.com')

		doc = self.test_default_condition()
		workflow_actions = frappe.get_all('Workflow Action', fields=['*'])
		self.assertEqual(len(workflow_actions), 1)

		# test if status of workflow actions are updated on approval
		WorkflowAction = DocType("Workflow Action")
		WorkflowActionPermittedRole = DocType("Workflow Action Permitted Role")
		frappe.qb.update(WorkflowAction).set(WorkflowAction.user, 'test2@example.com').run()
		frappe.qb.update(WorkflowActionPermittedRole).set(WorkflowActionPermittedRole.role, '').run()

		self.test_approve(doc)

		user.remove_roles('Test Approver', 'System Manager')
		workflow_actions = frappe.get_all('Workflow Action', fields=['status'])
		self.assertEqual(len(workflow_actions), 1)
		self.assertEqual(workflow_actions[0].status, 'Completed')
		frappe.set_user('Administrator')


	def test_update_docstatus(self):
		todo = create_new_todo()
		apply_workflow(todo, 'Approve')

		self.workflow.states[1].doc_status = 0
		self.workflow.save()
		todo.reload()
		self.assertEqual(todo.docstatus, 0)
		self.workflow.states[1].doc_status = 1
		self.workflow.save()
		todo.reload()
		self.assertEqual(todo.docstatus, 1)

		self.workflow.states[1].doc_status = 0
		self.workflow.save()

	def test_if_workflow_set_on_action(self):
		self.workflow.states[1].doc_status = 1
		self.workflow.save()
		todo = create_new_todo()
		self.assertEqual(todo.docstatus, 0)
		todo.submit()
		self.assertEqual(todo.docstatus, 1)
		self.assertEqual(todo.workflow_state, 'Approved')

		self.workflow.states[1].doc_status = 0
		self.workflow.save()

	def test_syntax_error_in_transition_rule(self):
		self.workflow.transitions[0].condition = 'doc.status =! "Closed"'

		with self.assertRaises(frappe.ValidationError) as se:
			self.workflow.save()

		self.assertTrue("invalid python code" in str(se.exception).lower(),
				msg="Python code validation not working")


def create_todo_workflow():
	if frappe.db.exists('Workflow', 'Test ToDo'):
		frappe.delete_doc('Workflow', 'Test ToDo')

	if not frappe.db.exists('Role', 'Test Approver'):
		frappe.get_doc(dict(doctype='Role',
			role_name='Test Approver')).insert(ignore_if_duplicate=True)
	workflow = frappe.new_doc('Workflow')
	workflow.workflow_name = 'Test ToDo'
	workflow.document_type = 'ToDo'
	workflow.workflow_state_field = 'workflow_state'
	workflow.is_active = 1
	workflow.send_email_alert = 0
	workflow.append('states', dict(
		state = 'Pending', allow_edit = 'All'
	))
	workflow.append('states', dict(
		state = 'Approved', allow_edit = 'Test Approver',
		update_field = 'status', update_value = 'Closed'
	))
	workflow.append('states', dict(
		state = 'Rejected', allow_edit = 'Test Approver'
	))
	workflow.append('transitions', dict(
		state = 'Pending', action='Approve', next_state = 'Approved',
		allowed='Test Approver', allow_self_approval= 1
	))
	workflow.append('transitions', dict(
		state = 'Pending', action='Reject', next_state = 'Rejected',
		allowed='Test Approver', allow_self_approval= 1
	))
	workflow.append('transitions', dict(
		state = 'Rejected', action='Review', next_state = 'Pending',
		allowed='All', allow_self_approval= 1
	))
	workflow.insert(ignore_permissions=True)

	return workflow

def create_new_todo():
	return frappe.get_doc(dict(doctype='ToDo', description='workflow ' + random_string(10))).insert()

class TestVotingWorkflow(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		make_test_records("User")
		create_extra_states()		

	def setUp(self):
		self.workflow = create_voting_workflow()
		frappe.set_user('Administrator')

	def tearDown(self):
		frappe.delete_doc('Workflow', 'Test Voting')
		pass
	

	def test_voting_progress(self):
		doc = create_new_voting()
		
		# somehow, when running tests for this DocType, you can end up with 
		# the "Administrator" account showing up twice in the 'Test Voter' 
		# Role.  This shouldn't be possible, but it is happening.  So fix it.
		# these two lines don't seem work to get rid of Administrator being in the group:
		#user = frappe.get_doc('User', 'Administrator')
		#user.remove_roles('Test Voter')
		# so use a bigger hammer:
		#frappe.db.sql("delete from `tabHas Role` where parent = 'Administrator' and parentfield = 'roles' and parenttype = 'User' and role = 'Test Voter'")
		frappe.db.delete('Has Role', {'parent': 'Administrator'
			, 'parentfield': 'roles'
			, 'parenttype': 'User'
			, 'role': 'Test Voter'})
		user1 = frappe.get_doc('User', 'test1@example.com')
		user1.add_roles('Test Voter')
		user2 = frappe.get_doc('User', 'test2@example.com')
		user2.add_roles('Test Voter')
		user3 = frappe.get_doc('User', 'test3@example.com')
		user3.add_roles('Test Voter')
		user4 = frappe.get_doc('User', 'test4@example.com')
		user4.add_roles('Test Voter')
		
		# two votes (50% of 4 members) to get from "Pending" to "In Process"
		frappe.set_user('test1@example.com')
		apply_workflow(doc, 'Approve')
		self.assertEqual(doc.workflow_state, "Pending")
		# voting twice shouldn't change things
		frappe.set_user('test1@example.com')
		#apply_workflow(doc, 'Approve')
		self.assertRaises(WorkflowTransitionError, apply_workflow, doc, 'Approve')
		self.assertEqual(doc.workflow_state, "Pending")
		# second vote
		frappe.set_user('test2@example.com')
		apply_workflow(doc, 'Approve')
		self.assertEqual(doc.workflow_state, "In Process")
		# three votes to get from "In Process" to "Approved"
		frappe.set_user('test1@example.com')
		apply_workflow(doc, 'Approve')
		self.assertEqual(doc.workflow_state, "In Process")
		# voting twice shouldn't change things
		frappe.set_user('test1@example.com')
		#apply_workflow(doc, 'Approve')
		self.assertRaises(WorkflowTransitionError, apply_workflow, doc, 'Approve')
		self.assertEqual(doc.workflow_state, "In Process")
		# second vote
		frappe.set_user('test2@example.com')
		apply_workflow(doc, 'Approve')
		self.assertEqual(doc.workflow_state, "In Process")
		# third vote
		frappe.set_user('test3@example.com')
		apply_workflow(doc, 'Approve')
		self.assertEqual(doc.workflow_state, "Approved")
		frappe.set_user('Administrator')


def create_voting_workflow():
	# designed for a group of 4.  Administrator was showing up in the group, but I used the
	# big hammer to remove it.
	# starts at "Pending", goes to "In Process" with 50%, goes to "Approved" with 3 individuals
	if frappe.db.exists('Workflow', 'Test Tag'):
		frappe.db.delete('Workflow Action Vote', {'workflow': 'Test Tag'})
		frappe.delete_doc('Workflow', 'Test Tag')

	if not frappe.db.exists('Role', 'Test Voter'):
		frappe.get_doc(dict(doctype='Role',
			role_name='Test Voter')).insert(ignore_if_duplicate=True)
	workflow = frappe.new_doc('Workflow')
	workflow.workflow_name = 'Test Tag'
	workflow.document_type = 'Tag'
	workflow.workflow_state_field = 'workflow_state'
	workflow.is_active = 1
	workflow.send_email_alert = 0
	workflow.append('states', dict(
		state = 'Pending', allow_edit = 'All'
	))
	workflow.append('states', dict(
		state = 'In Process', allow_edit = 'Test Voter'
	))
	workflow.append('states', dict(
		state = 'Approved', allow_edit = 'Test Voter',
		update_field = 'status', update_value = 'Closed'
	))
	workflow.append('states', dict(
		state = 'Rejected', allow_edit = 'Test Voter'
	))
	workflow.append('transitions', dict(
		state = 'Pending', action='Approve', next_state = 'In Process',
		allowed='Test Voter', allow_self_approval= 1, quantity = 50, unit_of_measure = 'Percent'
	))
	workflow.append('transitions', dict(
		state = 'In Process', action='Approve', next_state = 'Approved',
		allowed='Test Voter', allow_self_approval= 1, quantity = 3, unit_of_measure = 'Individual'
	))
	workflow.append('transitions', dict(
		state = 'Pending', action='Reject', next_state = 'Rejected',
		allowed='Test Voter', allow_self_approval= 1
	))
	workflow.append('transitions', dict(
		state = 'In Process', action='Reject', next_state = 'Rejected',
		allowed='Test Voter', allow_self_approval= 1
	))
	workflow.append('transitions', dict(
		state = 'Rejected', action='Review', next_state = 'Pending',
		allowed='Test Voter', allow_self_approval= 1
	))
	workflow.insert(ignore_permissions=True)

	return workflow

def create_new_voting():
	rnd_str = random_string(10)
	return frappe.get_doc(dict(doctype='Tag', description='workflow ' + rnd_str, name = rnd_str)).insert()

def create_extra_states():
	if not frappe.db.exists('Workflow State', 'In Process'):
		frappe.get_doc(dict(doctype='Workflow State'
			, workflow_state_name='In Process')).insert(ignore_if_duplicate=True)
	