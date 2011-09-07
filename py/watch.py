"""
Watch the folder at regular intervals and build if files have been changed
"""

if __name__=='__main__':
	import time, build
	
	while 1:
		build.run()
		time.sleep(2)

