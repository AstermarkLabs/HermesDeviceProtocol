"""FR-32: `hdp-spec/errors.md` (the normative doc) must be identical to `hdp_proto.errors`
(the executable copy) — same code set, same declaration order, same hint text. This test parses
`errors.md`'s `## \`code\`` / `- **Hint:**` structure and diffs it against `ErrorCode`/`HINTS`
rather than trusting the two were kept in sync by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

from hdp_proto.errors import HINTS, ErrorCode

ERRORS_MD = Path(__file__).resolve().parent.parent / "errors.md"


def _parse_errors_md() -> list[tuple[str, str]]:
    text = ERRORS_MD.read_text()
    sections = re.split(r"\n## `", text)[1:]  # drop the preamble before the first entry
    entries: list[tuple[str, str]] = []
    for section in sections:
        code, _, body = section.partition("`\n")
        hint_match = re.search(r"- \*\*Hint:\*\*(.*?)(?=\n## `|\Z)", body, re.DOTALL)
        assert hint_match is not None, f"errors.md entry {code!r} is missing a Hint field"
        hint_lines = [line.strip() for line in hint_match.group(1).strip().splitlines()]
        hint = " ".join(line for line in hint_lines if line)
        entries.append((code, hint))
    return entries


def test_errors_md_code_set_and_order_match_error_code():
    parsed_codes = [code for code, _ in _parse_errors_md()]
    expected_codes = [member.value for member in ErrorCode]
    assert parsed_codes == expected_codes


def test_errors_md_hints_match_hints_dict():
    for code, hint in _parse_errors_md():
        expected = HINTS[ErrorCode(code)]
        assert hint == expected, f"{code}: errors.md hint text does not match HINTS[{code!r}]"


def test_errors_md_has_no_orphaned_entries():
    """Catches the inverse drift: a code declared in errors.md but removed from ErrorCode."""
    parsed_codes = {code for code, _ in _parse_errors_md()}
    known_codes = {member.value for member in ErrorCode}
    assert parsed_codes == known_codes
