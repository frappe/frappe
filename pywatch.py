#!/usr/bin/python3

# Usage: ./pywatch.py <path> [-d]
# path is location of your python code which you want
# to monitor for changes.

# Example:
# Throw this script in the home directory of your
# ERPNext server and run
#./pywatch frappe-bench/apps/ &

# Only dependency for this script is pyinotify. To install it
# run "sudo pip install pyinotify" (and if you don't want to
# install it globally, it's recommended to use python
# virtual environment (http://docs.python-guide.org/en/latest/dev/virtualenvs/)

# Explanation:
# ERPNext has a funky caching issue, where if you modify 
# python file inside an app, ERPNext doesn't pick up the changes
# until you run "bench restart". bench restart usually takes
# around 10-13 seconds which is very annoying and slow. We
# discovered that by killing gunicorn (pkill gunicord), the
# python code gets reloaded and gunicorn process gets
# restarted automatically. Killing gunicorn is almost
# instant, so it's much faster than running bench restart.
# 
# This script watches for changes in python files and
# automatically triggers gunicord restart whenever a
# python file changes, so the changes in the code take
# effect almost instantly.

# TODO:
#  -possibly exclude .git directory with exclude_filter
#  -add a timer and don't kill gunicorn more than once every second.
#  -Issue: when modifying python with vim, on_event is called twice.
#  -Check what happens when a bunch of python files get changed at the same time, for example when installing new app.

import time, sys, pyinotify, subprocess

debug = False

if len(sys.argv) != 2:
   if len(sys.argv) == 3 and sys.argv[2] == '-d':
      debug = True
   else:
      print('%s <PATH_TO_MONITOR> [-d]' % sys.argv[0])
      exit()

path = sys.argv[1]

wm = pyinotify.WatchManager()
notifier = pyinotify.Notifier(wm)

def on_event(arg):
   name = arg.pathname
   #print('event %s' % name)
   if name.split('.')[-1] == 'py':
      if debug:
         print('python file changed: %s' % name)
      subprocess.call(['pkill', 'gunicorn'])

#watch_mask = pyinotify.ALL_EVENTS
watch_mask = pyinotify.IN_CREATE | pyinotify.IN_MODIFY
#exclude_filter=not_py_file (this can be used to exclude .git directory)
wm.add_watch(path, watch_mask, proc_fun=on_event, rec=True, auto_add=True, quiet=False)

notifier.loop()
