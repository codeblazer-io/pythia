'''
array slice syntax
'''

def somefunc():
	a = []int(1,2,3,4,5)
	print( 'a pointer use count:', inline('a.use_count()'))
	print('a addr:', a)
	print('len a:', len(a))
	b = a[1:]
	print('b addr (should not be `a` above):', b)
	print('len b  (should be 4):', len(b))

	c = a[:]
	print('c addr (should not be `a` or `b` above):', c)
	print('len c:', len(c))
	c.push_back(6)
	print('len c - after append:', len(c))
	print('len a:', len(a))

	print('end slice test')
	print( 'a pointer use count:', inline('a.use_count()'))
	print( 'b pointer use count:', inline('b.use_count()'))
	print( 'c pointer use count:', inline('c.use_count()'))
	print('somefunc done')

def main():
	print('calling somefunc')
	somefunc()

	## never reached because there is a segfault at the end
	## of somefunc when the slices go out of scope, they are free'ed twice.
	print('OK')