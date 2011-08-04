class SandboxController:
	def __init__(self, parent, models):
		self.parent, self.models = parent, models
		
	def validate(self):
		return 'inside validate'
