#!/usr/bin/env python3
"""Extract a deterministic CrossTL frontend language snapshot."""

import argparse
import ast
import difflib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath


FRONTEND_DIR = Path("crosstl") / "translator"
FRONTEND_FILES = ("lexer.py", "parser.py", "ast.py", "validation.py")
LIVE_SPEC_MODULE = "crosstl.translator.language_spec"
LIVE_SPEC_FILE = FRONTEND_DIR / "language_spec.py"
SNAPSHOT_PATH = Path("docs") / "language" / "crosstl-frontend-language-spec-v0.json"
LANGUAGE_AUTHORITY_REFERENCES = (
    {
        "id": "authority.pr720-merged-reference",
        "kind": "merged-pr",
        "repository": "CrossGL/crosstl",
        "url": "https://github.com/CrossGL/crosstl/pull/720",
        "state": "MERGED",
        "headCommit": "19557a4b4e6ccca55622e819c795963d7f3a0a59",
        "languageAuthorityImpact": "no-sealed-source-drift",
    },
    {
        "id": "authority.pr724-project-porting-reference",
        "kind": "merged-pr",
        "repository": "CrossGL/crosstl",
        "url": "https://github.com/CrossGL/crosstl/pull/724",
        "state": "MERGED",
        "headCommit": "ffc1d88519589a7b11c45a18a9c3cac9bddb0604",
        "languageAuthorityImpact": "project-porting-source-remap-contract",
    },
)

PRIMITIVE_TYPE_TOKENS = (
    "BOOL",
    "I8",
    "I16",
    "I32",
    "I64",
    "U8",
    "U16",
    "U32",
    "U64",
    "F16",
    "F32",
    "F64",
    "INT",
    "UINT",
    "FLOAT",
    "DOUBLE",
    "HALF",
    "CHAR",
    "STRING",
    "VOID",
)

VECTOR_TYPE_TOKENS = (
    "VEC2",
    "VEC3",
    "VEC4",
    "IVEC2",
    "IVEC3",
    "IVEC4",
    "UVEC2",
    "UVEC3",
    "UVEC4",
    "DVEC2",
    "DVEC3",
    "DVEC4",
    "BVEC2",
    "BVEC3",
    "BVEC4",
)

MATRIX_TYPE_PREFIXES = ("MAT", "DMAT")
SAMPLER_IMAGE_TOKEN_PREFIXES = ("SAMPLER", "IMAGE", "IIMAGE", "UIMAGE")

REQUIRED_LEXER_CONSTANTS = {
    "TOKENS": list,
    "KEYWORDS": dict,
    "SKIP_TOKENS": set,
}

REQUIRED_PARSER_CONSTANTS = {
    "MESH_INTRINSICS": set,
    "PARAMETER_PRIMITIVE_QUALIFIER_NAMES": set,
    "PARAMETER_QUALIFIER_TOKEN_TYPES": set,
    "RAYQUERY_METHODS": set,
    "RAYTRACING_INTRINSICS": set,
    "SHADER_STAGE_TOKEN_TYPES": set,
    "TEXTURE_TYPE_NAMES": dict,
    "VARIABLE_QUALIFIER_NAMES": set,
    "VARIABLE_QUALIFIER_TOKEN_TYPES": set,
    "WAVE_INTRINSICS": set,
}

REQUIRED_VALIDATION_CONSTANTS = {
    "ADDRESS_SPACE_METADATA_NAMES": dict,
    "BUILTIN_SEMANTIC_METADATA_NAMES": dict,
    "DESCRIPTOR_INDEX_METADATA_NAMES": dict,
    "HLSL_SEMANTIC_METADATA_BASE_NAMES": set,
    "IMAGE_FORMAT_METADATA_NAMES": set,
    "IMAGE_RESOURCE_INTRINSIC_NAMES": set,
    "INTEGER_COORDINATE_INTRINSIC_NAMES": set,
    "INTERPOLATION_MODE_METADATA_NAMES": dict,
    "INTERPOLATION_SAMPLING_METADATA_NAMES": dict,
    "MEMORY_LAYOUT_METADATA_NAMES": dict,
    "MULTI_VALUE_METADATA_NAMES": set,
    "RESOURCE_ACCESS_METADATA_NAMES": dict,
    "RESOURCE_BUFFER_TYPE_NAMES": set,
    "SAMPLER_STATE_TYPE_NAMES": set,
    "SINGLE_VALUE_METADATA_ALIASES": dict,
    "SINGLE_VALUE_METADATA_NAMES": set,
    "STAGE_LAYOUT_DIRECTION_REQUIREMENTS": dict,
    "STAGE_LAYOUT_EXCLUSIVE_ENTRY_GROUPS": tuple,
    "STORAGE_IMAGE_TYPE_NAMES": set,
    "TESSELLATION_CONTROL_STAGE_LAYOUT_ENTRIES": set,
    "TESSELLATION_EVALUATION_STAGE_LAYOUT_ENTRIES": set,
    "TEXTURE_INTRINSIC_ALLOWED_ARGUMENT_COUNTS": dict,
    "TEXTURE_INTRINSIC_MAX_ARGUMENTS": dict,
    "TEXTURE_INTRINSIC_MIN_ARGUMENTS": dict,
    "TEXTURE_INTRINSICS_WITH_EXPLICIT_SAMPLERS": set,
    "UAV_RESOURCE_BUFFER_TYPE_NAMES": set,
}

PARSER_STRING_SET_CONSTANTS = (
    "MESH_INTRINSICS",
    "PARAMETER_PRIMITIVE_QUALIFIER_NAMES",
    "PARAMETER_QUALIFIER_TOKEN_TYPES",
    "RAYQUERY_METHODS",
    "RAYTRACING_INTRINSICS",
    "SHADER_STAGE_TOKEN_TYPES",
    "VARIABLE_QUALIFIER_NAMES",
    "VARIABLE_QUALIFIER_TOKEN_TYPES",
    "WAVE_INTRINSICS",
)

VALIDATION_STRING_MAPPING_CONSTANTS = (
    "ADDRESS_SPACE_METADATA_NAMES",
    "BUILTIN_SEMANTIC_METADATA_NAMES",
    "DESCRIPTOR_INDEX_METADATA_NAMES",
    "INTERPOLATION_MODE_METADATA_NAMES",
    "INTERPOLATION_SAMPLING_METADATA_NAMES",
    "MEMORY_LAYOUT_METADATA_NAMES",
    "RESOURCE_ACCESS_METADATA_NAMES",
    "SINGLE_VALUE_METADATA_ALIASES",
    "STAGE_LAYOUT_DIRECTION_REQUIREMENTS",
)

VALIDATION_STRING_SET_CONSTANTS = (
    "HLSL_SEMANTIC_METADATA_BASE_NAMES",
    "IMAGE_FORMAT_METADATA_NAMES",
    "IMAGE_RESOURCE_INTRINSIC_NAMES",
    "INTEGER_COORDINATE_INTRINSIC_NAMES",
    "MULTI_VALUE_METADATA_NAMES",
    "RESOURCE_BUFFER_TYPE_NAMES",
    "SAMPLER_STATE_TYPE_NAMES",
    "SINGLE_VALUE_METADATA_NAMES",
    "STORAGE_IMAGE_TYPE_NAMES",
    "TESSELLATION_CONTROL_STAGE_LAYOUT_ENTRIES",
    "TESSELLATION_EVALUATION_STAGE_LAYOUT_ENTRIES",
    "TEXTURE_INTRINSICS_WITH_EXPLICIT_SAMPLERS",
    "UAV_RESOURCE_BUFFER_TYPE_NAMES",
)


class ExtractionError(RuntimeError):
    """Raised when required CrossTL source data cannot be extracted."""


class UnresolvedLiteral(ValueError):
    """Raised when a Python AST expression is not a static literal."""


def read_text(path):
    return path.read_text(encoding="utf-8")


def sha256_text(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def base_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return base_name(node.value)
    return None


def literal_value(node, env):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [literal_value(item, env) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(literal_value(item, env) for item in node.elts)
    if isinstance(node, ast.Set):
        return {literal_value(item, env) for item in node.elts}
    if isinstance(node, ast.Dict):
        return {
            literal_value(key, env): literal_value(value, env)
            for key, value in zip(node.keys, node.values)
        }
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise UnresolvedLiteral(node.id)
    if isinstance(node, ast.BinOp):
        left = literal_value(node.left, env)
        right = literal_value(node.right, env)
        if isinstance(node.op, ast.BitOr):
            return set(left) | set(right)
        if isinstance(node.op, ast.Sub):
            return set(left) - set(right)
        raise UnresolvedLiteral(ast.dump(node.op))
    if isinstance(node, ast.Call):
        name = call_name(node.func)
        args = [literal_value(arg, env) for arg in node.args]
        if name in {"set", "frozenset"}:
            return set(args[0] if args else [])
        if name == "list":
            return list(args[0] if args else [])
        if name == "tuple":
            return tuple(args[0] if args else [])
        if name == "dict":
            return dict(args[0] if args else [])
        if name == "OrderedDict":
            return list(args[0] if args else [])
        raise UnresolvedLiteral(name or ast.dump(node.func))
    raise UnresolvedLiteral(ast.dump(node))


def parse_python(path):
    text = read_text(path)
    return ast.parse(text, filename=str(path)), text


def extract_constants(module):
    env = {}
    constants = {}
    unresolved = {}
    for node in module.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = literal_value(node.value, env)
        except UnresolvedLiteral as exc:
            unresolved[target.id] = str(exc)
            continue
        env[target.id] = value
        constants[target.id] = value
    return constants, unresolved


def expected_type_name(expected_type):
    if isinstance(expected_type, tuple):
        return " or ".join(item.__name__ for item in expected_type)
    return expected_type.__name__


def is_empty_required_value(value):
    return isinstance(value, (dict, list, set, tuple)) and not value


def require_constants(constants, unresolved, source_name, expected):
    missing = []
    unresolved_required = []
    wrong_type = []
    empty = []
    for name, expected_type in expected.items():
        if name not in constants:
            if name in unresolved:
                unresolved_required.append(f"{name} ({unresolved[name]})")
            else:
                missing.append(name)
            continue
        value = constants[name]
        if not isinstance(value, expected_type):
            wrong_type.append(
                f"{name} expected {expected_type_name(expected_type)}, "
                f"got {type(value).__name__}"
            )
            continue
        if is_empty_required_value(value):
            empty.append(name)

    failures = []
    if missing:
        failures.append("missing " + ", ".join(sorted(missing)))
    if unresolved_required:
        failures.append("unresolved " + ", ".join(sorted(unresolved_required)))
    if wrong_type:
        failures.append("wrong type " + "; ".join(sorted(wrong_type)))
    if empty:
        failures.append("empty " + ", ".join(sorted(empty)))
    if failures:
        raise ExtractionError(
            f"{source_name}: failed required constant extraction: "
            + "; ".join(failures)
        )


def require_non_empty(name, value):
    if is_empty_required_value(value):
        raise ExtractionError(f"{name} is empty after extraction")
    return value


def require_string_mapping(name, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ExtractionError(f"{name} must be a non-empty mapping")
    bad_items = [
        key
        for key, value in mapping.items()
        if not isinstance(key, str) or not isinstance(value, str) or not value
    ]
    if bad_items:
        raise ExtractionError(
            f"{name} contains non-string or empty string entries: {bad_items}"
        )
    return mapping


def require_string_collection(name, values):
    if is_empty_required_value(values):
        raise ExtractionError(f"{name} must be non-empty")
    invalid = [value for value in values if not isinstance(value, str) or not value]
    if invalid:
        raise ExtractionError(
            f"{name} contains non-string or empty string entries: {invalid}"
        )


def require_int_mapping(name, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ExtractionError(f"{name} must be a non-empty mapping")
    invalid = [
        key
        for key, value in mapping.items()
        if not isinstance(key, str) or not isinstance(value, int)
    ]
    if invalid:
        raise ExtractionError(
            f"{name} contains non-string keys or non-integer values: {invalid}"
        )


def require_integer_count_mapping(name, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ExtractionError(f"{name} must be a non-empty mapping")
    invalid = []
    for key, values in mapping.items():
        if not isinstance(key, str) or not isinstance(values, tuple):
            invalid.append(key)
            continue
        if not values or any(not isinstance(value, int) for value in values):
            invalid.append(key)
    if invalid:
        raise ExtractionError(
            f"{name} contains invalid argument count entries: {invalid}"
        )


def validate_token_table(tokens):
    if not tokens:
        raise ExtractionError("lexer.py TOKENS is empty")
    invalid = []
    for item in tokens:
        if not (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and isinstance(item[0], str)
            and item[0]
            and isinstance(item[1], str)
            and item[1]
        ):
            invalid.append(item)
    if invalid:
        raise ExtractionError(f"lexer.py TOKENS contains invalid entries: {invalid}")


def find_method(module, class_name, function_name):
    for node in ast.walk(module):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == function_name:
                return item
    raise ExtractionError(f"could not find {class_name}.{function_name}")


def assignment_to_name(node, name):
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return False
    target = node.targets[0]
    return isinstance(target, ast.Name) and target.id == name


def node_contains(root, needle):
    return any(node is needle for node in ast.walk(root))


def sequence_string_literals(node):
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return None
    values = []
    for item in node.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return None
        values.append(item.value)
    return values


def subscript_index_value(node):
    index = subscript_slice_value(node)
    if isinstance(index, ast.Constant):
        return index.value
    return None


def subscript_slice_value(node):
    index = node.slice
    if hasattr(ast, "Index") and isinstance(index, ast.Index):
        return index.value
    return index


def is_current_token_type_access(node):
    if not isinstance(node, ast.Subscript) or subscript_index_value(node) != 0:
        return False
    value = node.value
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "current_token"
        and isinstance(value.value, ast.Name)
        and value.value.id == "self"
    )


def extract_current_token_membership(test, context):
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.In)
        and len(test.comparators) == 1
        and is_current_token_type_access(test.left)
    ):
        raise ExtractionError(
            f"{context}: expected `self.current_token[0] in [...]` condition"
        )

    tokens = sequence_string_literals(test.comparators[0])
    if tokens is None:
        raise ExtractionError(f"{context}: token condition is not a static list")
    if not tokens:
        raise ExtractionError(f"{context}: token condition is empty")
    duplicates = sorted({token for token in tokens if tokens.count(token) > 1})
    if duplicates:
        raise ExtractionError(
            f"{context}: token condition contains duplicates: {duplicates}"
        )
    return tokens


def is_name(node, name):
    return isinstance(node, ast.Name) and node.id == name


def is_sampler_named_type_call(node):
    if not (
        isinstance(node, ast.Call)
        and call_name(node.func) == "NamedType"
        and len(node.args) == 1
    ):
        return False
    argument = node.args[0]
    if not isinstance(argument, ast.Subscript):
        return False
    if not is_name(argument.value, "sampler_types"):
        return False
    return is_name(subscript_slice_value(argument), "token_type")


def is_token_type_assignment(node):
    return assignment_to_name(node, "token_type") and is_current_token_type_access(
        node.value
    )


def is_eat_token_type_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "eat"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and len(node.args) == 1
        and is_name(node.args[0], "token_type")
    )


def extract_sampler_image_type_names(module):
    function = find_method(module, "Parser", "parse_type")
    assignments = [
        node for node in ast.walk(function) if assignment_to_name(node, "sampler_types")
    ]
    if len(assignments) != 1:
        raise ExtractionError(
            "Parser.parse_type must contain exactly one sampler_types assignment; "
            f"found {len(assignments)}"
        )

    assignment = assignments[0]
    branches = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.If)
        and any(node_contains(item, assignment) for item in node.body)
    ]
    if len(branches) != 1:
        raise ExtractionError(
            "Parser.parse_type sampler/image branch is ambiguous; "
            f"found {len(branches)} candidate branches"
        )

    branch = branches[0]
    condition_tokens = extract_current_token_membership(
        branch.test, "Parser.parse_type sampler/image branch"
    )
    try:
        sampler_types = literal_value(assignment.value, {})
    except UnresolvedLiteral as exc:
        raise ExtractionError(
            f"Parser.parse_type sampler_types could not be resolved: {exc}"
        ) from exc

    require_string_mapping("Parser.parse_type sampler_types", sampler_types)
    condition_token_set = set(condition_tokens)
    sampler_token_set = set(sampler_types)
    if condition_token_set != sampler_token_set:
        missing = sorted(condition_token_set - sampler_token_set)
        extra = sorted(sampler_token_set - condition_token_set)
        details = []
        if missing:
            details.append(f"missing mappings for {missing}")
        if extra:
            details.append(f"unreachable mappings for {extra}")
        raise ExtractionError(
            "Parser.parse_type sampler_types does not match branch tokens: "
            + "; ".join(details)
        )

    invalid_prefixes = sorted(
        token
        for token in sampler_types
        if not token.startswith(SAMPLER_IMAGE_TOKEN_PREFIXES)
    )
    if invalid_prefixes:
        raise ExtractionError(
            "Parser.parse_type sampler_types contains unexpected token prefixes: "
            + ", ".join(invalid_prefixes)
        )

    token_type_assignments = [
        node for node in ast.walk(branch) if is_token_type_assignment(node)
    ]
    named_type_calls = [
        node for node in ast.walk(branch) if is_sampler_named_type_call(node)
    ]
    eat_calls = [node for node in ast.walk(branch) if is_eat_token_type_call(node)]
    if len(token_type_assignments) != 1:
        raise ExtractionError(
            "Parser.parse_type sampler/image branch must assign "
            f"`token_type = self.current_token[0]` once; found "
            f"{len(token_type_assignments)}"
        )
    if len(eat_calls) != 1:
        raise ExtractionError(
            "Parser.parse_type sampler/image branch must call "
            f"`self.eat(token_type)` once; found {len(eat_calls)}"
        )
    if len(named_type_calls) != 1:
        raise ExtractionError(
            "Parser.parse_type sampler/image branch must create "
            f"`NamedType(sampler_types[token_type])` once; found "
            f"{len(named_type_calls)}"
        )

    return sampler_types


def extract_enums(module):
    enums = {}
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(base_name(base) == "Enum" for base in node.bases):
            continue
        values = []
        for item in node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1:
                target = item.targets[0]
                if isinstance(target, ast.Name) and isinstance(
                    item.value, ast.Constant
                ):
                    values.append({"name": target.id, "value": item.value.value})
        enums[node.name] = values
    return enums


def extract_classes(module):
    classes = []
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        classes.append(
            {
                "name": node.name,
                "bases": [
                    name for name in (base_name(base) for base in node.bases) if name
                ],
            }
        )
    return classes


def source_segment(source_text, node):
    if node is None:
        return None
    segment = (
        ast.get_source_segment(source_text, node)
        if hasattr(ast, "get_source_segment")
        else None
    )
    if segment is not None:
        return " ".join(segment.split())
    if hasattr(ast, "unparse"):
        return " ".join(ast.unparse(node).split())
    return None


def annotation_text(source_text, arg):
    return source_segment(source_text, arg.annotation)


def annotation_is_optional(text):
    if text is None:
        return False
    return (
        "Optional[" in text
        or "None" in text
        or text.endswith(" | None")
        or " | None | " in text
    )


def parameter_entry(arg, kind, default_node, source_text):
    default = source_segment(source_text, default_node)
    annotation = annotation_text(source_text, arg)
    return {
        "name": arg.arg,
        "kind": kind,
        "annotation": annotation,
        "required": default_node is None,
        "default": default,
        "optional": default_node is not None or annotation_is_optional(annotation),
    }


def constructor_parameters(function, source_text):
    parameters = []
    positional = list(function.args.posonlyargs) + list(function.args.args)
    defaults = [None] * (len(positional) - len(function.args.defaults))
    defaults.extend(function.args.defaults)
    for arg, default_node in zip(positional, defaults):
        if arg.arg == "self":
            continue
        kind = (
            "positional-only"
            if arg in function.args.posonlyargs
            else "positional-or-keyword"
        )
        parameters.append(parameter_entry(arg, kind, default_node, source_text))

    for arg, default_node in zip(function.args.kwonlyargs, function.args.kw_defaults):
        parameters.append(
            parameter_entry(arg, "keyword-only", default_node, source_text)
        )

    if function.args.vararg is not None:
        entry = parameter_entry(
            function.args.vararg, "var-positional", None, source_text
        )
        entry["required"] = False
        entry["optional"] = True
        parameters.append(entry)

    if function.args.kwarg is not None:
        entry = parameter_entry(function.args.kwarg, "var-keyword", None, source_text)
        entry["required"] = False
        entry["optional"] = True
        parameters.append(entry)

    return parameters


def self_attribute_name(node):
    if not isinstance(node, ast.Attribute):
        return None
    value = node.value
    if isinstance(value, ast.Name) and value.id == "self":
        return node.attr
    return None


def referenced_parameter(value, parameter_names):
    if isinstance(value, ast.Name) and value.id in parameter_names:
        return value.id
    if isinstance(value, ast.BoolOp):
        for item in value.values:
            name = referenced_parameter(item, parameter_names)
            if name is not None:
                return name
    return None


def field_source(value, parameter_name):
    if parameter_name is not None:
        if isinstance(value, ast.Name):
            return "parameter"
        return "parameter-derived"
    if isinstance(value, ast.Constant):
        return "constant"
    return "derived"


def field_annotation(parameter_name, parameter_by_name, annotation, source_text):
    explicit = source_segment(source_text, annotation)
    if explicit is not None:
        return explicit
    if parameter_name is not None:
        return parameter_by_name[parameter_name]["annotation"]
    return None


def field_default(parameter_name, parameter_by_name, value, source_text):
    if parameter_name is not None:
        return parameter_by_name[parameter_name]["default"]
    if isinstance(value, ast.Constant):
        return source_segment(source_text, value)
    return None


def assignment_field_entries(statement, parameter_by_name, source_text):
    entries = []
    parameter_names = set(parameter_by_name)
    if isinstance(statement, ast.Assign):
        targets = statement.targets
        value = statement.value
        annotation = None
    elif isinstance(statement, ast.AnnAssign):
        targets = [statement.target]
        value = statement.value
        annotation = statement.annotation
    else:
        return entries

    for target in targets:
        name = self_attribute_name(target)
        if name is None:
            continue
        parameter_name = referenced_parameter(value, parameter_names)
        entry = {
            "name": name,
            "source": field_source(value, parameter_name),
            "parameter": parameter_name,
            "annotation": field_annotation(
                parameter_name, parameter_by_name, annotation, source_text
            ),
            "required": (
                bool(parameter_by_name[parameter_name]["required"])
                if parameter_name is not None
                else False
            ),
            "default": field_default(
                parameter_name, parameter_by_name, value, source_text
            ),
            "optional": (
                bool(parameter_by_name[parameter_name]["optional"])
                if parameter_name is not None
                else True
            ),
            "initializer": source_segment(source_text, value),
        }
        entries.append(entry)
    return entries


def find_class_init(class_node):
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            return item
    return None


def extract_class_field_inventory(module, source_text, classes):
    class_nodes = {
        node.name: node for node in module.body if isinstance(node, ast.ClassDef)
    }
    inventory = []
    for class_info in classes:
        class_name = class_info["name"]
        class_node = class_nodes[class_name]
        init = find_class_init(class_node)
        if init is None:
            inventory.append(
                {
                    "class": class_name,
                    "constructorDefined": False,
                    "constructorParameters": [],
                    "fields": [],
                }
            )
            continue

        parameters = constructor_parameters(init, source_text)
        parameter_by_name = {parameter["name"]: parameter for parameter in parameters}
        fields_by_name = {}
        for statement in ast.walk(init):
            for entry in assignment_field_entries(
                statement, parameter_by_name, source_text
            ):
                fields_by_name[entry["name"]] = entry

        inventory.append(
            {
                "class": class_name,
                "constructorDefined": True,
                "constructorParameters": parameters,
                "fields": [
                    fields_by_name[name] for name in sorted(fields_by_name.keys())
                ],
            }
        )
    return inventory


def descendants(classes, root_name):
    bases_by_name = {item["name"]: set(item["bases"]) for item in classes}

    def inherits(name, seen=None):
        if name == root_name:
            return False
        if seen is None:
            seen = set()
        if name in seen:
            return False
        seen.add(name)
        bases = bases_by_name.get(name, set())
        return root_name in bases or any(inherits(base, seen) for base in bases)

    return sorted(name for name in bases_by_name if inherits(name))


def sorted_strings(values):
    return sorted(str(value) for value in values)


def sorted_mapping(mapping, key_name="spelling", value_name="canonical"):
    return [
        {key_name: str(key), value_name: str(value)}
        for key, value in sorted(mapping.items(), key=lambda item: str(item[0]))
    ]


def token_spellings_by_name(keywords):
    spellings = {}
    for spelling, token in keywords.items():
        spellings.setdefault(token, []).append(spelling)
    return {token: sorted(values) for token, values in spellings.items()}


def preferred_spelling(token, spellings):
    values = spellings.get(token)
    if values:
        return values[0]
    return token.lower()


def vector_element(token):
    if token.startswith("IVEC"):
        return "int"
    if token.startswith("UVEC"):
        return "uint"
    if token.startswith("DVEC"):
        return "double"
    if token.startswith("BVEC"):
        return "bool"
    return "float"


def vector_width(spelling):
    try:
        return int(str(spelling)[-1])
    except ValueError as exc:
        raise ExtractionError(
            f"could not infer vector width from {spelling!r}"
        ) from exc


def matrix_shape(spelling):
    is_double = str(spelling).startswith("dmat")
    dimensions = str(spelling)[4:] if is_double else str(spelling)[3:]
    try:
        if "x" in dimensions:
            rows, cols = dimensions.split("x", 1)
            return int(rows), int(cols)
        size = int(dimensions)
        return size, size
    except ValueError as exc:
        raise ExtractionError(
            f"could not infer matrix shape from {spelling!r}"
        ) from exc


def is_matrix_type_token(token, spellings):
    spelling = preferred_spelling(token, spellings)
    return spelling.startswith(("mat", "dmat")) and spelling[-1].isdigit()


def canonical_stage_from_token(token, canonical_stages):
    manual_aliases = {
        "KERNEL": "compute",
    }
    if token in manual_aliases:
        return manual_aliases[token]
    candidate = token.lower()
    return candidate if candidate in canonical_stages else None


def classify_sampler_image(canonical_name):
    lowered = canonical_name.lower()
    if lowered.startswith(("image", "iimage", "uimage")):
        return "storage-image"
    if lowered.startswith("sampler"):
        return "sampler"
    return "resource"


def texture_intrinsic_entries(validation_constants):
    minimums = validation_constants["TEXTURE_INTRINSIC_MIN_ARGUMENTS"]
    maximums = validation_constants["TEXTURE_INTRINSIC_MAX_ARGUMENTS"]
    allowed = validation_constants["TEXTURE_INTRINSIC_ALLOWED_ARGUMENT_COUNTS"]
    explicit = set(validation_constants["TEXTURE_INTRINSICS_WITH_EXPLICIT_SAMPLERS"])
    names = sorted(set(minimums) | set(maximums) | set(allowed) | explicit)
    if not names:
        raise ExtractionError("texture intrinsic extraction produced no entries")
    missing_minimums = sorted((set(maximums) | set(allowed) | explicit) - set(minimums))
    missing_maximums = sorted((set(minimums) | set(allowed) | explicit) - set(maximums))
    if missing_minimums or missing_maximums:
        details = []
        if missing_minimums:
            details.append("missing minimums for " + ", ".join(missing_minimums))
        if missing_maximums:
            details.append("missing maximums for " + ", ".join(missing_maximums))
        raise ExtractionError(
            "texture intrinsic metadata is inconsistent: " + "; ".join(details)
        )
    entries = []
    for name in names:
        entry = {
            "name": name,
            "explicitSampler": name in explicit,
        }
        if name in minimums:
            entry["minArguments"] = minimums[name]
        if name in maximums:
            entry["maxArguments"] = maximums[name]
        if name in allowed:
            entry["allowedArgumentCounts"] = list(allowed[name])
        entries.append(entry)
    return entries


def require_declared_tokens(category, token_names, declared_tokens):
    missing = sorted(set(token_names) - set(declared_tokens))
    if missing:
        raise ExtractionError(
            f"{category} references tokens not declared by lexer.py: "
            + ", ".join(missing)
        )


def require_token_spellings(category, token_names, spellings):
    missing = sorted(token for token in token_names if not spellings.get(token))
    if missing:
        raise ExtractionError(
            f"{category} has no keyword spelling in lexer.py KEYWORDS: "
            + ", ".join(missing)
        )


def require_all_string_values(name, values):
    invalid = [value for value in values if not isinstance(value, str) or not value]
    if invalid:
        raise ExtractionError(f"{name} contains non-string or empty values: {invalid}")


def validate_stage_extraction(stage_tokens, stage_values, stage_keywords, spellings):
    require_non_empty("ShaderStage enum values", stage_values)
    require_non_empty("SHADER_STAGE_TOKEN_TYPES", stage_tokens)
    require_non_empty("stage keyword extraction", stage_keywords)
    require_token_spellings("SHADER_STAGE_TOKEN_TYPES", stage_tokens, spellings)
    accepted_without_canonical = sorted(
        item["token"]
        for item in stage_keywords
        if item["acceptedAsStageBlock"] and item["canonical"] is None
    )
    if accepted_without_canonical:
        raise ExtractionError(
            "stage keywords accepted by Parser.parse_shader are missing "
            "ShaderStage enum mappings: " + ", ".join(accepted_without_canonical)
        )


def validate_ast_inventory(ast_classes, ast_enums):
    require_non_empty("AST class inventory", ast_classes)
    class_names = {item["name"] for item in ast_classes}
    required_classes = {"ASTNode", "TypeNode", "StatementNode", "ExpressionNode"}
    missing_classes = sorted(required_classes - class_names)
    if missing_classes:
        raise ExtractionError(
            "ast.py is missing required AST class roots: " + ", ".join(missing_classes)
        )
    if "ShaderStage" not in ast_enums or not ast_enums["ShaderStage"]:
        raise ExtractionError("ast.py did not expose non-empty ShaderStage enum")

    required_descendant_roots = {
        "TypeNode": "AST type node inventory",
        "StatementNode": "AST statement node inventory",
        "ExpressionNode": "AST expression node inventory",
    }
    for root_name, label in required_descendant_roots.items():
        require_non_empty(label, descendants(ast_classes, root_name))


def validate_ast_field_inventory(ast_classes, class_fields):
    require_non_empty("AST class field inventory", class_fields)
    class_names = [item["name"] for item in ast_classes]
    field_classes = [item.get("class") for item in class_fields]
    if field_classes != class_names:
        raise ExtractionError(
            f"AST class field inventory does not match class order: {field_classes}"
        )

    for item in class_fields:
        class_name = item["class"]
        fields = item.get("fields")
        parameters = item.get("constructorParameters")
        if not isinstance(fields, list):
            raise ExtractionError(f"{class_name}: fields must be a list")
        if not isinstance(parameters, list):
            raise ExtractionError(f"{class_name}: constructorParameters must be a list")
        seen_fields = set()
        duplicate_fields = []
        for field in fields:
            field_name = field.get("name") if isinstance(field, dict) else None
            if field_name in seen_fields:
                duplicate_fields.append(field_name)
            seen_fields.add(field_name)
        duplicate_fields = sorted(name for name in duplicate_fields if name)
        if duplicate_fields:
            raise ExtractionError(
                f"{class_name}: duplicate field entries: {duplicate_fields}"
            )
        parameter_names = {
            parameter.get("name")
            for parameter in parameters
            if isinstance(parameter, dict)
        }
        for field in fields:
            if not isinstance(field, dict):
                raise ExtractionError(f"{class_name}: field entry must be an object")
            for required_key in (
                "name",
                "source",
                "parameter",
                "annotation",
                "required",
                "default",
                "optional",
                "initializer",
            ):
                if required_key not in field:
                    raise ExtractionError(
                        f"{class_name}: field entry missing {required_key}"
                    )
            if not isinstance(field["name"], str) or not field["name"]:
                raise ExtractionError(f"{class_name}: field entry has invalid name")
            parameter = field["parameter"]
            if parameter is not None and parameter not in parameter_names:
                raise ExtractionError(
                    f"{class_name}.{field['name']}: unknown parameter {parameter}"
                )


def validate_stage_layout_groups(groups):
    if not isinstance(groups, tuple) or not groups:
        raise ExtractionError("STAGE_LAYOUT_EXCLUSIVE_ENTRY_GROUPS must be non-empty")
    bad_groups = [group for group in groups if not isinstance(group, set) or not group]
    if bad_groups:
        raise ExtractionError(
            "STAGE_LAYOUT_EXCLUSIVE_ENTRY_GROUPS contains invalid groups"
        )


def require_snapshot_object(snapshot, path):
    value = snapshot
    for part in path:
        if not isinstance(value, dict) or part not in value:
            dotted = ".".join(path)
            raise ExtractionError(f"live CrossTL language spec is missing {dotted}")
        value = value[part]
    return value


def require_snapshot_list(snapshot, path):
    value = require_snapshot_object(snapshot, path)
    if not isinstance(value, list) or not value:
        dotted = ".".join(path)
        raise ExtractionError(f"live CrossTL language spec {dotted} must be a list")
    return value


def require_live_string_list(snapshot, path):
    values = require_snapshot_list(snapshot, path)
    require_string_collection(".".join(path), values)
    return values


def live_keyword_mapping(entries):
    mapping = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ExtractionError("live CrossTL language spec keyword must be object")
        spelling = entry.get("spelling")
        token = entry.get("token")
        if not isinstance(spelling, str) or not spelling:
            raise ExtractionError("live CrossTL language spec keyword has bad spelling")
        if not isinstance(token, str) or not token:
            raise ExtractionError("live CrossTL language spec keyword has bad token")
        if spelling in mapping:
            raise ExtractionError(
                "live CrossTL language spec duplicate keyword spelling: " + spelling
            )
        mapping[spelling] = token
    require_string_mapping("lexical.keywords", mapping)
    return mapping


def validate_live_token_table(tokens):
    invalid = []
    names = []
    for item in tokens:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item["name"]
            and isinstance(item.get("pattern"), str)
            and item["pattern"]
        ):
            invalid.append(item)
            continue
        names.append(item["name"])
    if invalid:
        raise ExtractionError(
            f"live CrossTL language spec lexical.tokens has invalid entries: {invalid}"
        )
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ExtractionError(
            "live CrossTL language spec lexical.tokens duplicates: "
            + ", ".join(duplicates)
        )


def validate_live_stage_keywords(stage_keywords):
    required_keys = {"spelling", "token", "canonical", "acceptedAsStageBlock"}
    for item in stage_keywords:
        if not isinstance(item, dict):
            raise ExtractionError(
                "live CrossTL language spec stage keyword must be object"
            )
        missing = sorted(required_keys - set(item))
        if missing:
            raise ExtractionError(
                "live CrossTL language spec stage keyword missing: "
                + ", ".join(missing)
            )
        if not isinstance(item["spelling"], str) or not item["spelling"]:
            raise ExtractionError(
                "live CrossTL language spec stage spelling is invalid"
            )
        if not isinstance(item["token"], str) or not item["token"]:
            raise ExtractionError("live CrossTL language spec stage token is invalid")
        if item["canonical"] is not None and not isinstance(item["canonical"], str):
            raise ExtractionError(
                "live CrossTL language spec stage canonical is invalid"
            )
        if not isinstance(item["acceptedAsStageBlock"], bool):
            raise ExtractionError(
                "live CrossTL language spec acceptedAsStageBlock is invalid"
            )


def validate_live_type_entries(snapshot, declared_token_names, spellings):
    primitive = require_snapshot_list(snapshot, ("language", "types", "primitive"))
    primitive_tokens = [
        item.get("token") for item in primitive if isinstance(item, dict)
    ]
    if primitive_tokens != list(PRIMITIVE_TYPE_TOKENS):
        raise ExtractionError(
            "live CrossTL language spec primitive type tokens changed: "
            + repr(primitive_tokens)
        )
    require_declared_tokens(
        "primitive type extraction", PRIMITIVE_TYPE_TOKENS, declared_token_names
    )
    require_token_spellings(
        "primitive type extraction", PRIMITIVE_TYPE_TOKENS, spellings
    )

    vectors = require_snapshot_list(snapshot, ("language", "types", "vectors"))
    vector_tokens = [item.get("token") for item in vectors if isinstance(item, dict)]
    if vector_tokens != list(VECTOR_TYPE_TOKENS):
        raise ExtractionError(
            "live CrossTL language spec vector type tokens changed: "
            + repr(vector_tokens)
        )
    for item in vectors:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("spelling"), str)
            and isinstance(item.get("token"), str)
            and isinstance(item.get("elementType"), str)
            and isinstance(item.get("width"), int)
            and item["width"] > 0
        ):
            raise ExtractionError(
                "live CrossTL language spec vector type entry is invalid: " + repr(item)
            )
    require_declared_tokens(
        "vector type extraction", VECTOR_TYPE_TOKENS, declared_token_names
    )
    require_token_spellings("vector type extraction", VECTOR_TYPE_TOKENS, spellings)

    matrices = require_snapshot_list(snapshot, ("language", "types", "matrices"))
    matrix_tokens = []
    for item in matrices:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("spelling"), str)
            and isinstance(item.get("token"), str)
            and isinstance(item.get("elementType"), str)
            and isinstance(item.get("rows"), int)
            and isinstance(item.get("columns"), int)
            and item["rows"] > 0
            and item["columns"] > 0
        ):
            raise ExtractionError(
                "live CrossTL language spec matrix type entry is invalid: " + repr(item)
            )
        matrix_tokens.append(item["token"])
    require_declared_tokens(
        "matrix type extraction", matrix_tokens, declared_token_names
    )
    require_token_spellings("matrix type extraction", matrix_tokens, spellings)

    textures = require_snapshot_list(snapshot, ("language", "types", "textures"))
    texture_tokens = []
    for item in textures:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("spelling"), str)
            and isinstance(item.get("token"), str)
            and isinstance(item.get("canonical"), str)
            and item["canonical"]
        ):
            raise ExtractionError(
                "live CrossTL language spec texture type entry is invalid: "
                + repr(item)
            )
        texture_tokens.append(item["token"])
    require_declared_tokens("TEXTURE_TYPE_NAMES", texture_tokens, declared_token_names)
    require_token_spellings("TEXTURE_TYPE_NAMES", texture_tokens, spellings)

    sampler_image = require_snapshot_list(
        snapshot, ("language", "types", "samplersAndImages")
    )
    sampler_image_tokens = []
    for item in sampler_image:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("token"), str)
            and isinstance(item.get("canonical"), str)
            and isinstance(item.get("kind"), str)
            and isinstance(item.get("keywordSpellings"), list)
        ):
            raise ExtractionError(
                "live CrossTL language spec sampler/image entry is invalid: "
                + repr(item)
            )
        require_all_string_values(
            f"samplersAndImages.{item['token']}.keywordSpellings",
            item["keywordSpellings"],
        )
        sampler_image_tokens.append(item["token"])
    require_declared_tokens(
        "Parser.parse_type sampler_types", sampler_image_tokens, declared_token_names
    )


def live_mapping_from_entries(entries, key_name="spelling", value_name="canonical"):
    mapping = {}
    for item in entries:
        if not isinstance(item, dict):
            raise ExtractionError("live CrossTL language spec mapping entry is invalid")
        key = item.get(key_name)
        value = item.get(value_name)
        if not isinstance(key, str) or not key:
            raise ExtractionError(
                "live CrossTL language spec mapping entry has invalid key"
            )
        if not isinstance(value, str) or not value:
            raise ExtractionError(
                "live CrossTL language spec mapping entry has invalid value"
            )
        if key in mapping:
            raise ExtractionError(
                "live CrossTL language spec duplicate mapping key: " + key
            )
        mapping[key] = value
    return mapping


def validate_live_mapping_entries(
    snapshot, path, key_name="spelling", value_name="canonical"
):
    entries = require_snapshot_list(snapshot, path)
    mapping = live_mapping_from_entries(entries, key_name, value_name)
    require_string_mapping(".".join(path), mapping)
    return mapping


def validate_live_texture_intrinsic_entries(entries):
    for item in entries:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item["name"]
            and isinstance(item.get("explicitSampler"), bool)
        ):
            raise ExtractionError(
                "live CrossTL language spec texture intrinsic entry is invalid: "
                + repr(item)
            )
        for key in ("minArguments", "maxArguments"):
            if key in item and not isinstance(item[key], int):
                raise ExtractionError(
                    f"live CrossTL language spec {item['name']} {key} is invalid"
                )
        if "allowedArgumentCounts" in item:
            counts = item["allowedArgumentCounts"]
            if not isinstance(counts, list) or any(
                not isinstance(value, int) for value in counts
            ):
                raise ExtractionError(
                    "live CrossTL language spec "
                    f"{item['name']} allowedArgumentCounts is invalid"
                )


def validate_live_source_file_path(path, translator_root):
    if "\\" in path:
        raise ExtractionError(
            "live CrossTL language spec source file path must use '/' separators: "
            + path
        )
    posix_path = PurePosixPath(path)
    windows_path = PureWindowsPath(path)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or not posix_path.parts
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        raise ExtractionError(
            "live CrossTL language spec source file path is unsafe: " + path
        )

    translator_root = translator_root.resolve()
    source_path = (translator_root / Path(*posix_path.parts)).resolve()
    try:
        source_path.relative_to(translator_root)
    except ValueError as exc:
        raise ExtractionError(
            "live CrossTL language spec source file escapes translator root: " + path
        ) from exc
    return source_path


def validate_live_source_file_seals(files, translator_root):
    source_file_hashes = {}
    for item in files:
        if not isinstance(item, dict):
            raise ExtractionError(
                "live CrossTL language spec source file must be object"
            )
        path = item.get("path")
        digest = item.get("sha256")
        if not isinstance(path, str) or not path:
            raise ExtractionError("live CrossTL language spec source file has bad path")
        if path in source_file_hashes:
            raise ExtractionError(
                "live CrossTL language spec duplicate source file seal: " + path
            )
        if not isinstance(digest, str) or len(digest) != 64:
            raise ExtractionError(
                f"live CrossTL language spec source file {path} has bad sha256"
            )

        source_path = validate_live_source_file_path(path, translator_root)
        if not source_path.is_file():
            raise ExtractionError(
                f"live CrossTL language spec source file missing: {path}"
            )
        actual_digest = sha256_text(read_text(source_path))
        if digest != actual_digest:
            raise ExtractionError(
                "live CrossTL language spec source file hash changed for "
                f"{path}: expected {actual_digest}, got {digest}"
            )
        source_file_hashes[path] = digest
    return source_file_hashes


def validate_live_language_spec_snapshot(snapshot, translator_root):
    if not isinstance(snapshot, dict):
        raise ExtractionError("live CrossTL language spec must be a JSON object")
    if snapshot.get("schemaVersion") != 0:
        raise ExtractionError(
            "live CrossTL language spec schemaVersion changed: "
            f"{snapshot.get('schemaVersion')}"
        )
    if snapshot.get("kind") != "crosstl-frontend-language-spec-snapshot":
        raise ExtractionError(
            "live CrossTL language spec kind changed: " + repr(snapshot.get("kind"))
        )

    source = require_snapshot_object(snapshot, ("source",))
    files = source.get("files")
    if not isinstance(files, list):
        raise ExtractionError("live CrossTL language spec source.files must be a list")
    sealed_paths = {
        item.get("path")
        for item in files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    expected_paths = {(FRONTEND_DIR / name).as_posix() for name in FRONTEND_FILES}
    missing_paths = sorted(expected_paths - sealed_paths)
    if missing_paths:
        raise ExtractionError(
            "live CrossTL language spec does not seal frontend files: "
            + ", ".join(missing_paths)
        )
    validate_live_source_file_seals(files, translator_root)

    extraction = source.get("extraction")
    if not isinstance(extraction, dict):
        raise ExtractionError("live CrossTL language spec source.extraction is missing")
    for key in ("tool", "method"):
        if not isinstance(extraction.get(key), str) or not extraction[key]:
            raise ExtractionError(
                f"live CrossTL language spec source.extraction.{key} is missing"
            )

    tokens = require_snapshot_list(snapshot, ("lexical", "tokens"))
    validate_live_token_table(tokens)
    keyword_entries = require_snapshot_list(snapshot, ("lexical", "keywords"))
    keywords = live_keyword_mapping(keyword_entries)
    skip_tokens = require_live_string_list(snapshot, ("lexical", "skipTokens"))
    literal_tokens = require_live_string_list(snapshot, ("lexical", "literalTokens"))
    require_string_collection("lexical.skipTokens", skip_tokens)
    require_string_collection("lexical.literalTokens", literal_tokens)
    declared_token_names = {item["name"] for item in tokens} | set(keywords.values())
    spellings = token_spellings_by_name(keywords)

    stages = require_snapshot_object(snapshot, ("language", "stages"))
    canonical_stage_values = stages.get("canonical")
    stage_keywords = stages.get("keywordSpellings")
    stage_token_types = stages.get("parserStageTokens")
    if not isinstance(canonical_stage_values, list):
        raise ExtractionError("live CrossTL language spec stage canonical list missing")
    if not isinstance(stage_keywords, list) or not isinstance(stage_token_types, list):
        raise ExtractionError("live CrossTL language spec stage inventory is malformed")
    require_all_string_values("ShaderStage enum values", canonical_stage_values)
    require_string_collection("language.stages.parserStageTokens", stage_token_types)
    validate_live_stage_keywords(stage_keywords)
    validate_stage_extraction(
        set(stage_token_types), canonical_stage_values, stage_keywords, spellings
    )
    require_declared_tokens(
        "stage keyword extraction", stage_token_types, declared_token_names
    )

    validate_live_type_entries(snapshot, declared_token_names, spellings)
    for path in (
        ("language", "qualifiers", "variableQualifierTokens"),
        ("language", "qualifiers", "parameterQualifierTokens"),
        ("language", "qualifiers", "variableQualifierNames"),
        ("language", "qualifiers", "parameterPrimitiveQualifierNames"),
        ("language", "resources", "storageImageTypeNames"),
        ("language", "resources", "resourceBufferTypeNames"),
        ("language", "resources", "uavResourceBufferTypeNames"),
        ("language", "resources", "samplerStateTypeNames"),
        ("language", "resources", "imageFormatMetadataNames"),
        ("language", "intrinsics", "imageResource"),
        ("language", "intrinsics", "integerCoordinate"),
        ("language", "intrinsics", "wave"),
        ("language", "intrinsics", "rayTracing"),
        ("language", "intrinsics", "rayQueryMethods"),
        ("language", "intrinsics", "mesh"),
        ("validation", "metadata", "singleValueNames"),
        ("validation", "metadata", "multiValueNames"),
        ("validation", "metadata", "hlslSemanticBaseNames"),
        ("validation", "stageLayout", "tessellationControlEntries"),
        ("validation", "stageLayout", "tessellationEvaluationEntries"),
    ):
        require_live_string_list(snapshot, path)

    validate_live_mapping_entries(
        snapshot, ("language", "resources", "resourceAccessMetadata")
    )
    validate_live_mapping_entries(
        snapshot,
        ("language", "resources", "descriptorIndexMetadata"),
        value_name="role",
    )
    validate_live_mapping_entries(
        snapshot, ("language", "resources", "addressSpaceMetadata")
    )
    validate_live_mapping_entries(
        snapshot, ("language", "resources", "memoryLayoutMetadata")
    )
    validate_live_mapping_entries(
        snapshot, ("language", "resources", "builtinSemanticMetadata")
    )
    validate_live_mapping_entries(
        snapshot, ("validation", "metadata", "singleValueAliases")
    )
    validate_live_mapping_entries(
        snapshot, ("validation", "metadata", "interpolationModes")
    )
    validate_live_mapping_entries(
        snapshot, ("validation", "metadata", "interpolationSampling")
    )
    validate_live_mapping_entries(
        snapshot,
        ("validation", "stageLayout", "directionRequirements"),
        key_name="entry",
        value_name="requiredDirection",
    )
    texture_intrinsics = require_snapshot_list(
        snapshot, ("language", "intrinsics", "textureAndImage")
    )
    validate_live_texture_intrinsic_entries(texture_intrinsics)
    exclusive_groups = require_snapshot_list(
        snapshot, ("validation", "stageLayout", "exclusiveEntryGroups")
    )
    for group in exclusive_groups:
        if not isinstance(group, list):
            raise ExtractionError(
                "live CrossTL language spec exclusive stage layout group is invalid"
            )
        require_string_collection("validation.stageLayout.exclusiveEntryGroups", group)

    ast_snapshot = require_snapshot_object(snapshot, ("ast",))
    ast_classes = ast_snapshot.get("classes")
    ast_enums = ast_snapshot.get("enums")
    ast_class_fields = ast_snapshot.get("classFields")
    if not isinstance(ast_classes, list) or not isinstance(ast_enums, dict):
        raise ExtractionError("live CrossTL language spec AST inventory is malformed")
    if not isinstance(ast_class_fields, list):
        raise ExtractionError(
            "live CrossTL language spec AST field inventory is malformed"
        )
    validate_ast_inventory(ast_classes, ast_enums)
    validate_ast_field_inventory(ast_classes, ast_class_fields)
    for path, root_name in (
        (("ast", "typeNodes"), "TypeNode"),
        (("ast", "statementNodes"), "StatementNode"),
        (("ast", "expressionNodes"), "ExpressionNode"),
    ):
        actual_nodes = require_live_string_list(snapshot, path)
        expected_nodes = descendants(ast_classes, root_name)
        if actual_nodes != expected_nodes:
            raise ExtractionError(
                f"live CrossTL language spec {'.'.join(path)} changed: "
                f"expected {expected_nodes}, got {actual_nodes}"
            )
    for item in ast_class_fields:
        class_name = item["class"]
        for field in item.get("fields", []):
            if (
                not isinstance(field.get("initializer"), str)
                or not field["initializer"]
            ):
                raise ExtractionError(
                    f"{class_name}.{field.get('name')}: field initializer "
                    "must be source-backed"
                )


def validate_translator_root(translator_root):
    if not translator_root.exists():
        raise ExtractionError(
            "CrossGL-Translator root does not exist: " + str(translator_root)
        )
    if not translator_root.is_dir():
        raise ExtractionError(
            "CrossGL-Translator root is not a directory: " + str(translator_root)
        )

    required_paths = [FRONTEND_DIR / name for name in FRONTEND_FILES]
    required_paths.append(LIVE_SPEC_FILE)
    missing = [
        path.as_posix()
        for path in required_paths
        if not (translator_root / path).is_file()
    ]
    if missing:
        raise ExtractionError(
            "CrossGL-Translator root is missing required CrossTL frontend "
            "authority files: " + ", ".join(missing)
        )


def extract_live_language_spec_snapshot(translator_root):
    validate_translator_root(translator_root)

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(translator_root)
        if not existing_pythonpath
        else str(translator_root) + os.pathsep + existing_pythonpath
    )
    command = [sys.executable, "-m", LIVE_SPEC_MODULE]
    process = subprocess.run(
        command,
        cwd=str(translator_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        details = process.stderr.strip() or process.stdout.strip()
        raise ExtractionError(
            "live CrossTL language spec extraction failed with exit code "
            f"{process.returncode}: {details}"
        )
    try:
        snapshot = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            f"live CrossTL language spec produced invalid JSON: {exc}"
        ) from exc
    validate_live_language_spec_snapshot(snapshot, translator_root)
    return snapshot


def apply_language_authority_references(snapshot):
    annotated = dict(snapshot)
    source = dict(annotated.get("source", {}))
    source["authorityReferences"] = [
        dict(reference) for reference in LANGUAGE_AUTHORITY_REFERENCES
    ]
    annotated["source"] = source
    return annotated


def build_snapshot(translator_root):
    return apply_language_authority_references(
        extract_live_language_spec_snapshot(translator_root)
    )


def find_default_translator_root(root):
    candidates = []
    env_root = os.environ.get("CROSSGL_TRANSLATOR_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend(
        [
            root.parent / "CrossGL-Translator",
            root.parent.parent / "CrossGL-Translator",
            Path.cwd().parent / "CrossGL-Translator",
        ]
    )
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / FRONTEND_DIR / "lexer.py").is_file():
            return resolved
    return None


def render_json(value):
    return json.dumps(value, indent=2) + "\n"


def write_snapshot(output_path, text):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def check_snapshot(output_path, generated_text):
    if not output_path.is_file():
        print(f"{output_path}: snapshot does not exist", file=sys.stderr)
        return 1
    existing_text = read_text(output_path)
    if existing_text == generated_text:
        print(f"{output_path}: up to date")
        return 0
    diff = difflib.unified_diff(
        existing_text.splitlines(keepends=True),
        generated_text.splitlines(keepends=True),
        fromfile=str(output_path),
        tofile=f"{output_path} (generated)",
    )
    print(f"{output_path}: snapshot is stale", file=sys.stderr)
    sys.stderr.writelines(diff)
    return 1


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="CrossGL-Compiler repository root.",
    )
    parser.add_argument(
        "--translator-root",
        type=Path,
        help=(
            "CrossGL-Translator root. Defaults to CROSSGL_TRANSLATOR_ROOT or a "
            "sibling checkout when available."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Snapshot path. Relative paths are resolved from --root. "
            f"Defaults to {SNAPSHOT_PATH.as_posix()}."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare generated snapshot with the checked-in artifact.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    root = args.root.expanduser().resolve()
    if args.output is None:
        output_path = root / SNAPSHOT_PATH
    elif args.output.is_absolute():
        output_path = args.output
    else:
        output_path = root / args.output
    output_path = output_path.expanduser().resolve()

    translator_root = (
        args.translator_root.expanduser().resolve()
        if args.translator_root
        else find_default_translator_root(root)
    )
    if translator_root is None:
        print(
            "CrossGL-Translator checkout not found; pass --translator-root or set "
            "CROSSGL_TRANSLATOR_ROOT.",
            file=sys.stderr,
        )
        return 2

    try:
        snapshot = build_snapshot(translator_root)
        generated_text = render_json(snapshot)
        if args.check:
            return check_snapshot(output_path, generated_text)

        write_snapshot(output_path, generated_text)
        print(f"wrote {output_path}")
        return 0
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except UnresolvedLiteral as exc:
        print(f"error: static value resolution failed: {exc}", file=sys.stderr)
        return 1
    except SyntaxError as exc:
        location = exc.filename or "<unknown>"
        if exc.lineno is not None:
            location = f"{location}:{exc.lineno}"
        print(f"error: syntax error in {location}: {exc.msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
