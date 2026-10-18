"""Python code-generation mixin for WorldLang BuiltInFunction.

Integrate it by importing this class in datatypes.py and declaring:
    class BuiltInFunction(BuiltInFunctionCodegen, BaseFunction):

Runtime execute_* methods remain unchanged. The transpiler calls these
transpile_* methods to emit Python source instead of executing the builtin.
"""

import ast
import re


class BuiltInFunctionCodegen:
    def transpile_call(self, args, transpiler):
        """Return Python expression source for this builtin call."""
        method = getattr(self, f"transpile_{self.name}", None)
        if method is None:
            raise NotImplementedError(
                f"WorldLang builtin {self.name!r} has no Python transpilation rule. "
                f"Add a transpile_{self.name}() method to BuiltInFunctionCodegen."
            )
        return method(args, transpiler)

    @classmethod
    def transpile_named(cls, name, args, transpiler):
        """Dispatch by canonical builtin name if the module is not loaded yet."""
        method = getattr(cls, f"transpile_{name}", None)
        if method is None:
            raise NotImplementedError(
                f"No Python transpilation rule exists for builtin {name!r}."
            )
        # Methods are normal instance methods; a tiny proxy supplies their self.
        return method(cls(), args, transpiler)

    @staticmethod
    def _arity(name, args, minimum=0, maximum=None):
        if len(args) < minimum:
            raise ValueError(
                f"{name}() expects at least {minimum} argument(s); got {len(args)}."
            )
        if maximum is not None and len(args) > maximum:
            raise ValueError(
                f"{name}() expects at most {maximum} argument(s); got {len(args)}."
            )

    @staticmethod
    def _arg(args, index, name):
        if len(args) <= index:
            raise ValueError(f"{name}() is missing argument {index + 1}.")
        return args[index]

    @staticmethod
    def _module_name(arg_source):
        """Require import() to receive a literal module-name string."""
        try:
            value = ast.literal_eval(arg_source)
        except (ValueError, SyntaxError):
            raise ValueError(
                "import() needs a literal string, e.g. import(\"Random\")."
            )
        if not isinstance(value, str) or not value.strip():
            raise ValueError("import() expects a non-empty module-name string.")
        return value.strip()

    # ------------------------------------------------------------------
    # Builtins with direct Python equivalents or small adaptations
    # ------------------------------------------------------------------

    def transpile_print(self, args, transpiler):
        return f"print({', '.join(args)})"

    def transpile_print_ret(self, args, transpiler):
        # The interpreter's print_ret returns a string representation of its argument list.
        return f"str([{', '.join(args)}])"

    def transpile_input(self, args, transpiler):
        self._arity("input", args, 0, 1)
        return f"input({', '.join(args)})"

    def transpile_input_int(self, args, transpiler):
        self._arity("input_int", args, 0, 1)
        transpiler.require_helper("input_int")
        return f"_wl_input_int({', '.join(args)})"

    def transpile_int_input(self, args, transpiler):
        return self.transpile_input_int(args, transpiler)

    def transpile_clear(self, args, transpiler):
        self._arity("clear", args, 0, 0)
        transpiler.require_helper("clear")
        return "_wl_clear()"

    def transpile_is_number(self, args, transpiler):
        self._arity("is_number", args, 1, 1)
        return f"isinstance({args[0]}, (int, float))"

    def transpile_is_int(self, args, transpiler):
        return self.transpile_is_number(args, transpiler)

    def transpile_is_string(self, args, transpiler):
        self._arity("is_string", args, 1, 1)
        return f"isinstance({args[0]}, str)"

    def transpile_is_str(self, args, transpiler):
        return self.transpile_is_string(args, transpiler)

    def transpile_is_dict(self, args, transpiler):
        self._arity("is_dict", args, 1, 1)
        return f"isinstance({args[0]}, dict)"

    def transpile_is_list(self, args, transpiler):
        self._arity("is_list", args, 1, 1)
        return f"isinstance({args[0]}, list)"

    def transpile_is_lst(self, args, transpiler):
        return self.transpile_is_list(args, transpiler)

    def transpile_is_function(self, args, transpiler):
        self._arity("is_function", args, 1, 1)
        return f"callable({args[0]})"

    def transpile_is_func(self, args, transpiler):
        return self.transpile_is_function(args, transpiler)

    def transpile_append(self, args, transpiler):
        self._arity("append", args, 2, 2)
        return f"({args[0]}.append({args[1]}))"

    def transpile_extend(self, args, transpiler):
        self._arity("extend", args, 2, 2)
        return f"({args[0]}.extend({args[1]}))"

    def transpile_pop(self, args, transpiler):
        self._arity("pop", args, 2, 2)
        return f"{args[0]}.pop({args[1]})"

    def transpile_len(self, args, transpiler):
        self._arity("len", args, 1, 1)
        return f"len({args[0]})"

    def transpile_sum(self, args, transpiler):
        self._arity("sum", args, 1, 1)
        return f"sum(int(_wl_item) for _wl_item in {args[0]})"

    def transpile_max(self, args, transpiler):
        self._arity("max", args, 1, 1)
        return f"max(int(_wl_item) for _wl_item in {args[0]})"

    def transpile_min(self, args, transpiler):
        self._arity("min", args, 1, 1)
        return f"min(int(_wl_item) for _wl_item in {args[0]})"

    def transpile_abs(self, args, transpiler):
        self._arity("abs", args, 1, 1)
        return f"abs(int({args[0]}))"

    def transpile_int(self, args, transpiler):
        self._arity("int", args, 1, 1)
        return f"int({args[0]})"

    def transpile_float(self, args, transpiler):
        self._arity("float", args, 1, 1)
        return f"float({args[0]})"

    def transpile_str(self, args, transpiler):
        self._arity("str", args, 1, 1)
        return f"str({args[0]})"

    def transpile_to_string(self, args, transpiler):
        self._arity("to_string", args, 1, 1)
        transpiler.require_import("json")
        return f"json.dumps({args[0]}, indent=4, ensure_ascii=False)"

    def transpile_keys(self, args, transpiler):
        self._arity("keys", args, 1, 1)
        return f"list({args[0]}.keys())"

    # ------------------------------------------------------------------
    # Filesystem / OS / timing
    # ------------------------------------------------------------------

    def transpile_readfile(self, args, transpiler):
        self._arity("readfile", args, 1, 1)
        transpiler.require_helper("readfile")
        transpiler.require_import("urllib.request")
        return f"_wl_readfile({args[0]})"

    def transpile_writefile(self, args, transpiler):
        self._arity("writefile", args, 2, 2)
        transpiler.require_helper("writefile")
        return f"_wl_writefile({args[0]}, {args[1]})"

    def transpile_readf(self, args, transpiler):
        return self.transpile_readfile(args, transpiler)

    def transpile_writef(self, args, transpiler):
        return self.transpile_writefile(args, transpiler)

    def transpile_abspath(self, args, transpiler):
        self._arity("abspath", args, 0, 0)
        transpiler.require_import("os")
        return "os.path.dirname(os.path.abspath(__file__))"

    def transpile_cwd(self, args, transpiler):
        self._arity("cwd", args, 0, 0)
        transpiler.require_import("os")
        return "os.getcwd()"

    def transpile_sleep(self, args, transpiler):
        self._arity("sleep", args, 1, 1)
        transpiler.require_import("time")
        return f"time.sleep({args[0]})"

    def transpile_chdir(self, args, transpiler):
        self._arity("chdir", args, 1, 1)
        transpiler.require_import("os")
        return f"os.chdir({args[0]})"

    def transpile_mkdir(self, args, transpiler):
        self._arity("mkdir", args, 1, 1)
        transpiler.require_import("os")
        return f"os.makedirs({args[0]}, exist_ok=True)"

    def transpile_list_dir(self, args, transpiler):
        self._arity("list_dir", args, 1, 1)
        transpiler.require_import("os")
        return f"os.listdir({args[0]})"

    def transpile_is_dir(self, args, transpiler):
        self._arity("is_dir", args, 1, 1)
        transpiler.require_import("os")
        return f"os.path.isdir({args[0]})"

    def transpile_architecture(self, args, transpiler):
        self._arity("architecture", args, 0, 0)
        transpiler.require_import("platform")
        return "platform.machine()"

    def transpile_processor(self, args, transpiler):
        self._arity("processor", args, 0, 0)
        transpiler.require_import("platform")
        return "platform.processor()"

    def transpile_move(self, args, transpiler):
        self._arity("move", args, 2, 2)
        transpiler.require_import("shutil")
        return f"shutil.move({args[0]}, {args[1]})"

    def transpile_system(self, args, transpiler):
        self._arity("system", args, 1, 1)
        transpiler.require_import("os")
        return f"os.system({args[0]})"

    # ------------------------------------------------------------------
    # String operations, common collection utilities
    # ------------------------------------------------------------------

    def transpile_split(self, args, transpiler):
        self._arity("split", args, 1, 2)
        if len(args) == 1:
            return f"{args[0]}.split()"
        return f"{args[0]}.split({args[1]})"

    def transpile_contains(self, args, transpiler):
        self._arity("contains", args, 2, 2)
        # Convention here is contains(container, item).
        return f"({args[1]} in {args[0]})"

    def transpile_uppercase(self, args, transpiler):
        self._arity("uppercase", args, 1, 1)
        return f"{args[0]}.upper()"

    def transpile_lowercase(self, args, transpiler):
        self._arity("lowercase", args, 1, 1)
        return f"{args[0]}.lower()"

    def transpile_capitalize(self, args, transpiler):
        self._arity("capitalize", args, 1, 1)
        return f"{args[0]}.capitalize()"

    def transpile_replace(self, args, transpiler):
        self._arity("replace", args, 3, 3)
        return f"{args[0]}.replace({args[1]}, {args[2]})"

    # ------------------------------------------------------------------
    # Random module: import("Random") + gen_random(min, max)
    # ------------------------------------------------------------------

    def transpile_gen_random(self, args, transpiler):
        self._arity("gen_random", args, 2, 2)
        transpiler.require_import("random")
        return f"random.randint({args[0]}, {args[1]})"

    def transpile_random(self, args, transpiler):
        # Handy if a library exposes the name `random` rather than `gen_random`.
        transpiler.require_import("random")
        if len(args) == 2:
            return f"random.randint({args[0]}, {args[1]})"
        if len(args) == 1:
            return f"random.random() * ({args[0]})"
        if not args:
            return "random.random()"
        raise ValueError("random() accepts zero, one, or two arguments.")

    # ------------------------------------------------------------------
    # Imports. import("Random") emits `import random` in the preamble.
    # ------------------------------------------------------------------

    def transpile_import(self, args, transpiler):
        self._arity("import", args, 1, 1)
        module_name = self._module_name(args[0])

        if module_name.endswith(".world"):
            if transpiler.worldlang_importer is None:
                raise NotImplementedError(
                    "import(\"file.world\") needs a worldlang_importer callback "
                    "that parses and transpiles WorldLang libraries."
                )
            generated = transpiler.worldlang_importer(module_name, transpiler)
            if generated:
                transpiler.extra_preamble.append(generated.rstrip())
            return "None"

        # WorldLang's standard library labels are traditionally TitleCase.
        # Python stdlib names such as random/math/os are lowercase.
        python_module = module_name[0].lower() + module_name[1:]
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", python_module):
            raise ValueError(f"Unsupported Python module name: {module_name!r}")
        transpiler.require_import(python_module)
        return "None"  # import() is a statement-like builtin in WorldLang.

    # ------------------------------------------------------------------
    # Integrations / optional libraries
    # ------------------------------------------------------------------

    def transpile_load_img(self, args, transpiler):
        self._arity("load_img", args, 1, 1)
        transpiler.require_helper("load_img")
        return f"_wl_load_img({args[0]})"

    def transpile_load(self, args, transpiler):
        return self.transpile_load_img(args, transpiler)

    def transpile_save_img(self, args, transpiler):
        self._arity("save_img", args, 2, 2)
        transpiler.require_helper("save_img")
        return f"_wl_save_img({args[0]}, {args[1]})"

    def transpile_send(self, args, transpiler):
        self._arity("send", args, 3, 3)
        transpiler.require_helper("send")
        return f"_wl_send({', '.join(args)})"

    def transpile_listen(self, args, transpiler):
        self._arity("listen", args, 0, 0)
        transpiler.require_helper("listen")
        return "_wl_listen()"

    def transpile_speak(self, args, transpiler):
        self._arity("speak", args, 1, 1)
        transpiler.require_helper("speak")
        return f"_wl_speak({args[0]})"

    def transpile_mouse_location(self, args, transpiler):
        self._arity("mouse_location", args, 0, 0)
        transpiler.require_import("pyautogui")
        return "pyautogui.position()"

    def transpile_set_location(self, args, transpiler):
        self._arity("set_location", args, 2, 2)
        transpiler.require_import("pyautogui")
        return f"pyautogui.moveTo({args[0]}, {args[1]})"

    def transpile_press(self, args, transpiler):
        self._arity("press", args, 1, 1)
        transpiler.require_import("pyautogui")
        return f"pyautogui.press({args[0]})"

    def transpile_write(self, args, transpiler):
        self._arity("write", args, 1, 1)
        transpiler.require_import("pyautogui")
        return f"pyautogui.write(str({args[0]}))"

    def transpile_click(self, args, transpiler):
        self._arity("click", args, 0, 2)
        transpiler.require_import("pyautogui")
        return f"pyautogui.click({', '.join(args)})"

    def transpile_visit(self, args, transpiler):
        self._arity("visit", args, 1, 1)
        transpiler.require_import("webbrowser")
        return f"webbrowser.open({args[0]})"

    # ------------------------------------------------------------------
    # Existing WorldLang-specific operations
    # ------------------------------------------------------------------

    def transpile_python(self, args, transpiler):
        self._arity("python", args, 1, 1)
        return f"exec({args[0]})"

    def transpile_exec(self, args, transpiler):
        raise NotImplementedError(
            "WorldLang exec() evaluates WorldLang source at runtime; it is not "
            "the same as Python exec(). Use python(code) for embedded Python, "
            "or provide a runtime compiler hook."
        )

    def transpile_eval(self, args, transpiler):
        raise NotImplementedError(
            "WorldLang eval() evaluates WorldLang source at runtime. It needs "
            "a runtime compiler hook and cannot safely be replaced with Python eval()."
        )

    def transpile_run(self, args, transpiler):
        raise NotImplementedError(
            "run() executes a WorldLang file. Add a worldlang_importer/runtime "
            "hook to support dynamic WorldLang file execution in generated Python."
        )

    def transpile_run_ext(self, args, transpiler):
        raise NotImplementedError(
            "run_ext() executes a WorldLang extension dynamically and needs a runtime hook."
        )

    def transpile_translate(self, args, transpiler):
        raise NotImplementedError(
            "translate() translates WorldLang source between natural languages; "
            "it has no direct Python equivalent."
        )

    def transpile_exit(self, args, transpiler):
        self._arity("exit", args, 0, 0)
        return "raise SystemExit"

    def transpile_generate(self, args, transpiler):
        raise NotImplementedError(
            "generate() is project-specific; add a transpile_generate() method "
            "matching the actual builtin's arguments and behavior."
        )

    def transpile_receive(self, args, transpiler):
        raise NotImplementedError(
            "receive() is project-specific; add a transpile_receive() method "
            "matching the actual builtin's arguments and behavior."
        )

    def transpile_plot(self, args, transpiler):
        raise NotImplementedError(
            "plot() is plotting-library-specific; add a rule matching your plotting module."
        )

    def transpile_plotting_mode(self, args, transpiler):
        raise NotImplementedError(
            "plotting_mode() is plotting-library-specific; add a rule matching your plotting module."
        )
