# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
#from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
#from selenium.common.exceptions import TimeoutException
import time
import signal
import os, sys
import frappe

class TestDriver(object):
	def __init__(self, host=None, port='8000'):
		self.host = host
		self.port = port
		self.driver = webdriver.Chrome()
		self.driver.set_window_size(1080,800)
		self.cur_route = None
		self.logged_in = False

	@property
	def localhost(self):
		return "{host}:{port}".format(host=frappe.local.site, port=self.port)

	def get(self, url):
		return self.driver.get(os.path.join(self.localhost, url))

	def start(self):
		def signal_handler(signal, frame):
			self.close()
			sys.exit(0)
		signal.signal(signal.SIGINT, signal_handler)

	def close(self):
		if self.driver:
			self.driver.quit()
		self.driver = None

	def login(self, wait_for_id="#page-desktop"):
		if self.logged_in:
			return
		self.get('login')
		self.wait_for("#login_email")
		self.set_input("#login_email", "Administrator")
		self.set_input("#login_password", "admin", key=Keys.RETURN)
		self.wait_for(wait_for_id)
		self.logged_in = True

	def set_input(self, selector, text, key=None):
		elem = self.find(selector)[0]
		elem.clear()
		elem.send_keys(text)
		if key:
			time.sleep(0.5)
			elem.send_keys(key)
			time.sleep(0.2)

	def find(self, selector, everywhere=False, xpath=None):
		if xpath:
			return self.driver.find_elements_by_x_path(xpath)
		else:
			if self.cur_route and not everywhere:
				selector = self.cur_route + " " + selector
			return self.driver.find_elements_by_css_selector(selector)

	def wait_for(self, selector=None, everywhere=False, timeout=20, xpath=None):
		if self.cur_route and not everywhere:
			selector = self.cur_route + " " + selector

		time.sleep(0.5)

		if selector:
			_by = By.CSS_SELECTOR
		if xpath:
			_by = By.XPATH
			selector = xpath

		elem = self.get_wait(timeout).until(
			EC.presence_of_element_located((_by, selector)))
		return elem

	def get_wait(self, timeout=20):
		return WebDriverWait(self.driver, timeout)

	def scroll_to(self, selector):
		self.execute_script("frappe.ui.scroll('{0}')".format(selector))

	def set_route(self, *args):
		self.execute_script('frappe.set_route({0})'\
			.format(', '.join(['"{0}"'.format(r) for r in args])))

		self.wait_for(xpath='//div[@data-page-route="{0}"]'.format('/'.join(args)), timeout=4)

	def click_primary_action(self):
		selector = ".page-actions .primary-action"
		self.scroll_to(selector)
		self.wait_till_clickable(selector).click()
		self.wait_for_ajax()

	def wait_till_clickable(self, selector):
		if self.cur_route:
			selector = self.cur_route + " " + selector
		return self.get_wait().until(EC.element_to_be_clickable(
			(By.CSS_SELECTOR, selector)))

	def execute_script(self, js):
		self.driver.execute_script(js)

	def wait_for_ajax(self):
		self.wait_for('body[data-ajax-state="complete"]', True)

# def go_to_module(module_name, item=None):
# 	global cur_route
#
# 	# desktop
# 	find(".navbar-home", True)[0].click()
# 	cur_route = None
# 	wait("#page-desktop")
#
# 	page = "Module/" + module_name
# 	m = find('#page-desktop [data-link="{0}"] .app-icon'.format(page))
# 	if not m:
# 		page = "List/" + module_name
# 		m = find('#page-desktop [data-link="{0}"] .app-icon'.format(page))
# 	if not m:
# 		raise Exception("Module {0} not found".format(module_name))
#
# 	m[0].click()
# 	wait_for_page(page)
#
# 	if item:
# 		elem = find('[data-label="{0}"]'.format(item))[0]
# 		elem.click()
# 		page = elem.get_attribute("data-route")
# 		wait_for_page(page)
#
# def new_doc(module, doctype):
# 	go_to_module(module, doctype)
# 	primary_action()
# 	wait_for_page("Form/" + doctype)
#
# def add_child(fieldname):
# 	find('[data-fieldname="{0}"] .grid-add-row'.format(fieldname))[0].click()
# 	wait('[data-fieldname="{0}"] .form-grid'.format(fieldname))
#
# def done_add_child(fieldname):
# 	selector = '[data-fieldname="{0}"] .grid-row-open .btn-success'.format(fieldname)
# 	scroll_to(selector)
# 	wait_till_clickable(selector).click()
#
# def set_field(fieldname, value, fieldtype="input"):
# 	_driver.switch_to.window(_driver.current_window_handle)
# 	selector = '{0}[data-fieldname="{1}"]'.format(fieldtype, fieldname)
# 	set_input(selector, value, key=Keys.TAB)
# 	wait_for_ajax()
#
# def set_select(fieldname, value):
# 	select = Select(find('select[data-fieldname="{0}"]'.format(fieldname))[0])
# 	select.select_by_value(value)
# 	wait_for_ajax()
#
#
# def wait_for_page(name):
# 	global cur_route
# 	cur_route = None
# 	route = '[data-page-route="{0}"]'.format(name)
# 	wait_for_ajax()
# 	elem = wait(route)
# 	wait_for_ajax()
# 	cur_route = route
# 	return elem
#
#
# def wait_till_visible(selector):
# 	if cur_route:
# 		selector = cur_route + " " + selector
# 	return get_wait().until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
#
#
# def wait_for_state(state):
# 	return wait(cur_route + '[data-state="{0}"]'.format(state), True)
#
#
