import re
from dataclasses import dataclass
from pathlib import Path


INCLUDE_RE = re.compile(r'^\s*#\s*include\s*(?P<open>["<])(?P<path>[^">]+)(?P<close>[">])')
CLOSING = {'"': '"', "<": ">"}


@dataclass(frozen=True)
class IncludeDirective:
    """Represents a parsed C++ include directive
    """
    path: str
    delimiter: str
    line_number: int


def extract_includes(file_path: Path) -> list[IncludeDirective]:
    """Extracts all include directives from a given C++ source file

    Args:
        file_path (Path): the path to the C++ source file to parse

    Returns:
        list[IncludeDirective]: a list of extracted include directives
    """
    includes: list[IncludeDirective] = []

    with file_path.open("r", encoding="utf-8", errors="ignore") as file:
        for line_number, line in enumerate(file, start=1):
            # Matches `#include "x.h"`, `#include <x.h>` and valid spacing variants such as
            # `#  include "x.h"` or `#include<x.h>`. Lines without a closing delimiter are skipped.
            match = INCLUDE_RE.match(line)
            if match and CLOSING[match.group("open")] == match.group("close"):
                includes.append(
                    IncludeDirective(
                        path=match.group("path"),
                        delimiter=match.group("open"),
                        line_number=line_number,
                    )
                )

    return includes