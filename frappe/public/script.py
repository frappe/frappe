import os
import os.path as osp

import json

with open('build.json', mode = 'r') as f:
	build = json.loads(f.read())

	for source, targets in build.items():
		fname = source.split('/')[1]

		if source.split('/')[0] == 'js':
			with open(osp.join('js/webpack', fname), mode = 'w') as f:
				imports = [ ]
				for t in targets:
					if '/lib/' in t: continue

					# if t.startswith('public/js'):
					# 	t = t.replace('public/js', '..')
					# else:
					# 	t = t.replace('public', '../..')

					imports.append(t)

				for i in imports:
					f.write('import "{path}"'.format(path = i))
					f.write("\n");