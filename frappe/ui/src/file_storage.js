import Storage from './storage';
import walk from 'walk';
import path from 'path';
import { slug } from './utils';

export default class FileStorage extends Storage {
	constructor() {
		super();
		this.setup_path_map();
	}

	get(doctype, name) {
		return Promise.resolve(
			require(this.path_map[slug(doctype)][slug(name)])
		);
	}

	setup_path_map() {
		this.path_map = {};
		walk.walkSync('./frappe', {
			listeners: {
				file: (root, file_data, next) => {
					if (file_data.name.endsWith('.json')) {
						const doctype = path.basename(path.dirname(root));
						const name = path.basename(root);

						if (!this.path_map[doctype]) {
							this.path_map[doctype] = {};
						}

						this.path_map[doctype][name] = path.resolve(root, file_data.name);
					}
					next();
				}
			}
		})
	}
}