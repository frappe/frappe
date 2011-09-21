if __name__=='__main__':
	import sys, os
	sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..'))
	import build
	build.run()