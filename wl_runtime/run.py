from .Interpreter import *

def run(fn, text, language):
    # Generate tokens
    print(text)
    lexer = Lexer(fn, text, language)
    data_dict, tokens, error = lexer.make_tokens()
    if error: return None, error

    # Generate AST
    parser = Parser(tokens, data_dict)
    ast = parser.parse()
    print(ast.node)
    if ast.error: return None, ast.error

    # Run program
    transpiler = Transpiler(data_dict)
    context = Context('<program>', data_dict)

    result = transpiler.transpile(ast.node, context)

    if result.error:
        print(result.error)
    else:
        python_source = result.value
        print(python_source)
    return result.value, result.error

