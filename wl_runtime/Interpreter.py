import keyword
import re

from .RT_result import *
from .Tokens import *
from .Parser import *
from .Lexer import *
from .Errors import *
from .datatypes import *
from .BuiltInFunctionCodegen import BuiltInFunctionCodegen


class Transpiler:
    INDENT = "    "

    STATEMENT_NODES = (
        VarAssignNode,
        IfNode,
        ForNode,
        WhileNode,
        FuncDefNode,
        ReturnNode,
        BreakNode,
        ContinueNode,
    )

    HELPER_SOURCES = {
        "input_int": '''def _wl_input_int(prompt=""):
    while True:
        text = input(prompt)
        try:
            return int(text)
        except ValueError:
            print(f"{text!r} must be an integer. Try again!")
''',
        "clear": '''def _wl_clear():
    import os
    os.system("cls" if os.name == "nt" else "clear")
    return None
''',
        "range": '''def _wl_range(start, end, step=1):
    if step == 0:
        raise ValueError("WorldLang range step cannot be zero")
    current = start
    if step > 0:
        while current < end:
            yield current
            current += step
    else:
        while current > end:
            yield current
            current += step
''',
        "readfile": '''def _wl_readfile(path):
    path = str(path)
    if path.startswith(("http://", "https://")):
        with urllib.request.urlopen(path) as response:
            return response.read().decode("utf-8")
    with open(path, "r", encoding="utf-8") as file:
        return file.read()
''',
        "writefile": '''def _wl_writefile(path, content):
    with open(path, "w", encoding="utf-8") as file:
        file.write(str(content))
    return None
''',
        "load_img": '''def _wl_load_img(path):
    print("يبدوا أنك نسيت استدعاء مكتبة (Image)")
    return None
''',
        "save_img": '''def _wl_save_img(values, path):
    print("يبدوا أنك نسيت استدعاء مكتبة (Image)")
    return None
''',
        "send": '''def _wl_send(com, port, data):
    print("يبدوا انك نسيت استدعاء المكتبة (Serial)")
    return None
''',
        "listen": '''def _wl_listen():
    print("يبدوا انك نسيت استدعاء المكتبة (Speech)")
    return None
''',
        "speak": '''def _wl_speak(text):
    print("يبدوا انك نسيت استدعاء المكتبة (Speech)")
    return None
''',
    }

    def __init__(self, data_dict, symbol_table=None, worldlang_importer=None):
        self.data_dict = data_dict or {}
        self.symbol_table = symbol_table
        self.worldlang_importer = worldlang_importer
        self.indent_level = 0
        self.imports = set()
        self.helpers = set()
        self.extra_preamble = []

        # This reverse lookup is for language keywords/constants only and for
        # finding a builtin's canonical name when its module hasn't been loaded.
        self.source_to_canonical = {
            translated: canonical
            for canonical, translated in self.data_dict.items()
        }

    def visit(self, node, context=None):
        method_name = f"visit_{type(node).__name__}"
        method = getattr(self, method_name, self.no_visit_method)
        return method(node, context)

    def no_visit_method(self, node, context):
        raise Exception(f"No visit_{type(node).__name__} method defined")

    def indent(self):
        return self.INDENT * self.indent_level

    def require_import(self, module_name):
        self.imports.add(module_name)

    def require_helper(self, helper_name):
        if helper_name not in self.HELPER_SOURCES:
            raise ValueError(f"Unknown WorldLang transpiler helper: {helper_name}")
        self.helpers.add(helper_name)

    def target_identifier(self, name):
        """Make an identifier legal in Python while preserving Unicode letters."""
        name = str(name)
        name = re.sub(r"\W", "_", name, flags=re.UNICODE)
        if not name:
            name = "_wl_name"
        elif name[0].isdigit():
            name = f"_wl_{name}"
        elif keyword.iskeyword(name):
            name += "_"
        else:
            name = "wl_var_"+name.encode('ascii', errors='backslashreplace').decode('ascii').replace("\\","")
        
        return name
        
    def _lookup_symbol(self, name, context=None):
        possible_tables = []
        if context is not None:
            possible_tables.append(getattr(context, "symbol_table", context))
        if self.symbol_table is not None:
            possible_tables.append(self.symbol_table)

        for table in possible_tables:
            if table is None or not hasattr(table, "get"):
                continue
            try:
                value = table.get(name)
            except Exception:
                value = None
            if value is not None:
                return value
        return None

    def emit_statement(self, node, context=None):
        res = RTResult()
        try:
            code = res.register(self.visit(node, context))
        except (NotImplementedError, ValueError) as exc:
            return res.failure(Exception(str(exc)))
        if res.should_return():
            return res
        # import(...) is a statement-like WorldLang builtin. Its native Python
        # import has been collected in the preamble, so omit its placeholder line.
        if isinstance(node, CallNode) and code == "None":
            return res.success("")
        if not isinstance(node, self.STATEMENT_NODES):
            code = self.indent() + code
        return res.success(code)

    def emit_suite(self, node, context=None, is_statement_block=True):
        res = RTResult()
        lines = []

        if is_statement_block and isinstance(node, ListNode):
            for child in node.element_nodes:
                code = res.register(self.emit_statement(child, context))
                if res.should_return():
                    return res
                if code:
                    lines.append(code)
        else:
            code = res.register(self.emit_statement(node, context))
            if res.should_return():
                return res
            if code:
                lines.append(code)

        if not lines:
            lines.append(self.indent() + "pass")
        return res.success("\n".join(lines))

    def transpile(self, node, context=None):
        """Compile the AST and prepend imports/support helpers discovered in it."""
        self.indent_level = 0
        self.imports.clear()
        self.helpers.clear()
        self.extra_preamble.clear()

        statements = node.element_nodes if isinstance(node, ListNode) else [node]
        res = RTResult()
        body_lines = []
        for statement in statements:
            code = res.register(self.emit_statement(statement, context))
            if res.should_return():
                return res
            if code:
                body_lines.append(code)

        preamble = [f"import {name}" for name in sorted(self.imports)]
        for helper_name in sorted(self.helpers):
            preamble.append(self.HELPER_SOURCES[helper_name].rstrip())
        preamble.extend(item for item in self.extra_preamble if item)

        sections = []
        if preamble:
            sections.append("\n\n".join(preamble))
        if body_lines:
            sections.append("\n".join(body_lines))
        return res.success("\n\n".join(sections))

    # ------------------------------------------------------------------
    # Literals
    # ------------------------------------------------------------------

    def visit_NumberNode(self, node, context):
        return RTResult().success(repr(node.tok.value))

    def visit_StringNode(self, node, context):
        return RTResult().success(repr(node.tok.value))

    def visit_ListNode(self, node, context):
        res = RTResult()
        elements = []
        for child in node.element_nodes:
            elements.append(res.register(self.visit(child, context)))
            if res.should_return():
                return res
        return res.success(f"[{', '.join(elements)}]")

    def visit_DictNode(self, node, context):
        res = RTResult()
        elements = []
        for key_node, value_node in node.key_value_pairs:
            key = res.register(self.visit(key_node, context))
            if res.should_return():
                return res
            value = res.register(self.visit(value_node, context))
            if res.should_return():
                return res
            elements.append(f"{key}: {value}")
        return res.success(f"{{{', '.join(elements)}}}")

    # ------------------------------------------------------------------
    # Variables and names
    # ------------------------------------------------------------------

    def visit_VarAccessNode(self, node, context):
        source_name = node.var_name_tok.value
        canonical = self.source_to_canonical.get(source_name, source_name)

        if canonical == "true":
            return RTResult().success("True")
        if canonical == "false":
            return RTResult().success("False")
        if canonical == "null":
            return RTResult().success("None")
        if source_name == "MATH_PI":
            self.require_import("math")
            return RTResult().success("math.pi")

        return RTResult().success(self.target_identifier(source_name))

    def visit_VarAssignNode(self, node, context):
        res = RTResult()
        name = self.target_identifier(node.var_name_tok.value)
        value = res.register(self.visit(node.value_node, context))
        if res.should_return():
            return res
        return res.success(f"{self.indent()}{name} = {value}")

    # ------------------------------------------------------------------
    # Operators
    # ------------------------------------------------------------------

    def visit_BinOpNode(self, node, context):
        res = RTResult()
        left = res.register(self.visit(node.left_node, context))
        if res.should_return():
            return res
        right = res.register(self.visit(node.right_node, context))
        if res.should_return():
            return res

        operators = {
            TT_PLUS: "+", TT_MINUS: "-", TT_MUL: "*", TT_DIV: "/",
            TT_POW: "**", TT_EE: "==", TT_NE: "!=", TT_LT: "<",
            TT_GT: ">", TT_LTE: "<=", TT_GTE: ">=",
        }
        op = operators.get(node.op_tok.type)
        if op is None:
            if node.op_tok.matches(TT_KEYWORD, self.data_dict.get("and")):
                op = "and"
            elif node.op_tok.matches(TT_KEYWORD, self.data_dict.get("or")):
                op = "or"
            else:
                return res.failure(Exception(f"Unsupported operator: {node.op_tok}"))
        return res.success(f"({left} {op} {right})")

    def visit_UnaryOpNode(self, node, context):
        res = RTResult()
        value = res.register(self.visit(node.node, context))
        if res.should_return():
            return res
        if node.op_tok.type == TT_MINUS:
            result = f"(-{value})"
        elif node.op_tok.matches(TT_KEYWORD, self.data_dict.get("not")):
            result = f"(not {value})"
        else:
            return res.failure(Exception(f"Unsupported unary operator: {node.op_tok}"))
        return res.success(result)

    # ------------------------------------------------------------------
    # Conditionals and loops
    # ------------------------------------------------------------------

    def visit_IfNode(self, node, context):
        res = RTResult()
        lines = []
        for index, (condition, body, should_return_null) in enumerate(node.cases):
            condition_code = res.register(self.visit(condition, context))
            if res.should_return():
                return res
            keyword_ = "if" if index == 0 else "elif"
            lines.append(f"{self.indent()}{keyword_} {condition_code}:")
            self.indent_level += 1
            body_code = res.register(self.emit_suite(body, context, should_return_null))
            self.indent_level -= 1
            if res.should_return():
                return res
            lines.append(body_code)

        if node.else_case:
            body, should_return_null = node.else_case
            lines.append(f"{self.indent()}else:")
            self.indent_level += 1
            body_code = res.register(self.emit_suite(body, context, should_return_null))
            self.indent_level -= 1
            if res.should_return():
                return res
            lines.append(body_code)
        return res.success("\n".join(lines))

    def visit_ForNode(self, node, context):
        res = RTResult()
        start = res.register(self.visit(node.start_value_node, context))
        if res.should_return():
            return res
        end = res.register(self.visit(node.end_value_node, context))
        if res.should_return():
            return res
        if node.step_value_node:
            step = res.register(self.visit(node.step_value_node, context))
            if res.should_return():
                return res
        else:
            step = "1"

        self.require_helper("range")
        var_name = self.target_identifier(node.var_name_tok.value)
        header = f"{self.indent()}for {var_name} in _wl_range({start}, {end}, {step}):"
        self.indent_level += 1
        body = res.register(self.emit_suite(node.body_node, context, node.should_return_null))
        self.indent_level -= 1
        if res.should_return():
            return res
        return res.success(f"{header}\n{body}")

    def visit_WhileNode(self, node, context):
        res = RTResult()
        condition = res.register(self.visit(node.condition_node, context))
        if res.should_return():
            return res
        header = f"{self.indent()}while {condition}:"
        self.indent_level += 1
        body = res.register(self.emit_suite(node.body_node, context, node.should_return_null))
        self.indent_level -= 1
        if res.should_return():
            return res
        return res.success(f"{header}\n{body}")

    # ------------------------------------------------------------------
    # Functions and calls
    # ------------------------------------------------------------------

    def visit_FuncDefNode(self, node, context):
        res = RTResult()
        args = [self.target_identifier(arg.value) for arg in node.arg_name_toks]

        if not node.var_name_tok:
            if not node.should_auto_return:
                return res.failure(Exception(
                    "Anonymous block functions cannot be represented as Python lambdas. "
                    "Use an expression-bodied anonymous function."
                ))
            body = res.register(self.visit(node.body_node, context))
            if res.should_return():
                return res
            return res.success(f"lambda {', '.join(args)}: {body}")

        name = self.target_identifier(node.var_name_tok.value)
        header = f"{self.indent()}def {name}({', '.join(args)}):"
        self.indent_level += 1
        if node.should_auto_return:
            value = res.register(self.visit(node.body_node, context))
            if res.should_return():
                self.indent_level -= 1
                return res
            body = f"{self.indent()}return {value}"
        else:
            body = res.register(self.emit_suite(node.body_node, context, True))
            if res.should_return():
                self.indent_level -= 1
                return res
        self.indent_level -= 1
        return res.success(f"{header}\n{body}")

    def visit_CallNode(self, node, context):
        res = RTResult()
        call_node = node.node_to_call
        args = []
        for arg_node in node.arg_nodes:
            args.append(res.register(self.visit(arg_node, context)))
            if res.should_return():
                return res

        if isinstance(call_node, VarAccessNode):
            source_name = call_node.var_name_tok.value
            symbol = self._lookup_symbol(source_name, context)

            if isinstance(symbol, BuiltInFunction):
                try:
                    code = symbol.transpile_call(args, self)
                    return res.success(code)
                except (NotImplementedError, ValueError) as exc:
                    return res.failure(Exception(str(exc)))

            # The module may not yet have been loaded while transpiling an
            # import("Random") at the top of the source file. Method-based
            # dispatch still lets known builtins generate Python without a map.
            canonical = self.source_to_canonical.get(source_name, source_name)
            if hasattr(BuiltInFunctionCodegen, f"transpile_{canonical}"):
                try:
                    code = BuiltInFunctionCodegen.transpile_named(canonical, args, self)
                    return res.success(code)
                except (NotImplementedError, ValueError) as exc:
                    return res.failure(Exception(str(exc)))

        function = res.register(self.visit(call_node, context))
        if res.should_return():
            return res
        return res.success(f"{function}({', '.join(args)})")

    # ------------------------------------------------------------------
    # Control flow
    # ------------------------------------------------------------------

    def visit_ReturnNode(self, node, context):
        if node.node_to_return is None:
            return RTResult().success(f"{self.indent()}return")
        res = RTResult()
        value = res.register(self.visit(node.node_to_return, context))
        if res.should_return():
            return res
        return res.success(f"{self.indent()}return {value}")

    def visit_ContinueNode(self, node, context):
        return RTResult().success(f"{self.indent()}continue")

    def visit_BreakNode(self, node, context):
        return RTResult().success(f"{self.indent()}break")
