""" Useful general-purpose decorators.  (But don't expect ALL of our decorators to be here.  For example, the elapsed_time decorator is in the lib.log module.)
"""
# see https://wiki.python.org/moin/PythonDecoratorLibrary for some useful decorators!!

import time

from lib import clogging

def transparent(decorator):
	""" Decorators have a few unwanted side effects.  This decorator, when used on a decorator, reverses those side-effects!

	Longer explanation: This decorator can be used to turn simple functions
	into well-behaved decorators, so long as the decorators
	are fairly simple. If a decorator expects a function and
	returns a function (no descriptors), and if it doesn't
	modify function attributes or docstring, then it is
	eligible to use this. Simply apply @simple_decorator to
	your decorator and it will automatically preserve the
	docstring and function attributes of functions to which
	it is applied.
	"""
	def new_decorator(func):
		g = decorator(func)
		g.__name__ = func.__name__
		g.__doc__ = func.__doc__
		g.__dict__.update(func.__dict__)
		return g
	# Now a few lines needed to make transparent *itself*
	# be a well-behaved decorator!
	new_decorator.__name__ = decorator.__name__
	new_decorator.__doc__ = decorator.__doc__
	new_decorator.__dict__.update(decorator.__dict__)
	return new_decorator

@transparent
def record_elapsed_time(func, file_path='defpath'):
	def new_func(*args, **kwargs):
		start_time = time.time()
		out = func(*args, **kwargs)
		end_time = time.time()
		elapsed_time = end_time - start_time
		log_msg = 'Function: {}\tRuntime: {}'.format(func.__name__, str(elapsed_time))
		logger = clogging.getLogger('elapsed_times', filename='elapsed_times.log')
		logger.info(log_msg)
		return out
	return new_func

@transparent
def memoize(obj):
	""" Here's a memoizing function that works on functions, methods, or classes, and exposes the cache publicly.

		This basically takes any recursive function and uses memoizing to make it faster (sacrificing space instead).  This could be a "cheap" way to quickly speed up functions!
	"""
	cache = obj.cache = {}

	@functools.wraps(obj)
	def memoizer(*args, **kwargs):
		key = str(args) + str(kwargs)
		if key not in cache:
			cache[key] = obj(*args, **kwargs)
		return cache[key]
	return memoizer

# other ideas: type enforcement for inputs/outputs
# and so many more!
