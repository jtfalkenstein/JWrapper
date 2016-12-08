import time
from collections import namedtuple
from pprint import PrettyPrinter

call_tuple = namedtuple('call_tuple', ['args', 'kwargs', 'returned', 'execution_time'])


class WrappedFunc(object):
    def __init__(self, func, owner):
        super(WrappedFunc, self).__init__()
        self.__owner = owner
        self.__func = func
        self._wrapped_data = {
            'call_count': 0
        }

    def __call__(self, *args, **kwargs):
        start_time = time.time()
        self._wrapped_data.update({
            'last_args': args,
            'last_kwargs': kwargs,
        })
        self._wrapped_data['call_count'] += 1
        try:

            result = self.__func(*args, **kwargs)
            self._wrapped_data['last_return_value'] = result
            execution_time = (time.time() - start_time)
            self.__owner.print_padded_message(
                'Call to {} finished in {} seconds. \nCall print_wrapper_info() for more info.'.format(
                    self.__func.__name__,
                    execution_time))
        except Exception as e:
            self._wrapped_data['exception'] = e
            execution_time = (time.time() - start_time)
        finally:
            if 'result' not in locals() and 'e' in locals():
                result = e
            self.__owner._wrapped_calls[self.__func.__name__].append(
                call_tuple(args, kwargs, result, execution_time)
            )
            self.__owner._access_log.append(
                "{} called. Details: {}".format(self.__func.__name__, str(self._wrapped_data))
            )
            if 'e' in locals():
                self.__owner.print_padded_message('Exception stored. Call get_wrapper_info() for info.')
                raise e

            return result


class WrappedAttribute(object):
    def __init__(self, name, obj):
        super(WrappedAttribute, self).__init__()
        self.__name = name
        self.__obj = obj

    def log(self, message, instance):
        instance._access_log.append(
            message
        )

    def __get__(self, instance, owner):
        return self.__obj

    def __set__(self, instance, value):
        self.log("{} set to value: {}. Previous value was: {}".format(
            self.__name, str(value), str(self.__obj)), instance)
        self.__obj = value

    def __delete__(self, instance):
        self.log(self.__name + ' deleted.', instance)
        del self.__obj


class WrappedObject(object):
    def __init__(self, wrapped):
        super(WrappedObject, self).__init__()
        self._wrapped_calls = {}
        self._access_log = []
        self.__class__ = type('Wrapped_' + type(wrapped).__name__, (WrappedObject,), {})

        for attr_name in dir(wrapped):
            if not attr_name.startswith('__'):
                attr = getattr(wrapped, attr_name)
                if callable(attr):
                    self._wrapped_calls[attr_name] = []
                    setattr(self, attr_name, WrappedFunc(attr, self))
                elif attr_name not in ['_access_log', '_wrapped_calls']:
                    self._access_log.append(attr_name + ' initialized with value: ' + str(attr))
                    setattr(self.__class__, attr_name, WrappedAttribute(attr_name, attr))
                else:
                    setattr(self, attr_name, attr)
        self.print_padded_message(type(wrapped).__name__ + " wrapped.")

    def print_wrapper_info(self):
        print('Wrapper info: ')
        print('\nMethod Calls:')
        printer = PrettyPrinter(indent=2)
        printer.pprint({call: value for call, value in self._wrapped_calls.iteritems() if value})
        print('\nAccess log:')
        for l in self._access_log:
            print ('\t' + l)
        print('\nCall data can be accessed from self._wrapped_calls')
        print('Last call information can be found on the _wrapped_data attribute on individual methods.')

    def print_padded_message(self, message, closed=True, opened=True):
        self._access_log.append(message)
        if opened:
            message = ('*' * 80) + '\n' + message
        if closed:
            message += '\n' + ('*' * 80)
        print(message)

    def clear_log(self):
        del self._access_log[:]


def jwrap(object_class, *args, **kwargs):
    new_object = object_class(*args, **kwargs)
    return WrappedObject(new_object)
