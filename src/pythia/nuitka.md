Nuitka Integration
------------------

Simple frontend that compiles and packages a Nuitka module.

```python


def nuitka_compile(source, name='my_nuitka_module'):
	tmp = tempfile.gettempdir()
	file = os.path.join(tmp,'%s.py' %name)
	open(file, 'wb').write(source)
	subprocess.check_call(['nuitka', '--module', file], cwd=tmp)
	if sys.platform.startswith('linux'):
		return os.path.join(tmp, '%s.so' %name)
	elif sys.platform.startswith('darwin'):
		return os.path.join(tmp, '%s.dylib' %name)
	else:
		return os.path.join(tmp, '%s.dll' %name)


```

Integrated Build
----------------

This is incomplete, and not used right now, instead Nuitka is integrated as a simple frontend that compiles the module and packages it in the output tar.

`nuitka_compile_integrated` hacks the code generated by Nuitka,
so that it can be built directly along with the main C++ exe.  Nuitka requires some initalization, 
and its generated functions are not trival to call, it would probably be better to fork Nuitka and make it
work better with Rusthon, rather than try to hack its complex generated output here.

note: all the headers can be removed, except `__helpers.hpp`,
because that gets included from `calling.hpp` (part of the Nuitka public headers)

```python
def nuitka_compile_integrated(source, functions):
	tmp = tempfile.gettempdir()
	file = os.path.join(tmp,'__main__.py')
	open(file, 'wb').write(source)
	subprocess.check_call(
		[
			'nuitka', 
			'--generate-c++-only', 
			'--module', 
			file
		], 
		cwd=tmp
	)
	bdir = os.path.join(tmp, '__main__.build')
	assert os.path.isdir(bdir)
	constbin  = None
	helpers   = None
	headers   = [
		'#include "Python.h"',
		'#include "nuitka/prelude.hpp"',  ## from Nuitka
		'#include "nuitka/compiled_frame.hpp"',  ## prelude.hpp already includes this, for some reason MAKE_FRAME is still missing
		'#include "structseq.h"',         ## from CPython
		'const unsigned char constant_bin[] = "TODO";',  ## TODO read the constants.bin and insert here.
	]
	sources   = []
	buildfiles = os.listdir(bdir)
	buildfiles.sort()
	for name in buildfiles:
		data = open(os.path.join(bdir,name), 'rb').read()
		if name == '__constants.bin':
			constbin = data
		elif name == '__helpers.hpp':
			helpers = data
		elif name.endswith('.hpp'):
			headers.append(data)
		elif name.endswith('.cpp'):
			if name.startswith('module.') and name.endswith('__main__.cpp'):
				data = hack_nuitka_main(data, functions)
			else:
				data = hack_nuitka( data )
			sources.append(data)
		else:
			raise RuntimeError('invalid file found in nuitka build: %s' %name)

	assert helpers
	return {
		'files':[
			{'name':'__helpers.hpp', 'data':helpers}
		],
		'main':'\n'.join(headers+sources)
	}


def hack_nuitka(data):
	out = []
	for line in data.splitlines():
		if line.startswith('#include'):  ## do not include anything
			pass
		elif line == '#define _MODULE_UNFREEZER 1':  ## skips 'frozen' modules and DLL.
			pass
		elif line.strip() == 'extern "C" const unsigned char constant_bin[];':
			pass
		else:
			out.append(line)
	return '\n'.join(out)

def hack_nuitka_main(data, functions):
	out = []
	for line in data.splitlines():
		if line.startswith('#include'):  ## do not include anything
			pass
		elif line.startswith('static PyObject *impl_function_'):
			fname = line.split('impl_function_')[-1].split('(')[0]
			findex = fname.split('_')[0]
			fname  = fname.split('_')[1]
			cname  = line.split('static PyObject *')[-1].split('(')[0]
			func = {
				'name':fname,
				'cname': cname,
			}
			out.append(line)

		elif line.strip()=='#ifdef _NUITKA_WINMAIN_ENTRY_POINT':
			## cut away main ##
			break
		else:
			out.append(line)

	return '\n'.join(out)


```