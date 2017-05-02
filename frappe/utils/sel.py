# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from urllib import unquote
import time, subprocess
import signal
import sys

host = "http://localhost"
pipe = None
port = "8000"
_driver = None
_verbose = None
logged_in = False
cur_route = False
input_wait = 0

def get_localhost():
	return "{host}:{port}".format(host=host, port=port)

def start(verbose=None, driver=None):
	global _driver, _verbose
	_verbose = verbose

	_driver = getattr(webdriver, driver or "PhantomJS")()
	_driver.set_window_size(1080,800)

	signal.signal(signal.SIGINT, signal_handler)

def signal_handler(signal, frame):
	close()
	sys.exit(0)

def start_test_server(verbose):
	global pipe
	pipe = subprocess.Popen(["bench", "serve", "--port", port], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	#time.sleep(5)
	while not pipe.stderr.readline():
		time.sleep(0.5)
	if verbose:
		print("Test server started")

def get(url):
	_driver.get(url)

def login(wait_for_id="#page-desktop"):
	global logged_in
	if logged_in:
		return
	get(get_localhost() + "/login")
	wait("#login_email")
	set_input("#login_email", "Administrator")
	set_input("#login_password", "admin", key=Keys.RETURN)
	wait(wait_for_id)
	logged_in = True


def go_to_module(module_name, item=None):
	global cur_route

	# desktop
	find(".navbar-home", True)[0].click()
	cur_route = None
	wait("#page-desktop")

	page = "Module/" + module_name
	m = find('#page-desktop [data-link="{0}"] .app-icon'.format(page))
	if not m:
		page = "List/" + module_name
		m = find('#page-desktop [data-link="{0}"] .app-icon'.format(page))
	if not m:
		raise Exception, "Module {0} not found".format(module_name)

	m[0].click()
	wait_for_page(page)

	if item:
		elem = find('[data-label="{0}"]'.format(item))[0]
		elem.click()
		page = elem.get_attribute("data-route")
		wait_for_page(page)

def new_doc(module, doctype):
	go_to_module(module, doctype)
	primary_action()
	wait_for_page("Form/" + doctype)

def add_child(fieldname):
	find('[data-fieldname="{0}"] .grid-add-row'.format(fieldname))[0].click()
	wait('[data-fieldname="{0}"] .form-grid'.format(fieldname))

def done_add_child(fieldname):
	selector = '[data-fieldname="{0}"] .grid-row-open .btn-success'.format(fieldname)
	scroll_to(selector)
	wait_till_clickable(selector).click()

def find(selector, everywhere=False):
	if cur_route and not everywhere:
		selector = cur_route + " " + selector
	return _driver.find_elements_by_css_selector(selector)

def set_field(fieldname, value, fieldtype="input"):
	_driver.switch_to.window(_driver.current_window_handle)
	selector = '{0}[data-fieldname="{1}"]'.format(fieldtype, fieldname)
	set_input(selector, value, key=Keys.TAB)
	wait_for_ajax()

def set_select(fieldname, value):
	select = Select(find('select[data-fieldname="{0}"]'.format(fieldname))[0])
	select.select_by_value(value)
	wait_for_ajax()

def primary_action():
	selector = ".page-actions .primary-action"
	scroll_to(selector)
	wait_till_clickable(selector).click()
	wait_for_ajax()

def wait_for_page(name):
	global cur_route
	cur_route = None
	route = '[data-page-route="{0}"]'.format(name)
	wait_for_ajax()
	elem = wait(route)
	wait_for_ajax()
	cur_route = route
	return elem

def wait_till_clickable(selector):
	if cur_route:
		selector = cur_route + " " + selector
	return get_wait().until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))

def wait_till_visible(selector):
	if cur_route:
		selector = cur_route + " " + selector
	return get_wait().until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))

def wait_for_ajax():
	wait('body[data-ajax-state="complete"]', True)

def wait_for_state(state):
	return wait(cur_route + '[data-state="{0}"]'.format(state), True)

def wait(selector, everywhere=False):
	if cur_route and not everywhere:
		selector = cur_route + " " + selector

	time.sleep(0.5)
	elem = get_wait().until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
	return elem

def get_wait():
	return WebDriverWait(_driver, 20)

def set_input(selector, text, key=None):
	elem = find(selector)[0]
	elem.clear()
	elem.send_keys(text)
	if key:
		time.sleep(0.5)
		elem.send_keys(key)
	if input_wait:
		time.sleep(input_wait)

def scroll_to(selector):
	execute_script("frappe.ui.scroll('{0}')".format(selector))

def execute_script(js):
	_driver.execute_script(js)

def close():
	global _driver, pipe
	if _driver:
		_driver.quit()
	if pipe:
		pipe.kill()
	_driver = pipe = None
