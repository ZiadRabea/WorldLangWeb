# views.py

import json

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from django.views.decorators.http import require_POST

# Adjust this import to wherever your WorldLang run() function lives.
from wl_runtime import run


@require_POST
@csrf_exempt
def worldlang_api(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            "python": None,
            "result": None,
            "error": "Invalid JSON request body."
        }, status=400)

    code = payload.get("code")
    language = payload.get("language") or payload.get("lang") or "English"

    if not isinstance(code, str) or not code.strip():
        return JsonResponse({
            "python": None,
            "result": None,
            "error": "Missing or empty WorldLang source code."
        }, status=400)

    if not isinstance(language, str):
        return JsonResponse({
            "python": None,
            "result": None,
            "error": "Language must be a string."
        }, status=400)

    # Convert frontend tags such as French_KW to French,
    # if that is what your run() function expects.
    language = language.removesuffix("_KW")

    try:
        result, error = run.run(
            "<stdin>",
            code,
            language=language
        )

        if error:
            error_text = (
                error.as_string()
                if hasattr(error, "as_string")
                else str(error)
            )

            return JsonResponse({
                "python": None,
                "result": None,
                "error": error_text
            }, status=200)

        if not isinstance(result, str):
            return JsonResponse({
                "python": None,
                "result": None,
                "error": (
                    "WorldLang did not return transpiled Python source. "
                    "Check the return value of run()."
                )
            }, status=500)

        return JsonResponse({
            "python": result,
            "result": None,
            "error": None
        })

    except Exception as exc:
        return JsonResponse({
            "python": None,
            "result": None,
            "error": str(exc)
        }, status=500)
