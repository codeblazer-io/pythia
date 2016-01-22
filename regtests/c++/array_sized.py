'''
array with default size
'''

class A:
	pass

def somefunc():
	a = [5]int(1,2,3,4,5)
	print('len a:', len(a))
	a.pop()
	print('len a:', len(a))
	print(a[0])
	print(a[1])

	b = [10]int()
	print('len b:', len(b))
	print b[0]
	print b[1]

	c = [10]f64( 1.1, 2.2, 3.3 )
	print c[0]
	print c[1]
	print c[2]

	x = A()
	y = A()
	d = [4]A( x,y )
	print d[0]
	print d[1]

def stackfunc():
	with stack:
		a = [5]int(1,2,3,4,5)
		print('sizeof a:', sizeof(a))  ## says 20 bytes?
		#a.pop()  ## not possible for stack allocated fixed size arrays
		print('len a:', len(a))   ## translator keeps track of the array size
		print(a[0])
		print(a[1])

		for val in a:
			print a

def main():
	somefunc()
	stackfunc()
	print('OK')