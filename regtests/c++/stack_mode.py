'''
stack memory mode
'''
with stack:
	let garr : [10]int

	def stack_test():
		let arr : [5]int
		for i in garr:
			print i
			assert i==0
		print 'global array iter ok'
		for i in arr:
			print i
			assert i==0
		print 'local array iter ok'


def main():
	stack_test()
