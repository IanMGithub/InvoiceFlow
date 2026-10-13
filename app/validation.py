def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _issue(code, field, message, index=None, item_code=None):
    issue = {
        "code": code,
        "field": field,
        "message": message,
    }

    if index is not None:
        issue["index"] = index

    if item_code is not None:
        issue["item_code"] = item_code

    return issue


def _available_item_code(line):
    if not isinstance(line, dict):
        return None

    item_code = line.get("item_code")

    if not isinstance(item_code, str):
        return None

    stripped = item_code.strip()

    if stripped == "":
        return None

    return stripped


def _validate_required_string(invoice, field, issues):
    if field not in invoice or invoice[field] is None:
        issues.append(
            _issue(
                "MISSING_FIELD",
                field,
                f"{field} is required.",
            )
        )
        return None

    value = invoice[field]

    if not isinstance(value, str):
        issues.append(
            _issue(
                "INVALID_TYPE",
                field,
                f"{field} must be a string.",
            )
        )
        return None

    stripped = value.strip()

    if stripped == "":
        issues.append(
            _issue(
                "INVALID_VALUE",
                field,
                f"{field} must be a nonempty string.",
            )
        )
        return None

    return stripped


def _validate_integer_field(
    container,
    field,
    issues,
    minimum,
    index=None,
    item_code=None,
):
    if field not in container or container[field] is None:
        issues.append(
            _issue(
                "MISSING_FIELD",
                field,
                f"{field} is required.",
                index=index,
                item_code=item_code,
            )
        )
        return None

    value = container[field]

    if not _is_int(value):
        issues.append(
            _issue(
                "INVALID_TYPE",
                field,
                f"{field} must be an integer.",
                index=index,
                item_code=item_code,
            )
        )
        return None

    if value < minimum:
        if minimum > 0:
            message = f"{field} must be greater than zero."
        else:
            message = f"{field} must be greater than or equal to zero."

        issues.append(
            _issue(
                "INVALID_VALUE",
                field,
                message,
                index=index,
                item_code=item_code,
            )
        )
        return None

    return value


def _validate_line_string_field(line, field, issues, index, item_code):
    if field not in line or line[field] is None:
        issues.append(
            _issue(
                "MISSING_FIELD",
                field,
                f"{field} is required.",
                index=index,
                item_code=item_code,
            )
        )
        return None

    value = line[field]

    if not isinstance(value, str):
        issues.append(
            _issue(
                "INVALID_TYPE",
                field,
                f"{field} must be a string.",
                index=index,
                item_code=item_code,
            )
        )
        return None

    stripped = value.strip()

    if stripped == "":
        issues.append(
            _issue(
                "INVALID_VALUE",
                field,
                f"{field} must be a nonempty string.",
                index=index,
                item_code=item_code,
            )
        )
        return None

    return stripped


def _validate_line_item(line, index, issues, seen_item_codes):
    if not isinstance(line, dict):
        issues.append(
            _issue(
                "INVALID_TYPE",
                "line_items",
                "line item must be an object.",
                index=index,
            )
        )
        return

    item_code = _available_item_code(line)

    stripped_item_code = _validate_line_string_field(
        line,
        "item_code",
        issues,
        index,
        item_code,
    )
    _validate_line_string_field(
        line,
        "description",
        issues,
        index,
        item_code,
    )
    quantity = _validate_integer_field(
        line,
        "quantity",
        issues,
        minimum=1,
        index=index,
        item_code=item_code,
    )
    unit_price_cents = _validate_integer_field(
        line,
        "unit_price_cents",
        issues,
        minimum=0,
        index=index,
        item_code=item_code,
    )
    stated_line_total_cents = _validate_integer_field(
        line,
        "stated_line_total_cents",
        issues,
        minimum=0,
        index=index,
        item_code=item_code,
    )

    if (
        quantity is not None
        and unit_price_cents is not None
        and stated_line_total_cents is not None
    ):
        expected_total = quantity * unit_price_cents

        if stated_line_total_cents != expected_total:
            issues.append(
                _issue(
                    "LINE_TOTAL_MISMATCH",
                    "stated_line_total_cents",
                    "stated_line_total_cents must equal "
                    "quantity multiplied by unit_price_cents.",
                    index=index,
                    item_code=item_code,
                )
            )

    if stripped_item_code is not None:
        if stripped_item_code in seen_item_codes:
            issues.append(
                _issue(
                    "DUPLICATE_ITEM_CODE",
                    "item_code",
                    "item_code must not appear more than once.",
                    index=index,
                    item_code=stripped_item_code,
                )
            )
        else:
            seen_item_codes.add(stripped_item_code)


def validate_invoice(invoice: dict) -> list[dict]:
    issues = []

    if not isinstance(invoice, dict):
        return [
            _issue(
                "INVALID_TYPE",
                "invoice",
                "invoice must be an object.",
            )
        ]

    _validate_required_string(invoice, "invoice_number", issues)
    _validate_required_string(invoice, "vendor_name", issues)
    _validate_required_string(invoice, "po_reference", issues)

    currency = _validate_required_string(invoice, "currency", issues)

    if currency is not None:
        is_three_uppercase_letters = (
            len(currency) == 3
            and currency.isascii()
            and currency.isalpha()
            and currency.isupper()
        )

        if not is_three_uppercase_letters:
            issues.append(
                _issue(
                    "INVALID_VALUE",
                    "currency",
                    "currency must be exactly three uppercase "
                    "alphabetic characters.",
                )
            )

    _validate_integer_field(
        invoice,
        "stated_total_cents",
        issues,
        minimum=0,
    )

    if "line_items" not in invoice or invoice["line_items"] is None:
        issues.append(
            _issue(
                "MISSING_FIELD",
                "line_items",
                "line_items is required.",
            )
        )
        return issues

    line_items = invoice["line_items"]

    if not isinstance(line_items, list):
        issues.append(
            _issue(
                "INVALID_TYPE",
                "line_items",
                "line_items must be a list.",
            )
        )
        return issues

    if len(line_items) == 0:
        issues.append(
            _issue(
                "INVALID_VALUE",
                "line_items",
                "line_items must be a nonempty list.",
            )
        )
        return issues

    seen_item_codes = set()

    for index, line in enumerate(line_items):
        _validate_line_item(line, index, issues, seen_item_codes)

    return issues
