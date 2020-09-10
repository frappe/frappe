import re
import sys

errors_encounter = 0
pattern = re.compile(r"_\(([\"']{,3})(?P<message>((?!\1).)*)\1(\s*,\s*context\s*=\s*([\"'])(?P<py_context>((?!\5).)*)\5)*(\s*,\s*(.)*?\s*(,\s*([\"'])(?P<js_context>((?!\11).)*)\11)*)*\)")
start_pattern = re.compile(r"_{1,2}\([\"']{1,3}")

# skip first argument
files = sys.argv[1:]
files_to_scan = [_file for _file in files if _file.endswith(('.py', '.js'))]

for _file in files_to_scan:
	with open(_file, 'r') as f:
		print(f'Checking: {_file}')
		file_lines = f.readlines()
		for line_number, line in enumerate(file_lines, 1):
			start_matches = start_pattern.search(line)
			if start_matches:
				match = pattern.search(line)
				if not match and line.endswith(',\n'):
					# concat remaining text to validate multiline pattern
					line = "".join(file_lines[line_number - 1:])
					line = line[start_matches.start() + 1:]
					match = pattern.match(line)

				if not match:
					errors_encounter += 1
					print(f'\nTranslation syntax error at line number: {line_number + 1}\n{line.strip()[:100]}')

if errors_encounter > 0:
	print('\nYou can visit "https://frappeframework.com/docs/user/en/translations" to resolve this error.')
	sys.exit(1)
else:
	print('\nGood To Go!')
