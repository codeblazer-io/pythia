C++ Translator
-------------

![toplevel](http://rusthon.github.io/Rusthon/images/RusthonC++.svg)


Imports
-------
* [@import jvm.md](jvm.md)
* [@import nim.md](nim.md)
* [@import cppheader.md](cppheader.md)
* [@import cpython.md](cpython.md)
* [@import nuitka.md](nuitka.md)



```python

NUITKA_HEAD = '''
//PyObject *get_nuitka_module() { return module___main__; }
//PyDictObject *get_nuitka_module_dict() { return moduledict___main__; }

'''

def gen_nuitka_header():
	return NUITKA_HEAD

```

TODO: make inline cpp-channel.h an option.


```python

class CppGenerator( RustGenerator, CPythonGenerator ):

	def make_tuple(self, elts):
		tupletype = []
		for telt in elts:
			if isinstance(telt, ast.Str):  ## TODO test tuple with strings
				v = telt.s
				if v.startswith('"') and v.endswith('"'):  ## TODO this looks like a bug
					v = v[1:-1]
			elif isinstance(telt, ast.List): #v.startswith('[') and v.endswith(']'):
				tsubvec = None
				for st in telt.elts:
					if isinstance(st, ast.Num):
						if str(st.n).isdigit():
							tsubvec = 'int'
						else:
							tsubvec = 'float64'
						break
				assert tsubvec is not None
				v = 'std::vector<%s>' %tsubvec

			elif isinstance(telt, ast.Num):
				if str(telt.n).isdigit():
					v = 'int'
				else:
					v = 'float64'
			elif isinstance(telt, ast.Name):
				v = 'decltype(%s)' % self.visit(telt)
			else:
				v = self.visit(telt)

			if v.startswith('[]'):
				t  = v.split(']')[-1]
				if self._memory[-1]=='STACK':
					v = 'std::vector<%s>' %t
				else:
					v = 'std::vector<%s>*' %t

			tupletype.append(v)


		targs = []
		for ti,te in enumerate(elts):
			tt = tupletype[ti]
			tv = self.visit(te)
			if tv.startswith('[') and tv.endswith(']'):  ## old style
				assert tt.startswith('std::vector')
				if tt.endswith('*'):
					tv = '(new %s{%s})' %(tt[:-1], tv[1:-1])
				else:
					tv = '%s{%s}' %(tt, tv[1:-1])
			#elif tv.startswith('std::vector'):  ## never happens?
			#	raise RuntimeError(tv)

			if tt.startswith('std::vector') and self._memory[-1]=='HEAP':
				tupletype[ti] = 'std::shared_ptr<%s>' %tt
				#if not tv.startswith('new ') and tt.endswith('*'):  ## TODO test when is this required
				#	raise RuntimeError(self.format_error(tt))
				#	tv = 'std::shared_ptr<%s>(new %s)' %(tt[:-1], tv)
				#else:
				tv = 'std::shared_ptr<%s>(%s)' %(tt, tv)

			targs.append(tv)

		return tupletype, targs

	def visit_List(self, node):
		vectype = None
		vecinit = []
		tupletype = None
		for elt in node.elts:
			if vectype is None:
				if isinstance(elt, ast.Num):
					if str(elt.n).isdigit():
						vectype = 'int'
					else:
						vectype = 'float64'
				elif isinstance(elt, ast.Str):
					vectype = 'std::string'
				elif isinstance(elt, ast.Name):
					vectype = 'decltype(%s)' %elt.id
				elif isinstance(elt, ast.Tuple):
					if tupletype is None:
						tupletype = [None] * len(elt.elts)
					for i,sub in enumerate(elt.elts):
						if tupletype[i] is None:
							if isinstance(sub, ast.Num):
								if str(sub.n).isdigit():
									tupletype[i] = 'int'
								else:
									tupletype[i] = 'float64'
							elif isinstance(sub, ast.Str):
								tupletype[i] = 'std::string'
							elif isinstance(sub, ast.Name):
								tupletype[i] = 'decltype(%s)' %sub.id
							else:
								tupletype[i] = 'decltype(%s)' %self.visit(sub)

			if isinstance(elt, ast.Tuple):
				b = self.visit_Tuple(elt, force_make_tuple=True)
				vecinit.append( b )

			else:
				b = self.visit(elt)
				vecinit.append( b )
		if tupletype:
			assert None not in tupletype
			if self._memory[-1]=='STACK':
				vectype = 'std::tuple<%s>' %','.join(tupletype)
			else:
				vectype = 'std::shared_ptr<std::tuple<%s>>' %','.join(tupletype)

		if self._memory[-1]=='STACK':
			return 'std::vector<%s>{%s}' % (vectype,','.join(vecinit))
		else:
			return 'new std::vector<%s>{%s}' % (vectype,','.join(vecinit))


	def visit_Return(self, node):
		if isinstance(node.value, ast.Tuple):
			## initializer list ##
			return 'return {%s};' % ', '.join(map(self.visit, node.value.elts))
		if node.value:
			func = self._function_stack[-1]
			if node not in func._return_nodes:
				func._return_nodes.add(node)

			if isinstance(node.value, ast.Name) and node.value.id=='self':
				func.return_type = 'auto'

				if self._memory[-1]=='STACK':
					v = '*this;'
				else:
					#v = 'std::make_shared<%s>(*this)' %self._class_stack[-1].name
					#v = 'shared_from_this()'  ## this breaks subclasses when the base class has a method that returns `self`
					v = 'std::static_pointer_cast<%s>(shared_from_this())' %self._class_stack[-1].name

			elif isinstance(node.value, ast.Name) and node.value.id=='next':  ## seastar lambda repeat
				v = 'stop_iteration::no'
			elif isinstance(node.value, ast.Name) and node.value.id=='stop':  ## seastar lambda repeat
				v = 'make_ready_future<stop_iteration>(stop_iteration::yes)'

			elif isinstance(node.value, ast.Name) and node.value.id=='future':  ## seastar
				v = 'make_ready_future<>()'
			elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Subscript):
				T = self.visit(node.value.func.slice)
				F = self.visit(node.value.args[0])
				v = 'make_ready_future<%s>(%s)' %(T,F)
			else:
				if isinstance(node.value, ast.Num):
					if str(node.value.n).isdigit(): func.return_type = 'int'
					else: func.return_type = 'float64'
				elif isinstance(node.value, ast.Str):
					func.return_type = 'std::string'
				elif isinstance(node.value, ast.BinOp):
					if isinstance(node.value.right, ast.Num):
						if str(node.value.right.n).isdigit(): func.return_type = 'int'
						else: func.return_type = 'float64'
					elif isinstance(node.value.right, ast.Str):
						func.return_type = 'std::string'
				else:
					func.return_type = 'auto'

				v = self.visit(node.value)
			try:
				return 'return %s;' % v
			except:
				raise RuntimeError(v)
		else:
			return 'return;'


	def is_container_type(self, T):
		## TODO better parsing
		if 'std::vector' in T or 'std::map' in T:
			return True
		elif self.usertypes and 'vector' in self.usertypes:
			if self.usertypes['vector']['template'].split('<')[0] in T:
				return True
		return False

	def visit_Assert(self, node):
		t = ts = self.visit(node.test)
		ts = ts.replace('"', '\\"')
		return 'if (!(%s)) {throw std::runtime_error("assertion failed: %s"); }' %(t,ts)


	def visit_ImportFrom(self, node):
		# print node.module
		# print node.names[0].name
		# print node.level
		if node.module=='runtime':
			self._use_runtime = True
		return ''

	def get_user_class_headers(self):
		return self._user_class_headers

	def visit_Import(self, node):
		includes = []

		for alias in node.names:
			name = alias.name.replace('__SLASH__', '/').replace('__DASH__', '-')
			if alias.asname:
				self._user_class_headers[ alias.asname ] = {
					'file':name,
					'source':[]
				}

			if name == 'jvm':
				self._has_jvm = True
			elif name == 'nim':
				self._has_nim = True
			elif name == 'nuitka':
				self._has_nuitka = True
			elif name == 'cpython':
				self._has_cpython = True
			elif name.endswith('.h') or name.endswith('.hh'):
				includes.append('#include "%s"' %name)
			else:
				includes.append('#include <%s>' %name)

		return '\n'.join(includes)


	def visit_Module(self, node):
		header = [ CPP_HEADER ]
		lines = []

		for b in node.body:
			line = self.visit(b)
			if line == 'main();':  ## to be compatible with other backends that need to call main directly
				continue

			if line is not None:
				for sub in line.splitlines():
					if sub==';':
						#raise SyntaxError('bad semicolon')
						pass
					else:
						lines.append( sub )
			else:
				if isinstance(b, ast.Import):
					header.append( self.visit(b) )
				else:
					raise SyntaxError(b)

		if self._has_channels:
			## https://github.com/ahorn/cpp-channel
			#header.append('#include <channel>')
			## instead of including, just directly inline cpp-channel source
			#dirname = os.path.dirname(os.path.abspath(__file__))
			header.append(
				open( os.path.join(RUSTHON_LIB_ROOT, 'src/pythia/runtime/c++/cpp-channel.h') ).read()
			)

		if self._has_jvm:
			header.append( gen_jvm_header(self._java_classpaths) )

		if self._has_nim:
			header.append( gen_nim_header() )

		if self._has_nuitka:
			header.append( gen_nuitka_header() )

		if self._has_cpython:
			header.append( gen_cpython_header() )

		## forward declare all classes
		for classname in self._classes:
			header.append('class %s;' %classname)

		if len(self._kwargs_type_.keys()):
			#header.append('class _KwArgs_;')

			impl = []
			header.append('class _KwArgs_ {')
			header.append('	public:')

			for name in self._kwargs_type_:
				type = self._kwargs_type_[name]
				header.append( '  %s _%s_;' %(type,name))
				header.append( '  bool __use__%s;' %name)

			for name in self._kwargs_type_:
				type = self._kwargs_type_[name]
				header.append( '  _KwArgs_*  %s(%s %s);' %(name, type, name))

				impl.append( '  _KwArgs_*   _KwArgs_::%s(%s %s) {' %(name, type, name))
				impl.append( '		this->__use__%s = true;' %name)
				impl.append( '		this->_%s_ = %s;' %(name, name))
				impl.append( '		return this;')
				impl.append('};')
			header.append('};')
			header.extend( impl )

		if self._has_cpython:
			header.append( self.gen_cpython_helpers() )


		self.output_pak = pak = {'c_header':'', 'cpp_header':'', 'main':''}
		cheader = None
		cppheader = None
		if len(self._cheader):
			cheader = []
			cppheader = ['extern "C" {']
			for line in self._cheader:
				cheader.append(line)
				cppheader.append('\t'+line)
			cppheader.append('}')

		if cheader:
			pak['header.c'] = '\n'.join( cheader )
		if cppheader:
			pak['header.cpp'] = '\n'.join( cppheader )

		if self._user_class_headers:
			pass ## see get_user_class_headers
		else:
			if 'int main() {' in lines:  ## old hack to insert method defs before main
				main_index = lines.index('int main() {')
				for idef in self._cpp_class_impl:
					lines.insert(main_index,idef)
			else:
				## option to split this part into the cpp body TODO
				for idef in self._cpp_class_impl:
					lines.append(idef)

		if self._use_runtime:
			lines = header + list(self._imports) + lines
		else:
			lines = list(self._imports) + lines

		if len(self._kwargs_type_.keys()) and False:
			header = []
			impl = []
			header.append('class _KwArgs_ {')
			header.append('	public:')

			for name in self._kwargs_type_:
				type = self._kwargs_type_[name]
				header.append( '  %s _%s_;' %(type,name))
				header.append( '  bool __use__%s;' %name)

			for name in self._kwargs_type_:
				type = self._kwargs_type_[name]
				header.append( '  _KwArgs_*  %s(%s %s);' %(name, type, name))

				impl.append( '  _KwArgs_*   _KwArgs_::%s(%s %s) {' %(name, type, name))
				impl.append( '		this->__use__%s = true;' %name)
				impl.append( '		this->_%s_ = %s;' %(name, name))
				impl.append( '		return this;')
				impl.append('};')
			header.append('};')
			header.extend( impl )
			lines.extend(header)


		pak['main'] = '\n'.join( lines )
		return pak['main']

	def visit_Set(self, node):
		## c++11 aggregate initialization
		## http://en.cppreference.com/w/cpp/language/aggregate_initialization
		return '{%s}' %','.join([self.visit(elt) for elt in node.elts])

```

low level `new` for interfacing with external c++.
Also used for code that is blocked with `with pointers:`
to create a class without having to create a temp variable,
`f( new(MyClass(x,y)) )`, directly calls the constructor,
if MyClass is a Rusthon class then __init__ will be called.
TODO fix mixing with std::shared_ptr by keeping a weak_ptr
in each object that __init__ returns (also fixes the _ref_hacks)

```python

	def _visit_call_helper_new(self, node):
		if isinstance(node.args[0], ast.BinOp): # makes an array or map
			a = self.visit(node.args[0])
			if type(a) is not tuple:
				raise SyntaxError(self.format_error('TODO some extended type'))

			atype, avalue = a
			if atype.endswith('*'): atype = atype[:-1]
			else: pass  ## this should never happen
			return '(/*array-or-map*/ new %s %s)' %(atype, avalue)

		## Pythia User Class ##
		elif isinstance(node.args[0], ast.Call) and isinstance(node.args[0].func, ast.Name) and node.args[0].func.id in self._classes:
			classname = node.args[0].func.id
			args = [self.visit(arg) for arg in node.args[0].args ]
			if self._classes[classname]._requires_init:
				if not isinstance(self._stack[-2], ast.Assign):
					raise RuntimeError('TODO new(A(new(B))')
				return '(/*initialize-class*/ new %s)->__init__(%s)' %(classname, ','.join(args))

			elif args:  ## a rusthon class that subclasses from an external c++ class ##
				return '(/*external-parent-class*/ new %s(%s))' %(classname, ','.join(args))
			else:
				return '(/*create-class*/ new %s)' %classname

		## external c++ class ##
		else:
			classname = self.visit(node.args[0])
			return '(/*external-class*/ new %s)' %classname

```

Subclasses from `RustGenerator`, see here:
[rusttranslator.md](rusttranslator.md)
TODO: reverse, `RustGenerator` should subclass from `CppGenerator`.

note: polymorphic classes are not generated by default, virtual methods are not required,
casting works fine with `static_cast` and `std::static_pointer_cast`.

```python

	def __init__(self, source=None, requirejs=False, insert_runtime=False, cached_json_files=None, use_try=True):
		RustGenerator.__init__(self, source=source, requirejs=False, insert_runtime=False)
		self._cpp = True
		self._rust = False  ## can not be true at the same time self._cpp is true, conflicts in switch/match hack.
		self._shared_pointers = True
		self._noexcept = False
		self._polymorphic = False  ## by default do not use polymorphic classes (virtual methods)
		self._has_jvm = False
		self._jvm_classes = dict()
		self._has_nim = False
		self._has_nuitka = False
		self._has_cpython = False
		self._known_pyobjects  = dict()
		self._use_runtime = insert_runtime
		self.cached_json_files = cached_json_files or dict()
		self.usertypes = dict()
		self._user_class_headers = dict()
		self._finally_id = 0
		self._use_try = use_try
		self._has_gnu_stm = False

	def visit_Delete(self, node):
		targets = [self.visit(t) for t in node.targets]
		if len(targets)==0:
			raise RuntimeError('no delete targets')
		r = []
		if self.usertypes and 'weakref' in self.usertypes and 'reset' in self.usertypes['weakref']:
			for t in targets:
				r.append('%s.%s();' %(t, self.usertypes['weakref']['reset']))
		elif self.usertypes and 'shared' in self.usertypes and 'reset' in self.usertypes['shared']:
			for t in targets:
				r.append('%s.%s();' %(t, self.usertypes['shared']['reset']))
		elif self._shared_pointers:
			for t in targets:
				r.append('%s.reset();' %t)
		else:
			for t in targets:
				if t in self._known_arrays:
					r.append('delete[] %s;')
				else:
					r.append('delete %s;')

		return '\n'.join(r)

	def visit_Str(self, node, wrap=True):
		s = node.s.replace("\\", "\\\\").replace('\n', '\\n').replace('\r', '\\r').replace('"', '\\"')
		if wrap is False:
			return s
		elif self._force_cstr:
			return '"%s"' % s

		elif self.usertypes and 'string' in self.usertypes.keys():
			if self.usertypes['string'] is None:
				return '"%s"' % s
			else:
				return self.usertypes['string']['new'] % '"%s"' % s
		else:
			return 'std::string("%s")' % s

	def visit_Print(self, node):
		r = []
		for e in node.values:
			s = self.visit(e)
			if isinstance(e, ast.List) or isinstance(e, ast.Tuple):
				for sube in e.elts:
					r.append('std::cout << %s;' %self.visit(sube))
				if r:
					r[-1] += 'std::cout << std::endl;'
				else:
					r.append('std::cout << std::endl;')
			else:
				r.append('std::cout << %s << std::endl;' %s)
		return '\n'.join(r)
```

TODO
----
* test finally

```python

	def visit_TryExcept(self, node, finallybody=None):
		## TODO: check why `catch (...)` is not catching file errors
		out = []

		use_try = self._use_try  ## when building with external tools or platforms -fexceptions can not be enabled.


		if use_try:
			if finallybody:
				self._finally_id += 1
				out.append('bool __finally_done_%s = false;' %self._finally_id)
				out.append( self.indent()+'try {' )
			else:
				out.append( 'try {' )

		self.push()
		for b in node.body:
			out.append( self.indent()+self.visit(b) )

		self.pull()
		if use_try:
			out.append(self.indent()+ '}' )

			handler_types = []
			for ha in node.handlers:
				if ha.type:
					handler_types.append(self.visit(ha.type))

			if handler_types:
				out.append( self.indent() + 'catch (std::runtime_error* __error__) {' )
				self.push()
				out.append( self.indent() + 'std::string __errorname__ = __parse_error_type__(__error__);')
			else:
				out.append( self.indent() + 'catch (...) {' )
				self.push()

			for h in node.handlers:
				out.append(
					self.indent() + self.visit_ExceptHandler(h, finallybody=finallybody)
				)
			self.pull()

			out.append(self.indent()+ '}' )

			## TODO also catch these error that standard c++ libraries are likely to throw ##
			#out.append( self.indent() + 'catch (const std::overflow_error& e) { std::cout << "OVERFLOW ERROR" << std::endl; }' )
			#out.append( self.indent() + 'catch (const std::runtime_error& e) { std::cout << "RUNTIME ERROR" << std::endl; }' )
			#out.append( self.indent() + 'catch (const std::exception& e) {' )
			#out.append( self.indent() + 'catch (...) { std::cout << "UNKNOWN ERROR" << std::endl; }' )


			## wrap in another try that is silent
			if finallybody:
				out.append(self.indent()+'if (__finally_done_%s == false) {' %self._finally_id )
				self.push()
				out.append(self.indent()+'try {		// finally block')
				self.push()
				for b in finallybody:
					out.append(self.indent()+self.visit(b))
				self.pull()
				out.append(self.indent()+'} catch (...) {}')
				self.pull()
				out.append(self.indent()+'}')

				self._finally_id -= 1

		return '\n'.join( out )

	def visit_ExceptHandler(self, node, finallybody=None):
		#out = ['catch (std::runtime_error* __error__) {']
		T = 'Error'
		out = []
		if node.type:
			T = self.visit(node.type)
			out.append('if (__errorname__ == std::string("%s")) {' %T )

		self.push()

		if node.name:
			#out.append(self.indent()+'auto %s = *__error__;' % self.visit(node.name))
			out.append(self.indent()+'auto %s = __error__;' % self.visit(node.name))

		## this happens before the exception body, while this is not strictly python
		## it is close enough, because the main requirement is that the finally body
		## is always run, even if there is a return or new exception raised.
		if finallybody:
			out.append(self.indent()+'__finally_done_%s = true;' %self._finally_id)
			self.push()
			out.append(self.indent()+'try {		// finally block')
			self.push()
			for b in finallybody:
				out.append(self.indent()+self.visit(b))
			self.pull()
			out.append(self.indent()+'} catch (...) {}')
			self.pull()


		for b in node.body:
			out.append(self.indent()+self.visit(b))

		self.pull()
		if node.type:
			out.append(self.indent()+'}')
		return '\n'.join(out)


```


CPython C-API
-------------
user syntax `import cpython` and `->`

```python

	def gen_cpy_call(self, pyob, node):
		fname = self.visit(node.func)
		if not node.args and not node.keywords:
			return 'PyObject_Call(%s, Py_BuildValue("()"), NULL)' %pyob
		else:
			lambda_args = [
				'[&] {',
				'auto args = PyTuple_New(%s);' %len(node.args),
			]
			for i,arg in enumerate(node.args):
				if isinstance(arg, ast.Num):
					n = arg.n
					if str(n).isdigit():
						n = 'PyInt_FromLong(%s)' %n
						lambda_args.append('PyTuple_SetItem(args, %s, %s);' %(i, n))
					else:
						n = 'PyFloat_FromDouble(%s)' %n
						lambda_args.append('PyTuple_SetItem(args, %s, %s);' %(i, n))
				elif isinstance(arg, ast.Str):
					n = 'PyString_FromString("%s")' %arg.s
					lambda_args.append('PyTuple_SetItem(args, %s, %s);' %(i, n))
				else:
					lambda_args.append('PyTuple_SetItem(args, %s, %s);' %(i, self.visit(arg)))
			lambda_args.append('return args; }()')
			return 'PyObject_Call(%s, %s, NULL)' %(pyob, '\n'.join(lambda_args))

	def gen_cpy_get(self, pyob, name):
		return 'PyObject_GetAttrString(%s,"%s")' %(pyob, name)

```

Slice and List Comprehension `[:]`, `[]int(x for x in range(n))`
----------------------------------
negative slice is not fully supported, only `-1` literal works.

```python

	def _gen_slice(self, target=None, value=None, lower=None, upper=None, step=None, type=None, result_size=None):
		assert target
		assert value
		fixed_size = None
		if type and isinstance(type, tuple) and type[1]:
			fixed_size = type[1]
			type = type[0]

		elif type and type.startswith('[]'):
			T = type.split(']')[-1].strip()
			if self.is_prim_type(T) or self._memory[-1]=='STACK':
				type = T
			elif type.count('[')==1:
				type = 'std::shared_ptr<%s>' %T
			else:
				raise RuntimeError('TODO md-array slice')


		#################################################
		if fixed_size:
			slice = ['/* <fixed size slice> %s : %s : %s */' %(lower, upper, step)]
			con = []
			is_constant = True

			if fixed_size.isdigit():
				fixed_size = int(fixed_size)
				if lower and not upper:
					if lower.isdigit():
						for i in range(int(lower), fixed_size):
							con.append('%s[%s]' %(value,i))
					else:
						is_constant = False
				elif upper and not lower:
					if upper.isdigit():
						for i in range(0, int(upper)):
							con.append('%s[%s]' %(value,i))
					else:
						is_constant = False
				elif not lower and not upper:
					if step=='-1':
						i = fixed_size-1
						while i >= 0:
							con.append('%s[%s]' %(value,i))
							i -= 1
					else:
						for i in range(fixed_size):
							con.append('%s[%s]' %(value,i))
				else:
					raise SyntaxError('todo slice fixed size stack array')

				if is_constant:
					slice.append(
						self.indent()+'%s %s[%s] = {%s};' %(type,target, result_size, ','.join(con))
					)
				else:
					pass  ## fallback to for loop
			else:
				is_constant = False

			if not is_constant:
				if not lower and not upper:
					if step=='-1':
						slice.extend([
							self.indent()+'%s %s[%s];' %(type,target, fixed_size),
							self.indent()+'int __L = 0;',
							self.indent()+'for (int __i=%s-1; __i>=%s; __i--) {' %(fixed_size, lower),
							self.indent()+'  %s[__L] = %s[__i];' %(target, value),
							self.indent()+'  __L ++;',
							self.indent()+'}',
						])
					else:
						slice.extend([
							self.indent()+'%s %s[%s];' %(type,target, fixed_size),
							self.indent()+'for (int __i=0; __i<%s; __i++) {' %fixed_size,
							self.indent()+'  %s[__i] = %s[__i];' %(target, value),
							self.indent()+'}',
						])

				elif lower and not upper:
					if step=='-1':
						slice.extend([
							self.indent()+'%s %s[%s-%s];' %(type,target, fixed_size, lower),						
							self.indent()+'int __L = 0;',
							self.indent()+'for (int __i=%s-1; __i>=%s; __i--) {' %(fixed_size, lower),
							self.indent()+'  %s[__L] = %s[__i];' %(target, value),
							self.indent()+'  __L ++;',
							self.indent()+'}',
						])
					else:
						slice.extend([
							self.indent()+'%s %s[%s-%s];' %(type,target, fixed_size, lower),						
							self.indent()+'int __L = 0;',
							self.indent()+'for (int __i=%s; __i<%s; __i++) {' %(lower, fixed_size),
							self.indent()+'  %s[__L] = %s[__i];' %(target, value),
							self.indent()+'  __L ++;',
							self.indent()+'}',
						])
				elif upper and not lower:
					slice.extend([
						self.indent()+'%s %s[%s];' %(type,target, upper),						
						self.indent()+'int __U = 0;',
						self.indent()+'for (int __i=0; __i<%s; __i++) {' %upper,
						self.indent()+'  %s[__U] = %s[__i];' %(target, value),
						self.indent()+'  __U ++;',
						self.indent()+'}',
					])
				else:
					raise SyntaxError('\n'.join(slice))
			return '\n'.join(slice)

		elif type:
			slice = ['/*<<slice>> `%s` [%s:%s:%s] %s */' %(value, lower, upper, step, type)]
			if '<' in type and '>' in type:
				type = type.split('<')[-1].split('>')[0]
				if self._memory[-1]=='HEAP':
					if not self.is_prim_type(type):
						type = 'std::shared_ptr<%s>' %type

			if step=="-1":  ##if step.isdigit() and int(step)<0: TODO
				if self._memory[-1]=='STACK':
					slice.append(self.indent()+'std::vector<%s> %s;' %(type,target))
				else:
					slice.append(self.indent()+'std::vector<%s> _ref_%s;' %(type,target))

				step = step[1:]  ## strip `-`
				if lower and not upper:
					if self._memory[-1]=='STACK':
						slice.extend([
							'for(int _i_=%s;_i_>=0;_i_-=%s){' %(lower,step),
							' %s.push_back(%s[_i_]);' %(target, value),
							'}'
						])
					else:
						slice.extend([
							#'for(int _i_=%s->size()-(1+%s);_i_>=0;_i_-=%s){' %(value,lower,step),
							'for(int _i_=%s;_i_>=0;_i_-=%s){' %(lower,step),
							' _ref_%s.push_back((*%s)[_i_]);' %(target, value),
							'}'
						])
				elif upper:
					raise RuntimeError('slice todo')
				else:
					if self._memory[-1]=='STACK':
						slice.extend([
							'for(int _i_=%s.size()-1;_i_>=0;_i_-=%s){' %(value,step),
							' %s.push_back(%s[_i_]);' %(target, value),
							'}',
						])
					else:
						slice.extend([
							'for(int _i_=%s->size()-1;_i_>=0;_i_-=%s){' %(value,step),
							' _ref_%s.push_back((*%s)[_i_]);' %(target, value),
							'}',
						])

			elif step:
				if self._memory[-1]=='STACK':
					slice.append('std::vector<%s> %s;' %(type,target))
				else:
					slice.append('std::vector<%s> _ref_%s;' %(type,target))

				if lower and not upper:
					if self._memory[-1]=='STACK':
						slice.append( ''.join([
							'if(%s<0){'%step,
							'for(int _i_=%s.size()-%s-1;_i_>=0;_i_+=%s){' %(value,lower,step),
							' %s.push_back(%s[_i_]);' %(target, value),
							'}} else {',
							'for(int _i_=%s;_i_<%s.size();_i_+=%s){' %(lower,value,step),
							' %s.push_back(%s[_i_]);' %(target, value),
							'}}',
							])
						)
					else:
						slice.append( ''.join([
							'if(%s<0){'%step,
							'for(int _i_=%s->size()-%s-1;_i_>=0;_i_+=%s){' %(value,lower,step),
							' _ref_%s.push_back((*%s)[_i_]);' %(target, value),
							'}} else {',
							'for(int _i_=%s;_i_<%s->size();_i_+=%s){' %(lower,value,step),
							' _ref_%s.push_back((*%s)[_i_]);' %(target, value),
							'}}',
							])
						)
				elif upper:
					raise SyntaxError('TODO slice upper with step')
				else:
					if self._memory[-1]=='STACK':
						slice.append( ''.join([
							'if(%s<0){'%step,
							'for(int _i_=%s.size()-1;_i_>=0;_i_+=%s){' %(value,step),
							' %s.push_back(%s[_i_]);}' %(target, value),
							'} else {',
							'for(int _i_=0;_i_<%s.size();_i_+=%s){' %(value,step),
							' %s.push_back(%s[_i_]);}' %(target, value),
							'}',
							])
						)

					else:
						slice.append( ''.join([
							'if(%s<0){'%step,
							'for(int _i_=%s->size()-1;_i_>=0;_i_+=%s){' %(value,step),
							' _ref_%s.push_back((*%s)[_i_]);}' %(target, value),
							'} else {',
							'for(int _i_=0;_i_<%s->size();_i_+=%s){' %(value,step),
							' _ref_%s.push_back((*%s)[_i_]);}' %(target, value),
							'}',
							])
						)
			else:
				isptr = False
				#if value in self._known_arrays and isinstance(self._known_arrays[value], str):
				#	if self._known_arrays[value].startswith('[]'):
				#		isptr = True
				if value in self._known_pointers:
					isptr = True
					if self._memory[-1]=='HEAP':
						self._known_pointers[target] = self._known_pointers[value]
				if self._memory[-1]=='STACK':
					self._known_refs[target] = type
				################################

				if isptr and self._memory[-1]=='HEAP':
					slice.append(self.indent()+'auto %s = new std::vector<%s>(' %(target, type))					
				elif self._memory[-1]=='STACK':
					slice.append(self.indent()+'std::vector<%s> %s(' %(type,target))
				else:
					slice.append(self.indent()+'std::vector<%s> _ref_%s(' %(type,target))

				if lower:
					if isptr:
						slice.append(self.indent()+'%s->begin()+%s,' %(value, lower))
					elif self._memory[-1]=='STACK':
						slice.append(self.indent()+'%s.begin()+%s,' %(value, lower))
					else:
						slice.append(self.indent()+'%s->begin()+%s,' %(value, lower))
				else:
					if isptr:
						slice.append(self.indent()+'%s->begin(),' %value)
					elif self._memory[-1]=='STACK':
						slice.append(self.indent()+'%s.begin(),' %value)
					else:
						slice.append(self.indent()+'%s->begin(),' %value)

				if upper:
					if upper < 0:
						if self._memory[-1]=='STACK':
							slice.append(self.indent()+'%s.end() %s'%(value, upper))
						else:
							slice.append(self.indent()+'%s->end() %s'%(value, upper))
					else:
						if self._memory[-1]=='STACK':
							slice.append(self.indent()+'%s.begin()+%s'%(value, upper))
						else:
							slice.append(self.indent()+'%s->begin()+%s'%(value, upper))

				else:
					if isptr:
						slice.append(self.indent()+'%s->end()'%value)
					elif self._memory[-1]=='STACK':
						slice.append(self.indent()+'%s.end()'%value)
					else:
						slice.append(self.indent()+'%s->end()'%value)

				slice.append(self.indent()+');')

			vectype = 'std::vector<%s>' %type

			if self._memory[-1]=='STACK':
				pass
			elif not self._shared_pointers:
				slice.append(self.indent()+'%s* %s = &_ref_%s);' %(vectype, target, target))
			elif self._unique_ptr:
				slice.append(self.indent()+'std::unique_ptr<%s> %s = _make_unique<%s>(_ref_%s);' %(vectype, target, vectype, target))
			else:
				slice.append(self.indent()+'std::shared_ptr<%s> %s = std::make_shared<%s>(_ref_%s);' %(vectype, target, vectype, target))
			return '\n'.join(slice)

		else:  ## slice an unknown type of array ##
			if not lower and not upper and not step:  ## slice copy `myarr[:]`
				if self._memory[-1]=='STACK':
					return 'std::vector< decltype(%s->begin())::value_type > %s( %s->begin(), %s->end() );' %(value, target, value, value)
				else:
					vectype = 'std::vector<decltype(%s->begin())::value_type>' %value
					return 'auto %s = std::make_shared<%s>( %s(%s->begin(),%s->end()) );' %(target, vectype,vectype, value, value)

			elif lower and not upper and not step:
				if self._memory[-1]=='STACK':
					return 'std::vector< decltype(%s->begin())::value_type > %s( %s->begin()+%s, %s->end() );' %(value, target, value, lower, value)
				else:
					vectype = 'std::vector<decltype(%s->begin())::value_type>' %value
					return 'auto %s = std::make_shared<%s>( %s(%s->begin()+%s,%s->end()) );' %(target, vectype,vectype, value, lower, value)
			elif upper and not lower and not step:
				if self._memory[-1]=='STACK':
					return 'std::vector< decltype(%s->begin())::value_type > %s( %s->begin(), %s->begin()+%s );' %(value, target, value, value, upper)
				else:
					vectype = 'std::vector<decltype(%s->begin())::value_type>' %value
					return 'auto %s = std::make_shared<%s>( %s(%s->begin(),%s->begin()+%s) );' %(target, vectype,vectype, value, value, upper)

			else:
				raise RuntimeError('TODO slice unknown')


```


Translate to C++
----------------

TODO save GCC PGO files.

```python

def translate_to_cpp(script, insert_runtime=True, cached_json_files=None, use_try=True):
	if '--debug-inter' in sys.argv:
		raise RuntimeError(script)

	if '--osv' in sys.argv:
		osv = open( os.path.join(RUSTHON_LIB_ROOT, 'src/pythia/runtime/osv_builtins.py') ).read()
		osv = python_to_pythonjs( osv, cpp=True )
		script = osv + '\n' + script

	if insert_runtime:
		runtime = open( os.path.join(RUSTHON_LIB_ROOT, 'src/pythia/runtime/cpp_builtins.py') ).read()
		runtime = python_to_pythonjs( runtime, cpp=True )
		script = runtime + '\n' + script

	try:
		tree = ast.parse(script)
	except SyntaxError as err:
		e = ['%s:	%s'%(i+1, line) for i,line in enumerate(script.splitlines())]
		sys.stderr.write('\n'.join(e))
		raise err

	g = CppGenerator(
		source=script, 
		insert_runtime=insert_runtime, 
		cached_json_files=cached_json_files,
		use_try = use_try
	)
	g.visit(tree) # first pass gathers classes
	pass2 = g.visit(tree)
	g.reset()
	pass3 = g.visit(tree)
	userheaders = g.get_user_class_headers()
	if userheaders:
		g.output_pak['user-headers'] = userheaders
	return g.output_pak

```

