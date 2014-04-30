# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = None

def start():
	global driver
	driver = webdriver.PhantomJS()

def find(selector):
	return driver.find_elements_by_css_selector(selector)

def wait(selector):
	try:
		elem = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
		return elem
	except:
	    driver.quit()

