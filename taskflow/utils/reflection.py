# -*- coding: utf-8 -*-

# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012-2013 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import inspect
import types


def get_class_name(obj):
    """Get class name for object.

    If object is a type, fully qualified name of the type is returned.
    Else, fully qualified name of the type of the object is returned.
    """
    if not isinstance(obj, type):
        obj = type(obj)
    return '.'.join((obj.__module__, obj.__name__))


def get_all_class_names(obj, up_to=object):
    """Get class names of object parent classes

    Iterate over all class names object is instance or subclass of,
    in order of method resolution (mro). If up_to parameter is provided,
    only name of classes that are sublcasses to that class are returned.
    """
    if not isinstance(obj, type):
        obj = type(obj)
    for cls in obj.mro():
        if issubclass(cls, up_to):
            yield get_class_name(cls)


def get_callable_name(function):
    """Generate a name from callable

    Tries to do the best to guess fully qualified callable name.
    """
    im_class = getattr(function, 'im_class', None)
    if im_class is not None:
        if im_class is type:
            # this is bound class method
            im_class = function.im_self
        parts = (im_class.__module__, im_class.__name__,
                 function.__name__)
    elif isinstance(function, types.FunctionType):
        parts = (function.__module__, function.__name__)
    else:
        im_class = type(function)
        if im_class is type:
            im_class = function
        parts = (im_class.__module__, im_class.__name__)
    return '.'.join(parts)


def is_bound_method(method):
    """Returns if the method given is a bound to a object or not."""
    if not inspect.ismethod(method):
        return False
    # NOTE(harlowja): instance to which this method is bound, or None
    if getattr(method, 'im_self', None) is not None:
        return True
    return False


def _get_arg_spec(function):
    if isinstance(function, type):
        bound = True
        function = function.__init__
    elif isinstance(function, (types.FunctionType, types.MethodType)):
        bound = is_bound_method(function)
        function = getattr(function, '__wrapped__', function)
    else:
        function = function.__call__
        bound = is_bound_method(function)
    return inspect.getargspec(function), bound


def get_required_callable_args(function):
    """Get names of argument required by callable"""
    argspec, bound = _get_arg_spec(function)
    f_args = argspec.args
    if argspec.defaults:
        f_args = f_args[:-len(argspec.defaults)]
    if bound:
        f_args = f_args[1:]
    return f_args


def accepts_kwargs(function):
    """Returns True if function accepts kwargs"""
    argspec, _bound = _get_arg_spec(function)
    return bool(argspec.keywords)