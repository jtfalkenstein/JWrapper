import time
from collections import namedtuple
from pprint import PrettyPrinter
import inspect

class WrappedFunc(object):
    def __init__(self, func, owner):
        """
        Args:
            func(function): The function to wrap
            owner(WrappedObject): The containing instance wrapping this function
        """
        super(WrappedFunc, self).__init__()
        self.__owner = owner
        self.__func = func
        try:
            self.__bound = True if func.im_self is not None else False
        except AttributeError:
            self.__bound = False
        self._wrapped_data = {
            'call_count': 0
        }
        self._return_value = None

    def __call__(self, *args, **kwargs):
        start_time = time.time()
        self._wrapped_data.update({
            'last_args': args,
            'last_kwargs': kwargs,
        })
        self._wrapped_data['call_count'] += 1
        try:
            if self._return_value:
                self.__owner.print_padded_message("Faking {} value.".format(self.__func.__name__))
                if callable(self._return_value):
                    result = self._return_value(*args, **kwargs)
                else:
                    result = self._return_value
            else:
                if self.__bound and self.__owner._burrow_deep:
                    result = self.__func.im_func(self.__owner, *args, **kwargs)
                else:
                    result = self.__func(*args, **kwargs)
            self._wrapped_data['last_return_value'] = result
            execution_time = (time.time() - start_time)
        except Exception as e:
            self._wrapped_data['exception'] = e
            execution_time = (time.time() - start_time)
        finally:
            if 'result' not in locals() and 'e' in locals():
                result = e
            self.__owner._wrapped_calls[self.__func.__name__].append(
                {'args': args,
                 'kwargs': kwargs,
                 'result': result,
                 'execution_time': execution_time}
            )
            self.__owner._access_log.append(
                "->{0}() called. For details see {0}._wrapped_data".format(self.__func.__name__)
            )
            if 'e' in locals():
                self.__owner.print_padded_message('Exception stored. Call get_wrapper_info() for info.')
                raise e
            else:
                self.__owner.print_padded_message(
                    'Call to {} finished in {} seconds. \nCall print_wrapper_info() for more info.'.format(
                        self.__func.__name__,
                        execution_time))
            return result

    def fake_return_value(self, value):
        self._return_value = value

    def reset_return_value(self):
        self._return_value = None


class WrappedAttribute(object):
    def __init__(self, name, obj):
        super(WrappedAttribute, self).__init__()
        self.__name = name
        self.__obj = obj

    def log(self, message, instance):
        instance._access_log.append(
            '--' + message
        )

    def __get__(self, instance, owner):
        return self.__obj

    def __set__(self, instance, value):
        new_val_str = (str(value) if len(str(value)) < 100 else str(value)[:75] + '...')
        old_val_str = (str(self.__obj) if len(str(self.__obj)) < 100 else str(self.__obj)[:75] + '...')
        self.log("{} set to value: {}. Previous value was: {}".format(
            self.__name, new_val_str, old_val_str, instance), instance)
        self.__obj = value

    def __delete__(self, instance):
        self.log(self.__name + ' deleted.', instance)
        del self.__obj


class WrappedObject(object):
    def __init__(self, wrapped, burrow_deep=False):
        super(WrappedObject, self).__init__()
        self._wrapped_calls = {}
        self._access_log = []
        self._burrow_deep = burrow_deep
        self.__class__ = type('Wrapped_' + type(wrapped).__name__, (WrappedObject,), {})

        for attr_name in dir(wrapped):
            if not attr_name.startswith('__'):
                attr = getattr(wrapped, attr_name)
                if callable(attr):
                    self._wrapped_calls[attr_name] = []
                    setattr(self, attr_name, WrappedFunc(attr, self))
                elif attr_name not in ['_access_log', '_wrapped_calls']:
                    self._access_log.append(
                        attr_name +
                        ' initialized with value: '
                        + (str(attr) if len(str(attr)) < 100 else "VALUE TOO LONG.")
                    )
                    setattr(self.__class__, attr_name, WrappedAttribute(attr_name, attr))
                else:
                    setattr(self, attr_name, attr)
        self._access_log.append(('-' * 25) + 'INSTANTIATION COMPLETE' + ('-' * 25))
        self.print_padded_message(type(wrapped).__name__ + " wrapped.", closed=not self._burrow_deep)
        if self._burrow_deep:
            self.print_padded_message("Currently burrowing deep (self is exchanged and all calls will be logged.)" +
                                      "\nCall burrow_deep(False) to disable.", opened=False, closed=False)
            self._access_log.append('-' * 80)

    def print_wrapper_info(self):
        print('*' * 80)
        print('Wrapper info: ')
        print('\nMethod Calls:')
        printer = PrettyPrinter(indent=2)
        dict_to_report = {}
        for method, calls in self._wrapped_calls.iteritems():
            dict_to_report[method] = []
            if not calls:
                continue
            for index, call in enumerate(calls):
                dict_to_report[method].append([])
                dict_to_report[method][index] = {}
                for key, val in call.iteritems():
                    new_val = val if len(str(
                        val)) < 100 else "VALUE TOO LONG. See _wrapped_calls['{method}'][{index}]['{item}'] for actual data.".format(
                        method=method, index=index, item=key)
                    dict_to_report[method][index][key] = new_val
        printer.pprint(dict_to_report)
        print('\nAccess log:')
        for l in self._access_log:
            if ('\n' in l):
                for line in l.split('\n'):
                    print ('\t' + line)
            else:
                print('\t' + l)
        print('\nCall data can be accessed from self._wrapped_calls')
        print('Last call information can be found on the _wrapped_data attribute on individual methods.')
        print('*' * 80)

    def print_padded_message(self, message, closed=True, opened=True):
        self._access_log.append(message.split('\n')[0])
        if opened:
            message = ('*' * 80) + '\n' + message
        if closed:
            message += '\n' + ('*' * 80)
        print(message)

    def clear_log(self):
        del self._access_log[:]

    def burrow_deep(self, verbose=True):
        self._burrow_deep = verbose


def jwrap(object, burrow_deep=False, *args, **kwargs):
    if inspect.isclass(object):
        new_object = object(*args, **kwargs)
    else:
        new_object = object
    return WrappedObject(new_object, burrow_deep)
