# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
#from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
#from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

import time
import signal
import os, sys
import frappe
from ast import literal_eval

class TestDriver(object):
	def __init__(self, port=None):
		self.port = port or frappe.get_site_config().webserver_port or '8000'

		chrome_options = Options()
		capabilities = DesiredCapabilities.CHROME

		if os.environ.get('CI'):
			self.host = 'localhost'
		else:
			self.host = frappe.local.site

		# enable browser logging
		capabilities['loggingPrefs'] = {'browser':'ALL'}

		chrome_options.add_argument('--no-sandbox')
		chrome_options.add_argument('--start-maximized')
		self.driver = webdriver.Chrome(chrome_options=chrome_options,
			desired_capabilities=capabilities, port=9515)

		# self.driver.set_window_size(1080,800)
		self.cur_route = None
		self.logged_in = False

	@property
	def localhost(self):
		return "http://{host}:{port}".format(host=self.host, port=self.port)

	def get(self, url):
		return self.driver.get(os.path.join(self.localhost, url))

	def start(self):
		def signal_handler(signal, frame):
			self.close()
			sys.exit(0)
		signal.signal(signal.SIGINT, signal_handler)

	def refresh(self):
		self.driver.refresh()

	def close(self):
		if self.driver:
			self.driver.quit()
		self.driver = None

	def login(self, wait_for_id="#page-desktop", animate=0, scroll_offset=0):
		if self.logged_in:
			return
		self.get('login')
		self.wait_for("#login_email")
		self.set_input("#login_email", "Administrator")
		self.set_input("#login_password", "admin")
		self.click('.btn-login', animate=animate, offset=scroll_offset)
		self.wait_for(wait_for_id)
		self.logged_in = True

	def set_input(self, selector, text, key=None, xpath=None):
		elem = self.find(selector, xpath=xpath)[0]
		elem.clear()
		elem.send_keys(text)
		if key:
			time.sleep(0.5)
			elem.send_keys(key)
			time.sleep(0.2)

	def set_field(self, fieldname, text):
		elem = self.wait_for(xpath='//input[@data-fieldname="{0}"]'.format(fieldname))
		time.sleep(0.2)
		elem.send_keys(text)

	def set_select(self, fieldname, text):
		elem = self.wait_for(xpath='//select[@data-fieldname="{0}"]'.format(fieldname))
		time.sleep(0.2)
		elem.send_keys(text)

	def set_multicheck(self, fieldname, values):
		for value in values:
			path = '//div[@data-fieldname="{0}"]//span[@data-unit="{1}"]'.format(fieldname, value)
			elem = self.wait_for(xpath=path)
			time.sleep(0.2)
			elem.click()

	def set_text_editor(self, fieldname, text):
		elem = self.wait_for(xpath='//div[@data-fieldname="{0}"]//div[@contenteditable="true"]'.format(fieldname))
		time.sleep(0.2)
		elem.send_keys(text)

	def find(self, selector=None, everywhere=False, xpath=None):
		if xpath:
			return self.driver.find_elements_by_xpath(xpath)
		else:
			if self.cur_route and not everywhere:
				selector = self.cur_route + " " + selector
			return self.driver.find_elements_by_css_selector(selector)

	def wait_for(self, selector=None, everywhere=False, timeout=20, xpath=None, for_invisible=False):
		if self.cur_route and not everywhere:
			selector = self.cur_route + " " + selector

		time.sleep(0.5)

		if selector:
			_by = By.CSS_SELECTOR
		if xpath:
			_by = By.XPATH
			selector = xpath

		try:
			if not for_invisible:
				elem = self.get_wait(timeout).until(
					EC.presence_of_element_located((_by, selector)))
			else:
				elem = self.get_wait(timeout).until(
					EC.invisibility_of_element_located((_by, selector)))
			return elem
		except Exception as e:
			# body = self.driver.find_element_by_id('body_div')
			# print(body.get_attribute('innerHTML'))
			self.print_console()
			raise e

	def wait_for_invisible(self, selector=None, everywhere=False, timeout=20, xpath=None):
		self.wait_for(selector, everywhere, timeout, xpath, True)

	def get_console(self):
		out = []
		for entry in self.driver.get_log('browser'):
			source, line_no, message = entry.get('message').split(' ', 2)

			if message and message[0] in ('"', "'"):
				# message is a quoted/escaped string
				message = literal_eval(message)

			out.append(source + ' ' + line_no)
			out.append(message)
			out.append('-'*40)

		return out

	def print_console(self):
		for line in self.get_console():
			print(line)

	def get_wait(self, timeout=20):
		return WebDriverWait(self.driver, timeout)

	def scroll_to(self, selector, animate=0, offset=0):
		self.execute_script("frappe.ui.scroll('{0}', {1}, {2})".format(selector, animate, offset))

	def set_route(self, *args):
		self.execute_script('frappe.set_route({0})'\
			.format(', '.join(['"{0}"'.format(r) for r in args])))

		self.wait_for(xpath='//div[@data-page-route="{0}"]'.format('/'.join(args)), timeout=4)

	def click(self, css_selector, xpath=None, timeout=20, animate=0, offset=0):
		element = self.wait_till_clickable(css_selector, xpath, timeout)
		self.scroll_to(css_selector, animate, offset)
		time.sleep(0.5)
		element.click()
		return element

	def click_primary_action(self):
		selector = ".page-actions .primary-action"
		#self.scroll_to(selector)
		self.wait_till_clickable(selector).click()
		self.wait_for_ajax()

	def click_secondary_action(self):
		selector = ".page-actions .btn-secondary"
		#self.scroll_to(selector)
		self.wait_till_clickable(selector).click()
		self.wait_for_ajax()

	def click_modal_primary_action(self):
		self.get_visible_modal().find_element_by_css_selector('.btn-primary').click()

	def get_visible_modal(self):
		return self.get_visible_element('.modal-content')

	def get_visible_element(self, selector=None, xpath=None):
		for elem in self.find(selector=selector, xpath=xpath):
			if elem.is_displayed():
				return elem

	def wait_till_clickable(self, selector=None, xpath=None, timeout=20):
		if self.cur_route:
			selector = self.cur_route + " " + selector

		by = By.CSS_SELECTOR
		if xpath:
			by = By.XPATH
			selector = xpath

		return self.get_wait(timeout).until(EC.element_to_be_clickable(
			(by, selector)))


	def execute_script(self, js):
		self.driver.execute_script(js)

	def wait_for_ajax(self, freeze = False):
		self.wait_for('body[data-ajax-state="complete"]', True)
		if freeze:
			self.wait_for_invisible(".freeze-message-container")


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
