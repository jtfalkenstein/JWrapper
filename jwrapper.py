from __future__ import print_function

import __builtin__
import inspect
import time
import traceback
from pprint import PrettyPrinter
from datetime import datetime, timedelta


def timer():
    initialized = datetime.now()
    yield initialized
    while True:
        if initialized - datetime.now() >= timedelta(minutes=5):
            reset = (yield datetime.now())
            if reset:
                initialized = datetime.now()
        else:
            yield ""


class Printer(object):
    _printing_progress = False
    _printer = PrettyPrinter(indent=1)
    _progress_char_count = 0
    _timer = timer()

    @classmethod
    def stop_printing_progress(cls):
        if cls._printing_progress:
            print('\n')
            cls._printing_progress = False

    @classmethod
    def print_progress(cls, symbol='.'):
        if symbol != '.':
            print(cls._timer.next(), end='')
        cls._printing_progress = True
        cls._progress_char_count += 1
        if cls._progress_char_count > 80:
            cls._progress_char_count = 0
            print('\n' + symbol, end='')
            return
        print(symbol, end='')

    @classmethod
    def print_padded_message(cls, message, closed=True, opened=True):
        cls.stop_printing_progress()
        to_log = message.split('\n')[0]
        print((('*' * 80) + '\n' if opened else "") + message + ('\n' + ('*' * 80) if closed else ""))
        return to_log

    @classmethod
    def print_message(cls, message):
        cls.stop_printing_progress()
        cls._printer.pprint(message)


class WrappedFunc(object):
    def __init__(self, func, owner):
        """
        Args:
            func(function): The function to wrap
            owner(WrappedObject): The containing instance wrapping this function
        """
        super(WrappedFunc, self).__init__()
        self._owner = owner
        self._orig_func = func
        self._is_bound = True if inspect.ismethod(func) else False
        self._wrapped_data = {
            'call_count': 0,
            'calls': []
        }
        self._return_value = None
        self._alert = False

    def __call__(self, *args, **kwargs):
        Printer.print_progress('-')
        if self._alert:
            Printer.print_padded_message("!!! {} was called.".format(self._orig_func.__name__))
        start_time = time.time()
        self._wrapped_data['last_call'] = {
            'args': args,
            'kwargs': kwargs,
        }
        self._wrapped_data['call_count'] += 1
        try:
            if self._return_value:
                self._owner._access_log.append(
                    Printer.print_padded_message("Faking {} value.".format(self._orig_func.__name__)))
                if callable(self._return_value):
                    result = self._return_value(*args, **kwargs)
                else:
                    result = self._return_value
            else:
                # If the function is method and the WrappedObject is set to burrow deep...
                if self._is_bound and self._owner._burrow_deep:
                    # Use the WrappedObject as the value of "self" rather than the
                    # encapsulated object the method is bound to
                    result = self._orig_func.im_func(self._owner, *args, **kwargs)
                else:
                    # Otherwise, call the function regularly
                    result = self._orig_func(*args, **kwargs)
            self._wrapped_data['last_call']['return_value'] = result
            execution_time = (time.time() - start_time)
        except Exception as e:
            self._wrapped_data['exception'] = e
            execution_time = (time.time() - start_time)
        finally:
            if 'result' not in locals() and 'e' in locals():
                result = e
            call_info = {
                'function': self._orig_func.__name__,
                'args': args,
                'kwargs': kwargs,
                'result': result,
                'execution_time': execution_time
            }
            self._owner._wrapped_calls.get(self._orig_func.__name__, []).append(call_info)
            self._wrapped_data['calls'].append(call_info)
            self._owner._access_log.append(
                "-> {0}() called. For details see {0}._wrapped_data. Timing: {1}".format(self._orig_func.__name__,
                                                                                         execution_time)
            )
            if 'e' in locals():
                if not self._owner._last_failure:
                    call_info['traceback'] = traceback.format_exc()
                    self._owner._last_failure = call_info
                    log_message = 'Exception stored: {}.\nCall print_last_failure() for info.'.format(str(e))
                    self._owner._access_log.append(log_message)
                    Printer.print_padded_message(log_message)
                raise e
            return result

    def fake_return_value(self, value):
        self._return_value = value

    def reset_return_value(self):
        self._return_value = None

    def get_call_args(self):
        return inspect.getcallargs(self._orig_func)

    def print_call_data(self):
        Printer.print_message("-" * 80)
        Printer.print_message("Call data for " + self._orig_func.__name__ + ":")
        Printer.print_message("Access call data on _wrapped_data.")
        print('\n')
        cleaned_data = []
        for index, call in enumerate(self._wrapped_data['calls']):
            call_data = {}
            for key, val in call.items():
                newVal = val if len(str(val)) < 100 \
                    else "VALUE TOO LONG. See {}._wrapped_data['calls'][{}]['{}'] for value.".format(
                    self._orig_func.__name__, index, key)
                call_data[key] = newVal
            cleaned_data.append(call_data)
        Printer.print_message(cleaned_data)
        Printer.print_message('-' * 80)

    def set_alert(self, on=True):
        self._alert = on


class WrappedAttribute(object):
    def __init__(self, name, obj):
        super(WrappedAttribute, self).__init__()
        self.__name = name
        self.__obj = obj

    def _log(self, message, instance):
        instance._access_log.append(
            '-- ' + message
        )

    def __get__(self, instance, owner):
        Printer.print_progress()
        return self.__obj

    def __set__(self, instance, value):
        Printer.print_progress()
        new_val_str = (str(value) if len(str(value)) < 100 else str(value)[:75] + '...')
        old_val_str = (str(self.__obj) if len(str(self.__obj)) < 100 else str(self.__obj)[:75] + '...')
        self._log("{} set to value: {}. Previous value was: {}".format(
            self.__name, new_val_str, old_val_str, instance), instance)
        self.__obj = value

    def __delete__(self, instance):
        Printer.print_progress()
        self._log(self.__name + ' deleted.', instance)
        del self.__obj


class WrappedObject(object):
    def __init__(self, wrapped, burrow_deep=False):
        super(WrappedObject, self).__init__()
        __builtin__.print_last_failure = self.print_last_failure
        self._wrapped_calls = {}
        self._access_log = []
        self._burrow_deep = burrow_deep
        self._last_failure = {}
        self.__class__ = type('Wrapped_' + type(wrapped).__name__, (WrappedObject,), {})
        self._wrapped = wrapped

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
            elif attr_name in ['__enter__', '__exit__']:
                original = getattr(wrapped, attr_name)
                new_method = WrappedFunc(original, self)
                setattr(self.__class__, attr_name, new_method)
        self._access_log.append(('-' * 25) + 'INSTANTIATION COMPLETE' + ('-' * 25))
        self._access_log.append(
            Printer.print_padded_message(type(wrapped).__name__ + " wrapped.", closed=not self._burrow_deep))
        if self._burrow_deep:
            self._access_log.append(Printer.print_padded_message(
                "Currently burrowing deep (self is exchanged and all calls will be logged.)" +
                '\nCall burrow_deep(False) to disable.', opened=False, closed=False))
            self._access_log.append('-' * 80)

    def print_wrapper_info(self):
        Printer.print_message('*' * 80)
        Printer.print_message('Wrapper info: ')
        print('Method Calls:')
        printer = PrettyPrinter(indent=2)
        dict_to_report = {}
        for method, calls in self._wrapped_calls.items():
            if not calls:
                continue
            dict_to_report[method] = []
            for index, call in enumerate(calls):
                dict_to_report[method].append([])
                dict_to_report[method][index] = {}
                for key, val in call.items():
                    new_val = val if len(str(
                        val)) < 100 else "VALUE TOO LONG. See _wrapped_calls['{method}'][{index}]['{item}'] for actual data.".format(
                        method=method, index=index, item=key)
                    dict_to_report[method][index][key] = new_val
        Printer.print_message(dict_to_report)
        Printer.print_message('\nAccess log:')
        for l in self._access_log:
            if ('\n' in l):
                for line in l.split('\n'):
                    print('\t' + line)
            else:
                print('\t' + l)
        print('\nCall data can be accessed from self._wrapped_calls')
        print(
            'Last call information can be found on the _wrapped_data attribute on individual methods.')
        print('*' * 80)

    def print_last_failure(self):
        dict_minus_tb = {k: v for k, v in self._last_failure.items() if not k == 'traceback'}
        formatted_dict = PrettyPrinter().pformat(dict_minus_tb)
        tb = self._last_failure['traceback']
        print('Failure info:\n' + formatted_dict)
        print(tb)

    def clear_log(self):
        del self._access_log[:]

    def burrow_deep(self, activated=True):
        self._burrow_deep = activated

    def get_unwrapped(self):
        unwrapped = self._wrapped
        for attr_name in dir(self):
            orig = getattr(self, attr_name)
            if inspect.isdatadescriptor(orig):
                setattr(unwrapped, attr_name, orig)
        unwrapped._rewrap = lambda: jwrap(unwrapped, self._burrow_deep)
        return unwrapped


def jwrap(cls_or_obj, burrow_deep=False, *args, **kwargs):
    if inspect.isclass(cls_or_obj):
        new_object = cls_or_obj(*args, **kwargs)
    else:
        new_object = cls_or_obj
    return WrappedObject(new_object, burrow_deep)
