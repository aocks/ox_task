"""Tools to find useful things.
"""

import logging

from ox_task.core import noters

class FindBuiltinNoter:

    def lookup(self, name):
        _ = self
        result = getattr(noters, name, None)
        return result

    def __call__(self, name):
        return self.lookup(name)
        

class TaskNoteFinder:

    _lookup_funcs = {
        '__default__': FindBuiltinNoter()
        }

    @classmethod
    def add_lookup_functor(cls, name, functor):
        if name in cls._lookup_funcs:
            raise ValueError('Lookup function {name} already exists.')
        cls._lookup_funcs[name] = functor

    @classmethod
    def del_lookup_functor(cls, name):
        cls._lookup_funcs.pop(name, None)

    @classmethod
    def find_noter(cls, name):
        for functor_name, functor in cls._lookup_funcs.items():
            logging.debug('Looking up noter %s using %s', name, functor_name)
            result = functor(name)
            if result is not None:
                return result
        raise KeyError(name)
        
    
