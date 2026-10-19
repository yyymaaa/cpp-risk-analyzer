from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IncludeDirective:
    path: str
    delimiter: str
    line_number: int


def extract_includes(file_path: Path) -> list[IncludeDirective]:
    includes: list[IncludeDirective] = []

    with file_path.open("r", encoding="utf-8", errors="ignore") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()

            if stripped.startswith('#include "'): # " because of lines like #include <vector>, we do not want to extract that
                closing_quote = stripped.find('"', len('#include "'))

                if closing_quote != -1:
                    include_path = stripped[
                        len('#include "'):closing_quote
                    ]

                    includes.append(
                        IncludeDirective(
                            path=include_path,
                            delimiter='"',
                            line_number=line_number,
                        )
                    )

                continue

            if stripped.startswith("#include <"):
                closing_bracket = stripped.find(
                    ">",
                    len("#include <"),
                )

                if closing_bracket != -1:
                    include_path = stripped[
                        len("#include <"):closing_bracket
                    ]

                includes.append(
                    IncludeDirective(
                        path=include_path,
                        delimiter="<",
                        line_number=line_number,
                    )
                )
    return includes