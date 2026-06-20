"""Shared source-location assertions for package fixture checks."""

from pathlib import Path


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _coherent_offset_span(location, *, strict_int, require_positive_length):
    offset = location.get("offset")
    length = location.get("length")
    end_offset = location.get("endOffset")
    int_check = (
        is_int
        if strict_int
        else lambda value: isinstance(value, int) and not isinstance(value, bool)
    )
    if not (int_check(offset) and int_check(length) and int_check(end_offset)):
        return None, "integer", offset, length, end_offset
    if offset < 0 or length < 0 or end_offset < 0:
        return None, "nonnegative", offset, length, end_offset
    if require_positive_length and length <= 0:
        return None, "positive", offset, length, end_offset
    if end_offset != offset + length:
        return None, "coherent", offset, length, end_offset
    return (offset, length, end_offset), None, offset, length, end_offset


def _line_column_for_offset(text, offset):
    line = 1
    column = 1
    for char in text[:offset]:
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return line, column


def _read_source_text(path):
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _expect_span_matches_text_positions(
    errors,
    case_name,
    path,
    location,
    text,
    offset,
    end_offset,
):
    if offset > len(text) or end_offset > len(text):
        errors.append(
            f"{case_name}: expected {path} span to stay within source text, "
            f"got offset={offset!r}, endOffset={end_offset!r}, "
            f"textSize={len(text)!r}"
        )
        return

    expected_line, expected_column = _line_column_for_offset(text, offset)
    actual_line = location.get("line")
    actual_column = location.get("column")
    if actual_line != expected_line or actual_column != expected_column:
        errors.append(
            f"{case_name}: expected {path}.line/column to match offset "
            f"{offset}, got line={actual_line!r}, column={actual_column!r}, "
            f"expected line={expected_line!r}, column={expected_column!r}"
        )

    expected_end_line, expected_end_column = _line_column_for_offset(
        text,
        end_offset,
    )
    actual_end_line = location.get("endLine")
    actual_end_column = location.get("endColumn")
    if actual_end_line != expected_end_line or actual_end_column != expected_end_column:
        errors.append(
            f"{case_name}: expected {path}.endLine/endColumn to match "
            f"endOffset {end_offset}, got endLine={actual_end_line!r}, "
            f"endColumn={actual_end_column!r}, expected "
            f"endLine={expected_end_line!r}, endColumn={expected_end_column!r}"
        )


def expect_location_span_coherent(errors, case_name, path, location):
    if not isinstance(location, dict):
        errors.append(f"{case_name}: expected {path} to be a location object")
        return

    _span, reason, offset, length, end_offset = _coherent_offset_span(
        location,
        strict_int=True,
        require_positive_length=False,
    )
    if reason == "integer":
        errors.append(
            f"{case_name}: expected integer {path} offset/length/endOffset, "
            f"got {location!r}"
        )
    elif reason == "nonnegative":
        errors.append(
            f"{case_name}: expected nonnegative {path} "
            f"offset/length/endOffset, got offset={offset!r}, "
            f"length={length!r}, endOffset={end_offset!r}"
        )
    elif reason == "coherent":
        errors.append(
            f"{case_name}: expected {path}.endOffset to equal offset + length, "
            f"got offset={offset!r}, length={length!r}, endOffset={end_offset!r}"
        )

    line = location.get("line")
    column = location.get("column")
    end_line = location.get("endLine")
    end_column = location.get("endColumn")
    if not (
        is_int(line) and is_int(column) and is_int(end_line) and is_int(end_column)
    ):
        errors.append(
            f"{case_name}: expected integer {path} line/column/endLine/endColumn, "
            f"got {location!r}"
        )
        return
    if line <= 0 or column <= 0 or end_line <= 0 or end_column <= 0:
        errors.append(
            f"{case_name}: expected positive {path} line/column/endLine/endColumn, "
            f"got line={line!r}, column={column!r}, endLine={end_line!r}, "
            f"endColumn={end_column!r}"
        )

    if end_line < line:
        errors.append(
            f"{case_name}: expected {path}.endLine >= line, "
            f"got line={line!r}, endLine={end_line!r}"
        )
    if end_line == line and end_column < column:
        errors.append(
            f"{case_name}: expected same-line {path}.endColumn >= column, "
            f"got column={column!r}, endColumn={end_column!r}"
        )


def expect_location(
    errors,
    case_name,
    path,
    location,
    expected_file_name,
    *,
    expected_offset=None,
    min_offset=None,
    min_length=None,
):
    if not isinstance(location, dict):
        errors.append(f"{case_name}: expected {path} to be a location object")
        return
    file_name = Path(location.get("file", "")).name
    if file_name != expected_file_name:
        errors.append(
            f"{case_name}: expected {path}.file to end in "
            f"{expected_file_name!r}, got {location.get('file')!r}"
        )
    offset = location.get("offset")
    length = location.get("length")
    end_offset = location.get("endOffset")
    if expected_offset is not None and offset != expected_offset:
        errors.append(
            f"{case_name}: expected {path}.offset to equal "
            f"{expected_offset}, got {offset!r}"
        )
    if min_offset is not None and (not isinstance(offset, int) or offset < min_offset):
        errors.append(
            f"{case_name}: expected {path}.offset >= {min_offset}, got {offset!r}"
        )
    if min_length is not None and (not isinstance(length, int) or length < min_length):
        errors.append(
            f"{case_name}: expected {path}.length >= {min_length}, got {length!r}"
        )
    if (
        isinstance(offset, int)
        and isinstance(length, int)
        and end_offset != offset + length
    ):
        errors.append(
            f"{case_name}: expected {path}.endOffset to equal offset + length, "
            f"got offset={offset!r}, length={length!r}, endOffset={end_offset!r}"
        )


def expect_location_spans_file(
    errors,
    case_name,
    path,
    location,
    source_path,
    *,
    expected_file_name=None,
):
    if not isinstance(location, dict):
        errors.append(f"{case_name}: expected {path} to be a location object")
        return

    source_path = Path(source_path)
    expected_file_name = expected_file_name or source_path.name
    actual_file = Path(location.get("file", "")).name
    if actual_file != expected_file_name:
        errors.append(
            f"{case_name}: expected {path}.file to end in "
            f"{expected_file_name!r}, got {location.get('file')!r}"
        )
        return

    span, _reason, _, _, _ = _coherent_offset_span(
        location,
        strict_int=False,
        require_positive_length=False,
    )
    if span is None:
        errors.append(f"{case_name}: expected coherent {path} span, got {location!r}")
        return
    offset, _length, end_offset = span

    text = _read_source_text(source_path)
    if offset != 0 or end_offset != len(text):
        errors.append(
            f"{case_name}: expected {path} to span all of "
            f"{source_path.name!r}, got offset={offset!r}, "
            f"endOffset={end_offset!r}, textSize={len(text)!r}"
        )
        return

    _expect_span_matches_text_positions(
        errors,
        case_name,
        path,
        location,
        text,
        offset,
        end_offset,
    )


def expect_location_overlaps_text(
    errors,
    case_name,
    path,
    location,
    source_path,
    start_marker,
    end_marker=None,
    *,
    expected_file_name=None,
):
    if not isinstance(location, dict):
        errors.append(f"{case_name}: expected {path} to be a location object")
        return

    source_path = Path(source_path)
    expected_file_name = expected_file_name or source_path.name
    actual_file = Path(location.get("file", "")).name
    if actual_file != expected_file_name:
        errors.append(
            f"{case_name}: expected {path}.file to end in "
            f"{expected_file_name!r}, got {location.get('file')!r}"
        )
        return

    span, _reason, _, _, _ = _coherent_offset_span(
        location,
        strict_int=False,
        require_positive_length=True,
    )
    if span is None:
        errors.append(
            f"{case_name}: expected positive coherent {path} span, got {location!r}"
        )
        return
    offset, length, end_offset = span

    text = _read_source_text(source_path)
    _expect_span_matches_text_positions(
        errors,
        case_name,
        path,
        location,
        text,
        offset,
        end_offset,
    )
    try:
        marker_start = text.index(start_marker)
        marker_end = (
            text.index(end_marker, marker_start)
            if end_marker is not None
            else marker_start + len(start_marker)
        )
    except ValueError as exc:
        errors.append(f"{case_name}: failed to locate test marker: {exc}")
        return

    if offset + length <= marker_start or offset >= marker_end:
        errors.append(
            f"{case_name}: {path} does not overlap {start_marker!r}: {location!r}"
        )


def expect_location_text_equals(
    errors,
    case_name,
    path,
    location,
    source_path,
    expected_text,
    *,
    expected_file_name=None,
):
    if not isinstance(location, dict):
        errors.append(f"{case_name}: expected {path} to be a location object")
        return

    source_path = Path(source_path)
    expected_file_name = expected_file_name or source_path.name
    actual_file = Path(location.get("file", "")).name
    if actual_file != expected_file_name:
        errors.append(
            f"{case_name}: expected {path}.file to end in "
            f"{expected_file_name!r}, got {location.get('file')!r}"
        )
        return

    span, _reason, _, _, _ = _coherent_offset_span(
        location,
        strict_int=True,
        require_positive_length=True,
    )
    if span is None:
        errors.append(
            f"{case_name}: expected positive coherent {path} span, got {location!r}"
        )
        return
    offset, _length, end_offset = span

    text = _read_source_text(source_path)
    _expect_span_matches_text_positions(
        errors,
        case_name,
        path,
        location,
        text,
        offset,
        end_offset,
    )
    actual_text = text[offset:end_offset]
    if actual_text != expected_text:
        errors.append(
            f"{case_name}: expected {path} to select {expected_text!r}, "
            f"got {actual_text!r} from {location!r}"
        )
