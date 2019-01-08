# wget setup_frappe.py | python
import os, sys, subprocess, getpass, json, multiprocessing, shutil, platform
from distutils.spawn import find_executable

tmp_bench_repo = '/tmp/.bench'

def install_bench(args):
	# check_distribution_compatibility()
	check_brew_installed()
	# pre-requisites for bench repo cloning
	install_package('curl')
	install_package('wget')

	success = run_os_command({
		'apt-get': [
			'sudo apt-get update',
			'sudo apt-get install -y git build-essential python-setuptools python-dev libffi-dev libssl-dev'
		],
		'yum': [
			'sudo yum groupinstall -y "Development tools"',
			'sudo yum install -y epel-release redhat-lsb-core git python-setuptools python-devel openssl-devel libffi-devel'
		],
		# epel-release is required to install redis, so installing it before the playbook-run.
		# redhat-lsb-core is required, so that ansible can set ansible_lsb variable
	})

	if not find_executable("git"):
		success = run_os_command({
			'brew': 'brew install git'
		})

	if not success:
		print('Could not install pre-requisites. Please check for errors or install them manually.')
		return

	# secure pip installation
	if find_executable('pip'):
		run_os_command({
			'pip': 'sudo pip install --upgrade setuptools cryptography pip'
		})

	else:
		if not os.path.exists("get-pip.py"):
			run_os_command({
				'wget': 'wget https://bootstrap.pypa.io/get-pip.py'
			})

		success = run_os_command({
			'python': 'sudo python get-pip.py --force-reinstall'
		})

		if success:
			run_os_command({
				'pip': 'sudo pip install --upgrade setuptools requests cryptography pip'
			})

	success = run_os_command({
		'pip': "sudo pip install --upgrade cryptography ansible"
	})

	if not success:
		could_not_install('Ansible')

	# clone bench repo
	if not args.run_travis:
		clone_bench_repo(args)

	if not args.user:
		if args.production:
			args.user = 'frappe'

		elif 'SUDO_USER' in os.environ:
			args.user = os.environ['SUDO_USER']

		else:
			args.user = getpass.getuser()

	if args.user == 'root':
		raise Exception('Please run this script as a non-root user with sudo privileges, but without using sudo or pass --user=USER')

	# Python executable
	if not args.production:
		dist_name, dist_version = get_distribution_info()
		if dist_name=='centos':
			args.python = 'python3.6'
		else:
			args.python = 'python3'

	# create user if not exists
	extra_vars = vars(args)
	extra_vars.update(frappe_user=args.user)

	if os.path.exists(tmp_bench_repo):
		repo_path = tmp_bench_repo

	else:
		repo_path = os.path.join(os.path.expanduser('~'), 'bench')

	extra_vars.update(repo_path=repo_path)
	# run_playbook('create_user.yml', extra_vars=extra_vars)

	extra_vars.update(get_passwords(args))
	if args.production:
		extra_vars.update(max_worker_connections=multiprocessing.cpu_count() * 1024)

	if args.frappe_branch:
		frappe_branch = args.frappe_branch
	else:
		frappe_branch = 'master' if args.production else 'develop'
	extra_vars.update(frappe_branch=frappe_branch)

	if args.erpnext_branch:
		erpnext_branch = args.erpnext_branch
	else:
		erpnext_branch = 'master' if args.production else 'develop'
	extra_vars.update(erpnext_branch=erpnext_branch)
	
	bench_name = 'frappe-bench' if not args.bench_name else args.bench_name
	extra_vars.update(bench_name=bench_name)

	# Will install ERPNext production setup by default
	run_playbook('site.yml', sudo=True, extra_vars=extra_vars)

	# # Will do changes for production if --production flag is passed
	# if args.production:
	# 	run_playbook('production.yml', sudo=True, extra_vars=extra_vars)

	if os.path.exists(tmp_bench_repo):
		shutil.rmtree(tmp_bench_repo)

def check_distribution_compatibility():
	supported_dists = {'ubuntu': [14, 15, 16, 18], 'debian': [8, 9],
		'centos': [7], 'macos': [10.9, 10.10, 10.11, 10.12]}

	dist_name, dist_version = get_distribution_info()
	if dist_name in supported_dists:
		if float(dist_version) in supported_dists[dist_name]:
			return

	print("Sorry, the installer doesn't support {0} {1}. Aborting installation!".format(dist_name, dist_version))
	if dist_name in supported_dists:
		print("Install on {0} {1} instead".format(dist_name, supported_dists[dist_name][-1]))
	sys.exit(1)

def get_distribution_info():
	# return distribution name and major version
	if platform.system() == "Linux":
		current_dist = platform.dist()
		return current_dist[0].lower(), current_dist[1].rsplit('.')[0]
	elif platform.system() == "Darwin":
		current_dist = platform.mac_ver()
		return "macos", current_dist[0].rsplit('.', 1)[0]

def install_python27():
	version = (sys.version_info[0], sys.version_info[1])

	if version == (2, 7):
		return

	print('Installing Python 2.7')

	# install python 2.7
	success = run_os_command({
		'apt-get': 'sudo apt-get install -y python-dev',
		'yum': 'sudo yum install -y python27',
		'brew': 'brew install python'
	})

	if not success:
		could_not_install('Python 2.7')

	# replace current python with python2.7
	os.execvp('python2.7', ([] if is_sudo_user() else ['sudo']) + ['python2.7', __file__] + sys.argv[1:])

def install_package(package):
	package_exec = find_executable(package)

	if not package_exec:
		success = run_os_command({
			'apt-get': ['sudo apt-get install -y {0}'.format(package)],
			'yum': ['sudo yum install -y {0}'.format(package)]
		})
	else:
		return

	if not success:
		could_not_install(package)

def check_brew_installed():
	if 'Darwin' not in os.uname():
		return

	brew_exec = find_executable('brew')

	if not brew_exec:
		raise Exception('''
		Please install brew package manager before proceeding with bench setup. Please run following
		to install brew package manager on your machine,

		/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
		''')

def clone_bench_repo(args):
	'''Clones the bench repository in the user folder'''
	if os.path.exists(tmp_bench_repo):
		return 0

	elif args.without_bench_setup:
		clone_path = os.path.join(os.path.expanduser('~'), 'bench')

	else:
		clone_path = tmp_bench_repo

	branch = args.bench_branch or 'master'
	repo_url = args.repo_url or 'https://github.com/frappe/bench'


	success = run_os_command(
		{'git': 'git clone {repo_url} {bench_repo} --depth 1 --branch {branch}'.format(
			repo_url=repo_url, bench_repo=clone_path, branch=branch)}
	)

	return success

def run_os_command(command_map):
	'''command_map is a dictionary of {'executable': command}. For ex. {'apt-get': 'sudo apt-get install -y python2.7'} '''
	success = True
	for executable, commands in list(command_map.items()):
		if find_executable(executable):
			if isinstance(commands, str):
				commands = [commands]

			for command in commands:
				returncode = subprocess.check_call(command, shell=True)
				success = success and ( returncode == 0 )

			break

	return success

def could_not_install(package):
	raise Exception('Could not install {0}. Please install it manually.'.format(package))

def is_sudo_user():
	return os.geteuid() == 0


def get_passwords(args):
	"""
	Returns a dict of passwords for further use
	and creates passwords.txt in the bench user's home directory
	"""

	ignore_prompt = args.run_travis or args.without_bench_setup
	mysql_root_password, admin_password = '', ''
	passwords_file_path = os.path.join(os.path.expanduser('~' + args.user), 'passwords.txt')

	if not ignore_prompt:
		# set passwords from existing passwords.txt
		if os.path.isfile(passwords_file_path):
			with open(passwords_file_path, 'r') as f:
				passwords = json.load(f)
				mysql_root_password, admin_password = passwords['mysql_root_password'], passwords['admin_password']

		# set passwords from cli args
		if args.mysql_root_password:
			mysql_root_password = args.mysql_root_password
		if args.admin_password:
			admin_password = args.admin_password

		# prompt for passwords
		pass_set = True
		while pass_set:
			# mysql root password
			if not mysql_root_password:
				mysql_root_password = getpass.unix_getpass(prompt='Please enter mysql root password: ')
				conf_mysql_passwd = getpass.unix_getpass(prompt='Re-enter mysql root password: ')

				if mysql_root_password != conf_mysql_passwd or mysql_root_password == '':
					mysql_root_password = ''
					continue

			# admin password
			if not admin_password:
				admin_password = getpass.unix_getpass(prompt='Please enter the default Administrator user password: ')
				conf_admin_passswd = getpass.unix_getpass(prompt='Re-enter Administrator password: ')

				if admin_password != conf_admin_passswd or admin_password == '':
					admin_password = ''
					continue

			pass_set = False
	else:
		mysql_root_password = admin_password = 'travis'

	passwords = {
		'mysql_root_password': mysql_root_password,
		'admin_password': admin_password
	}

	if not ignore_prompt:
		with open(passwords_file_path, 'w') as f:
			json.dump(passwords, f, indent=1)

		print('Passwords saved at ~/passwords.txt')

	return passwords


def get_extra_vars_json(extra_args):
	# We need to pass production as extra_vars to the playbook to execute conditionals in the
	# playbook. Extra variables can passed as json or key=value pair. Here, we will use JSON.
	json_path = os.path.join('/tmp', 'extra_vars.json')
	extra_vars = dict(list(extra_args.items()))
	with open(json_path, mode='w') as j:
		json.dump(extra_vars, j, indent=1, sort_keys=True)

	return ('@' + json_path)

def run_playbook(playbook_name, sudo=False, extra_vars=None):
	args = ['ansible-playbook', '-c', 'local',  playbook_name]

	if extra_vars:
		args.extend(['-e', get_extra_vars_json(extra_vars)])

		if extra_vars.get('verbosity'):
			args.append('-vvvv')

	if sudo:
		user = extra_vars.get('user') or getpass.getuser()
		args.extend(['--become', '--become-user={0}'.format(user)])

	if os.path.exists(tmp_bench_repo):
		cwd = tmp_bench_repo
	else:
		cwd = os.path.join(os.path.expanduser('~'), 'bench')

	success = subprocess.check_call(args, cwd=os.path.join(cwd, 'playbooks'))
	return success

def parse_commandline_args():
	import argparse

	parser = argparse.ArgumentParser(description='Frappe Installer')

	# Arguments develop and production are mutually exclusive both can't be specified together.
	# Hence, we need to create a group for discouraging use of both options at the same time.
	args_group = parser.add_mutually_exclusive_group()

	args_group.add_argument('--develop', dest='develop', action='store_true', default=False,
		help='Install developer setup')

	args_group.add_argument('--production', dest='production', action='store_true',
		default=False, help='Setup Production environment for bench')

	parser.add_argument('--site', dest='site', action='store', default='site1.local',
		help='Specifiy name for your first ERPNext site')
	
	parser.add_argument('--without-site', dest='without_site', action='store_true',
		default=False)

	parser.add_argument('--verbose', dest='verbosity', action='store_true', default=False,
		help='Run the script in verbose mode')

	parser.add_argument('--user', dest='user', help='Install frappe-bench for this user')

	parser.add_argument('--bench-branch', dest='bench_branch', help='Clone a particular branch of bench repository')

	parser.add_argument('--repo-url', dest='repo_url', help='Clone bench from the given url')

	parser.add_argument('--frappe-repo-url', dest='frappe_repo_url', action='store', default='https://github.com/frappe/frappe',
		help='Clone frappe from the given url')

	parser.add_argument('--frappe-branch', dest='frappe_branch', action='store',
		help='Clone a particular branch of frappe')
	
	parser.add_argument('--erpnext-repo-url', dest='erpnext_repo_url', action='store', default='https://github.com/frappe/erpnext',
		help='Clone erpnext from the given url')
	
	parser.add_argument('--erpnext-branch', dest='erpnext_branch', action='store',
		help='Clone a particular branch of erpnext')

	parser.add_argument('--without-erpnext', dest='without_erpnext', action='store_true', default=False,
		help='Prevent fetching ERPNext')

	# To enable testing of script using Travis, this should skip the prompt
	parser.add_argument('--run-travis', dest='run_travis', action='store_true', default=False,
		help=argparse.SUPPRESS)

	parser.add_argument('--without-bench-setup', dest='without_bench_setup', action='store_true', default=False,
		help=argparse.SUPPRESS)
	
	# whether to overwrite an existing bench
	parser.add_argument('--overwrite', dest='overwrite', action='store_true', default=False,
		help='Whether to overwrite an existing bench')

	# set passwords
	parser.add_argument('--mysql-root-password', dest='mysql_root_password', help='Set mysql root password')
	parser.add_argument('--admin-password', dest='admin_password', help='Set admin password')
	parser.add_argument('--bench-name', dest='bench_name', help='Create bench with specified name. Default name is frappe-bench')

	# Python interpreter to be used
	parser.add_argument('--python', dest='python', default='python',
		help=argparse.SUPPRESS
	)

	args = parser.parse_args()

	return args

if __name__ == '__main__':
	try:
		import argparse
	except ImportError:
		# install python2.7
		install_python27()

	args = parse_commandline_args()

	install_bench(args)

	print('''Frappe/ERPNext has been successfully installed!''')
