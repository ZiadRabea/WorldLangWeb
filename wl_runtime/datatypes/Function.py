from .Value import *
import os
import sys
import requests
import json
import time
import importlib
from wl_runtime.BuiltInFunctionCodegen import BuiltInFunctionCodegen


if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))

class BaseFunction(Value):
    def __init__(self, name):
        super().__init__()
        self.name = name or "<anonymous>"

    def generate_new_context(self):
        new_context = Context(self.name, self.context, self.pos_start)
        new_context.symbol_table = SymbolTable(new_context.parent.symbol_table)
        return new_context

    def check_args(self, infinite, accept_none, arg_names, args):
        res = RTResult()

        if len(args) > len(arg_names):
            if infinite:
                return res.success(None)
            return res.failure(RTError(
                self.pos_start, self.pos_end,
                f"{len(args) - len(arg_names)} too many args passed into {self}",
                self.context
            ))

        if len(args) < len(arg_names):
            if len(arg_names) == 1 and accept_none:
                return res.success(None)
            else:
                return res.failure(RTError(
                    self.pos_start, self.pos_end,
                    f"{len(arg_names) - len(args)} too few args passed into {self}",
                    self.context
                ))

        return res.success(None)

    def populate_args(self, infinite, arg_names, args, exec_ctx):
        for i in range(len(args)):
            if infinite:
                arg_name = arg_names[0]
                # print(x for x in args)
                arg_value = List([x for x in args])
            else:
                arg_name = arg_names[i]
                arg_value = args[i]

            arg_value.set_context(exec_ctx)
            exec_ctx.symbol_table.set(arg_name, arg_value)

    def check_and_populate_args(self, infinite, accept_none, arg_names, args, exec_ctx):
        res = RTResult()
        res.register(self.check_args(infinite, accept_none, arg_names, args))
        if res.should_return(): return res
        self.populate_args(infinite, arg_names, args, exec_ctx)
        return res.success(None)
      
class BuiltInFunction(BuiltInFunctionCodegen, BaseFunction):
    def __init__(self, name, data_dict=None, runner=None, translator=None):
        super().__init__(name)
        self.data_dict = data_dict
        self.runner = runner
        self.translator = translator

    def execute(self, args):
        res = RTResult()
        exec_ctx = self.generate_new_context()

        method_name = f'execute_{self.name}'
        method = getattr(self, method_name, self.no_visit_method)

        res.register(
            self.check_and_populate_args(method.infinite, method.accept_none, method.arg_names, args, exec_ctx))
        if res.should_return(): return res

        return_value = res.register(method(exec_ctx))
        if res.should_return(): return res
        return res.success(return_value)

    def no_visit_method(self, node, context):
        raise Exception(f'No execute_{self.name} method defined')

    def copy(self):
        copy = BuiltInFunction(self.name, self.data_dict, self.runner, self.translator)
        copy.set_context(self.context)
        copy.set_pos(self.pos_start, self.pos_end)
        return copy

    def __repr__(self):
        return f"<built-in function {self.name}>"