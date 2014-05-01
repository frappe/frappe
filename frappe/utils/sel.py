# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

driver = None
verbose = None
host = None
logged_in = False
cur_route = False

def start(_verbose=None):
	global driver, verbose
	driver = webdriver.PhantomJS()
	verbose = _verbose

def get(url):
	driver.get(url)

def login(_host):
	global host, logged_in
	if logged_in:
		return
	host = _host
	get(host + "/login")
	wait("#login_email")
	set_input("#login_email", "Administrator")
	set_input("#login_password", "admin" + Keys.RETURN)
	wait("#page-desktop")
	logged_in = True


def module(module_name):
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

def find(selector, everywhere=False):
	if cur_route and not everywhere:
		selector = cur_route + " " + selector
	return driver.find_elements_by_css_selector(selector)

def set_field_input(fieldname, value):
	set_input('[data-fieldname="{0}"]'.format(fieldname), value)

def primary_action():
	find(".appframe-titlebar .btn-primary")[0].click()

def wait_for_page(name):
	global cur_route
	cur_route = None
	route = '[data-page-route="{0}"]'.format(name)
	wait(route)
	cur_route = route

def wait_for_state(state):
	wait(cur_route + '[data-state="{0}"]'.format(state), True)

def wait(selector, everywhere=False):
	if cur_route and not everywhere:
		selector = cur_route + " " + selector
	try:
		elem = WebDriverWait(driver, 10).until(
			EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
		if verbose:
			print "found " + selector
	except TimeoutException:
		print "not found " + selector
		raise
	return elem

def set_input(selector, text):
	elem = find(selector)[0]
	elem.send_keys(text)

def close():
	global driver
	driver.quit()
	driver = None
