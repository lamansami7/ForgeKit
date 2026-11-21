"""Keep explicitly requested JSON output machine-readable on CLI syntax errors."""

import sys
from contextvars import ContextVar
from typing import Any, Sequence

import typer
from typer.core import TyperGroup

from forgekit.output import print_json

# Older supported Typer releases use Click; current Typer releases bundle their own Click fork.
# Select the exception class actually used by the installed Typer version.
if typer.BadParameter.__module__.startswith("typer._click"):
    from typer._click.exceptions import UsageError
else:
    from click.exceptions import UsageError

_explicit_json = ContextVar("forgekit_explicit_json", default=False)


def explicit_json_requested() -> bool:
    return _explicit_json.get()


class JsonErrorGroup(TyperGroup):
    """Render parser errors as JSON when explicitly requested at any CLI level.

    Typer catches syntax exceptions inside ``main``. Calling it in non-standalone
    mode only for explicit JSON requests lets us handle those exceptions before
    Typer renders text. Ordinary, non-JSON invocations retain Typer's usual output.
    """

    def main(
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        arguments = list(sys.argv[1:] if args is None else args)
        before_separator = arguments[: arguments.index("--")] if "--" in arguments else arguments
        if "--json" not in before_separator:
            return super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=standalone_mode,
                windows_expand_args=windows_expand_args,
                **extra,
            )
        token = _explicit_json.set(True)
        try:
            try:
                result = super().main(
                    args=arguments,
                    prog_name=prog_name,
                    complete_var=complete_var,
                    standalone_mode=False,
                    windows_expand_args=windows_expand_args,
                    **extra,
                )
            except UsageError as exc:
                print_json({"error": exc.format_message()})
                if standalone_mode:
                    raise SystemExit(exc.exit_code) from exc
                raise
            except typer.Abort as exc:
                print_json({"error": "Aborted"})
                if standalone_mode:
                    code = 130 if isinstance(exc.__cause__, KeyboardInterrupt) else 1
                    raise SystemExit(code) from exc
                raise
            if standalone_mode:
                raise SystemExit(result if isinstance(result, int) else 0)
            return result
        finally:
            _explicit_json.reset(token)

    def invoke(self, ctx: typer.Context) -> Any:
        try:
            return super().invoke(ctx)
        except UsageError as exc:
            # The main callback sets this when JSON is enabled by config. It
            # also covers nested syntax errors for a top-level --json flag.
            if isinstance(ctx.obj, dict) and ctx.obj.get("json"):
                print_json({"error": exc.format_message()})
                raise typer.Exit(exc.exit_code) from exc
            raise
