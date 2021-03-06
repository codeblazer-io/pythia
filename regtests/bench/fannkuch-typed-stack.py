# The Computer Language Benchmarks Game
# http://shootout.alioth.debian.org/
#
# contributed by Sokolov Yura
# modified by Tupteq
# modified by hartsantler 2014

from time import clock

DEFAULT_ARG = 9


def fannkuch(n:int) ->int:
	with stack:
		#count = range(1, n+1)
		count = [n]int()
		i = 0
		for j in range(1,n+1):
			count[i]=j
			i += 1

		max_flips = 0
		m = n-1
		r = n
		check = 0
		#perm1 = range(n)
		#perm = range(n)

		perm1 = [n]int()
		perm  = [n]int()
		for j in range(n):
			perm[j]  = j
			perm1[j] = j

		while True:
			if check < 30:
				check += 1

			while r != 1:
				count[r-1] = r
				r -= 1

			if perm1[0] != 0 and perm1[m] != m:
				perm = perm1[:]

				flips_count = 0
				k = perm[0]
				while k != 0:
					#assert k < n
					#assert k < len(perm)

					#perm[:k+1] = perm[k::-1] #TODO
					tmp = perm[k::-1]
					#assert len(tmp) <= len(perm)
					#tmp.shrink_to_fit()  ## not required in stack mem mode

					#assert k+1 <= len(perm)
					perm[:k+1] = tmp
					#assert len(perm) < n+1

					flips_count += 1
					k = perm[0]
					if flips_count > 1:
						break

				if flips_count > max_flips:
					max_flips = flips_count


			do_return = True
			while r != n:
				perm1.insert(r, perm1.pop(0))

				#px = perm1.pop(0)
				#if r < len(perm1):
				#	perm1.insert(perm1.begin()+r, px)
				#else:
				#	perm1.append(px)

				count[r] -= 1
				if count[r] > 0:
					do_return = False
					break
				r += 1

			if do_return:
				return max_flips


def main():
	print 'fannkuch...'
	times = []float()
	for i in range(4):
		t0 = clock()
		res = fannkuch(DEFAULT_ARG)
		#print 'fannkuch flips:', res
		tk = clock()
		times.append(tk - t0)
	print 'test OK'
	avg = sumf(times) / len(times)
	print(avg)
