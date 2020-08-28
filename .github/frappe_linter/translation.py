import re
import sys

errors_encounter = 0
pattern = re.compile(r"_\(([\"']{,3})(?P<message>((?!\1).)*)\1(\s*,\s*context\s*=\s*([\"'])(?P<py_context>((?!\5).)*)\5)*(\s*,\s*(.)*?\s*(,\s*([\"'])(?P<js_context>((?!\11).)*)\11)*)*\)")
start_pattern = re.compile(r"_{1,2}\([\"']{1,3}")

# skip first argument
files = sys.argv[1:]
for _file in files:
	if not _file.endswith(('.py', '.js')):
		continue
	with open(_file, 'r') as f:
		print(f'Checking: {_file}')
		for num, line in enumerate(f, 1):
			all_matches = start_pattern.finditer(line)
			if all_matches:
				for match in all_matches:
					verify = pattern.search(line)
					if not verify:
						errors_encounter += 1
						print(f'A syntax error has been discovered at line number: {num}')
						print(f'Syntax error occurred with: {line}')
if errors_encounter > 0:
	print('You can visit "https://frappeframework.com/docs/user/en/translations" to resolve this error.')
	assert 1+1 == 3
else:
	print('Good To Go!')
