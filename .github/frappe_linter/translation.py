import re
import sys


files = sys.argv[1]
print(files)

errors_encounter = 0
pattern = re.compile(r"_\(([\"']{,3})(?P<message>((?!\1).)*)\1(\s*,\s*context\s*=\s*([\"'])(?P<py_context>((?!\5).)*)\5)*(\s*,\s*(.)*?\s*(,\s*([\"'])(?P<js_context>((?!\11).)*)\11)*)*\)")
temp = re.compile(r"_\(([\"']{,3})")

files = files.decode('utf-8')
files = files.split()
for file in files:
	with open(file, 'r') as f:
	for num, line in enumerate(f, 1):
		all_matches = temp.finditer(line)
		if all_matches:
		for match in all_matches:
			verify = pattern.search(line)
			if not verify:
			errors_encounter += 1
			print('A syntax error has been discovered at line number: ' + num)
			print('Syntax error occurred with: ' + line)
if errors_encounter > 0 :
	print('You can visit "https://frappe.io/docs/user/en/translations" to resolve this error.')
	assert 1+1 == 3