# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

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
port = "8888"
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

	signal.signal(signal.SIGINT, signal_handler)

def signal_handler(signal, frame):
	close()
	sys.exit(0)

def start_test_server(verbose):
	global pipe
	pipe = subprocess.Popen(["frappe", "--serve", "--port", port], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	#time.sleep(5)
	while not pipe.stderr.readline():
		time.sleep(0.5)
	if verbose:
		print "Test server started"

def get(url):
	_driver.get(url)

def login(wait_for_id="#page-desktop"):
	global logged_in
	if logged_in:
		return
	get(get_localhost() + "/login")
	wait("#login_email")
	set_input("#login_email", "Administrator")
	set_input("#login_password", "admin" + Keys.RETURN)
	wait(wait_for_id)
	logged_in = True


def go_to_module(module_name, item=None):
	global cur_route

	# desktop
	find(".navbar-brand")[0].click()
	cur_route = None
	wait("#page-desktop")

	page = "Module/" + module_name
	m = find('#page-desktop [data-link="{0}"]'.format(page))
	if not m:
		page = "List/" + module_name
		m = find('#page-desktop [data-link="{0}"]'.format(page))
	if not m:
		raise Exception, "Module {0} not found".format(module_name)

	m[0].click()
	wait_for_page(page)

	if item:
		elem = find('[data-label="{0}"]'.format(item))[0]
		elem.click()
		page = unquote(elem.get_attribute("href").split("#", 1)[1])
		wait_for_page(page)

def new_doc(module, doctype):
	go_to_module(module, doctype)
	find('.appframe-iconbar .icon-plus')[0].click()
	wait_for_page("Form/" + doctype)

def add_child(fieldname):
	find('[data-fieldname="{0}"] .grid-add-row'.format(fieldname))[0].click()
	wait('[data-fieldname="{0}"] .form-grid'.format(fieldname))

def find(selector, everywhere=False):
	if cur_route and not everywhere:
		selector = cur_route + " " + selector
	return _driver.find_elements_by_css_selector(selector)

def set_field(fieldname, value, fieldtype="input"):
	set_input('{0}[data-fieldname="{1}"]'.format(fieldtype, fieldname), value + Keys.TAB)
	wait_for_ajax()

def set_select(fieldname, value):
	select = Select(find('select[data-fieldname="{0}"]'.format(fieldname))[0])
	select.select_by_value(value)
	wait_for_ajax()

def primary_action():
	find(".appframe-titlebar .btn-primary")[0].click()
	wait_for_ajax()

def wait_for_ajax():
	wait('body[data-ajax-state="complete"]', True)

def wait_for_page(name):
	global cur_route
	cur_route = None
	route = '[data-page-route="{0}"]'.format(name)
	elem = wait(route)
	wait_for_ajax()
	cur_route = route
	return elem

def wait_for_state(state):
	return wait(cur_route + '[data-state="{0}"]'.format(state), True)

def wait(selector, everywhere=False):
	if cur_route and not everywhere:
		selector = cur_route + " " + selector
	try:
		elem = WebDriverWait(_driver, 20).until(
			EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
		if _verbose:
			print "found " + selector
	except TimeoutException:
		print "not found " + selector
		raise
	return elem

def set_input(selector, text):
	elem = find(selector)[0]
	elem.clear()
	elem.send_keys(text)
	if input_wait:
		time.sleep(input_wait)

def close():
	global _driver, pipe
	if _driver:
		_driver.quit()
	if pipe:
		pipe.kill()
	_driver = pipe = None
