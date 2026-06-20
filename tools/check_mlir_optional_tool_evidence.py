#!/usr/bin/env python3
"""Validate report-only optional MLIR tool evidence.

The checker intentionally does not discover MLIR or invoke mlir-opt. It validates
the committed manifest contract and, when given a configured build-tree evidence
file, verifies that missing MLIR is represented as a clean optional skip.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path("experimental/mlir/experiment_manifest.json")
FIXTURE_INVENTORY_PATH = Path("experimental/mlir/fixture_inventory.json")
CTEST_PATH = Path("tests/cmake/CrossGLMLIRExperimentTests.cmake")
CMAKE_PATH = Path("CMakeLists.txt")
KIND = "crossgl-mlir-optional-tool-evidence-v0"
GATE_OPTION = "CROSSGL_ENABLE_MLIR_EXPERIMENTAL"
GATE_TARGET = "crossgl_mlir_experiment"
VERIFIER_TEST = "cglc_mlir_experiment_minimal_compute_verifier"
EVIDENCE_TEST = "cglc_mlir_optional_tool_evidence"
VERIFIER_INPUT_LIST = "CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS"
VERIFIER_INPUT = "tests/fixtures/mlir/minimal_compute_builtin_module.mlir"
MINIMAL_FIXTURE = "tests/fixtures/MinimalComputeShader.cgl"
SCALAR_EXPRESSION_VERIFIER_TEST = (
    "cglc_mlir_experiment_scalar_expression_compute_verifier"
)
SCALAR_EXPRESSION_VERIFIER_INPUT = (
    "tests/fixtures/mlir/scalar_expression_compute_builtin_module.mlir"
)
SCALAR_EXPRESSION_FIXTURE = "tests/fixtures/ScalarExpressionComputeShader.cgl"
STORAGE_BUFFER_VERIFIER_TEST = "cglc_mlir_experiment_storage_buffer_compute_verifier"
STORAGE_BUFFER_VERIFIER_INPUT = (
    "tests/fixtures/mlir/storage_buffer_compute_builtin_module.mlir"
)
STORAGE_BUFFER_FIXTURE = "tests/fixtures/StorageBufferComputeShader.cgl"
IF_COMPUTE_VERIFIER_TEST = "cglc_mlir_experiment_if_compute_verifier"
IF_COMPUTE_VERIFIER_INPUT = "tests/fixtures/mlir/if_compute_builtin_module.mlir"
IF_COMPUTE_FIXTURE = "tests/fixtures/IfComputeShader.cgl"
TEXTURE_SAMPLER_VERIFIER_TEST = "cglc_mlir_experiment_texture_sampler_compute_verifier"
TEXTURE_SAMPLER_VERIFIER_INPUT = (
    "tests/fixtures/mlir/texture_sampler_compute_builtin_module.mlir"
)
TEXTURE_SAMPLER_FIXTURE = "tests/fixtures/VulkanTextureSamplerLodShader.cgl"
SOURCE_RESOURCE_CATALOG = "experimental/mlir/source_resource_catalog.v0.json"
SOURCE_RESOURCE_CATALOG_KIND = "crossgl-mlir-source-resource-catalog-v0"
SOURCE_RESOURCE_CATALOG_CHECKER = "tools/check_mlir_source_resource_catalog.py"
SOURCE_RESOURCE_PRESERVATION_SECTION = "sourceResourceEntrypointPreservation"
OPTION_DEFAULT = "OFF"
OPTION_ACTUAL_VALUES = ("OFF", "ON")
DEFAULT_OFF_BRANCH = f"if(NOT {GATE_OPTION})"
FIND_PROGRAM_COMMAND = "find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)"
VERSION_PROBE_COMMAND = "mlir-opt --version"
STATUS_VALUES = ("default-off", "toolchain-unavailable", "toolchain-available")
TOOL_DISCOVERY_STATUS_VALUES = (
    "not-run-default-off",
    "not-run-toolchain-incomplete",
    "not-found",
    "probe-failed",
    "available",
)
VERIFIER_REGISTRATION_MODES = ("skipped", "executable")
BASE_SKIP_LABELS = {"mlir", "optional-mlir"}
AVAILABLE_TOOL_LABEL = "mlir-tool-available"
UNAVAILABLE_TOOL_LABEL = "mlir-tool-unavailable"
SKIP_REGEX = "^SKIP:"
DEFAULT_OFF_MISSING_REASON = f"{GATE_OPTION}=OFF"
REQUIRED_GATE_FACTS = (
    f"{GATE_OPTION}=ON",
    "MLIR_FOUND=TRUE",
    f"target {GATE_TARGET}",
    VERIFIER_INPUT,
    SCALAR_EXPRESSION_VERIFIER_INPUT,
    STORAGE_BUFFER_VERIFIER_INPUT,
    IF_COMPUTE_VERIFIER_INPUT,
    TEXTURE_SAMPLER_VERIFIER_INPUT,
    "mlir-opt discovery",
    "mlir-opt --version probe",
)
MINIMAL_REQUIRED_VERIFIER_MARKERS = (
    f'crossgl_fixture = "{MINIMAL_FIXTURE}"',
    'crossgl_entry_point = "main"',
    "crossgl_source_location_fact_source_file = true",
    "crossgl_source_location_fact_shader_module = true",
    "crossgl_source_location_fact_compute_stage = true",
    "crossgl_source_location_fact_entry_point = true",
    "crossgl_source_location_fact_layout_local_size = true",
    "crossgl_source_location_fact_return_statement = true",
    "crossgl_type_fact_void_entry_point = true",
    "crossgl_resource_count = 0",
    'crossgl_resource_metadata = "target-independent:none"',
    "crossgl_real_mlir_smoke = true",
)
SCALAR_EXPRESSION_REQUIRED_VERIFIER_MARKERS = (
    f'crossgl_fixture = "{SCALAR_EXPRESSION_FIXTURE}"',
    'crossgl_entry_point = "main"',
    "crossgl_source_location_fact_source_file = true",
    "crossgl_source_location_fact_shader_module = true",
    "crossgl_source_location_fact_compute_stage = true",
    "crossgl_source_location_fact_entry_point = true",
    "crossgl_source_location_fact_layout_local_size = true",
    "crossgl_source_location_fact_local_variable_declarations = true",
    "crossgl_source_location_fact_scalar_expression_statements = true",
    "crossgl_source_location_fact_return_statement = true",
    "crossgl_type_fact_void_entry_point = true",
    "crossgl_type_fact_float_scalar = true",
    "crossgl_type_fact_int_scalar = true",
    "crossgl_type_fact_bool_scalar = true",
    "crossgl_type_fact_scalar_literals = true",
    "crossgl_type_fact_constructor_cast_expression = true",
    "crossgl_type_fact_binary_expression_result_types = true",
    "crossgl_type_fact_comparison_expression_result_type = true",
    "crossgl_scalar_local_count = 4",
    'crossgl_scalar_local_0_name = "base"',
    'crossgl_scalar_local_0_type = "float"',
    'crossgl_scalar_local_1_name = "scaled"',
    'crossgl_scalar_local_1_type = "float"',
    'crossgl_scalar_local_2_name = "count"',
    'crossgl_scalar_local_2_type = "int"',
    'crossgl_scalar_local_3_name = "keep"',
    'crossgl_scalar_local_3_type = "bool"',
    "crossgl_scalar_expression_count = 4",
    "crossgl_scalar_expression_fact_float_literal = true",
    "crossgl_scalar_expression_fact_int_literal = true",
    "crossgl_scalar_expression_fact_binary_add = true",
    "crossgl_scalar_expression_fact_binary_multiply = true",
    "crossgl_scalar_expression_fact_constructor_cast = true",
    "crossgl_scalar_expression_fact_comparison_greater_than = true",
    "crossgl_scalar_expression_fact_comparison_result_bool = true",
    "crossgl_resource_count = 0",
    "crossgl_resource_fact_descriptors_empty = true",
    "crossgl_resource_fact_storage_buffers_empty = true",
    "crossgl_resource_fact_storage_images_empty = true",
    "crossgl_resource_fact_textures_empty = true",
    "crossgl_resource_fact_samplers_empty = true",
    "crossgl_target_independent_resource_metadata_empty = true",
    'crossgl_resource_metadata = "target-independent:none"',
    'crossgl_scalar_expression_metadata = "locals:base:float,scaled:float,count:int,keep:bool;expressions:literal,binary,constructor_cast,comparison"',
    "crossgl_real_mlir_smoke = true",
)
STORAGE_BUFFER_REQUIRED_VERIFIER_MARKERS = (
    f'crossgl_fixture = "{STORAGE_BUFFER_FIXTURE}"',
    'crossgl_entry_point = "main"',
    "crossgl_source_location_fact_source_file = true",
    "crossgl_source_location_fact_shader_module = true",
    "crossgl_source_location_fact_compute_stage = true",
    "crossgl_source_location_fact_entry_point = true",
    "crossgl_source_location_fact_layout_local_size = true",
    "crossgl_source_location_fact_storage_buffer_declaration = true",
    "crossgl_source_location_fact_local_variable_declarations = true",
    "crossgl_source_location_fact_scalar_expression_statements = true",
    "crossgl_source_location_fact_storage_buffer_write = true",
    "crossgl_source_location_fact_return_statement = true",
    "crossgl_type_fact_void_entry_point = true",
    "crossgl_type_fact_float_scalar = true",
    "crossgl_type_fact_float_pointer_storage_buffer = true",
    "crossgl_type_fact_storage_buffer_element_type = true",
    "crossgl_type_fact_binary_expression_result_types = true",
    "crossgl_resource_count = 1",
    "crossgl_descriptor_count = 1",
    'crossgl_descriptor_0_stage = "compute"',
    'crossgl_descriptor_0_name = "values"',
    'crossgl_descriptor_0_kind = "storageBuffer"',
    "crossgl_descriptor_0_set = 0",
    "crossgl_descriptor_0_binding = 0",
    "crossgl_storage_buffer_count = 1",
    'crossgl_storage_buffer_0_name = "values"',
    'crossgl_storage_buffer_0_type = "float*"',
    'crossgl_storage_buffer_0_element_type = "float"',
    'crossgl_storage_buffer_0_address_space = "storage"',
    "crossgl_storage_buffer_0_write_access = true",
    "crossgl_resource_fact_storage_images_empty = true",
    "crossgl_resource_fact_textures_empty = true",
    "crossgl_resource_fact_samplers_empty = true",
    "crossgl_target_independent_resource_metadata_count = 1",
    'crossgl_target_independent_resource_metadata_0_stage = "compute"',
    'crossgl_target_independent_resource_metadata_0_name = "values"',
    'crossgl_target_independent_resource_metadata_0_kind = "storageBuffer"',
    'crossgl_target_independent_resource_metadata_0_source_type = "float*"',
    'crossgl_target_independent_resource_metadata_0_element_type = "float"',
    'crossgl_target_independent_resource_metadata_0_address_space = "storage"',
    'crossgl_target_independent_resource_metadata_0_access = "read_write"',
    "crossgl_target_independent_resource_metadata_0_set = 0",
    "crossgl_target_independent_resource_metadata_0_binding = 0",
    "crossgl_target_independent_resource_metadata_0_target_independent = true",
    'crossgl_resource_metadata = "target-independent:storageBuffer:compute:values:set=0:binding=0:type=float*:element=float:addressSpace=storage:access=read_write"',
    "crossgl_real_mlir_smoke = true",
)
IF_COMPUTE_REQUIRED_VERIFIER_MARKERS = (
    f'crossgl_fixture = "{IF_COMPUTE_FIXTURE}"',
    'crossgl_stage = "compute"',
    'crossgl_entry_point = "main"',
    'crossgl_local_size = "1,1,1"',
    "crossgl_source_location_fact_source_file = true",
    "crossgl_source_location_fact_shader_module = true",
    "crossgl_source_location_fact_compute_stage = true",
    "crossgl_source_location_fact_entry_point = true",
    "crossgl_source_location_fact_layout_local_size = true",
    "crossgl_source_location_fact_storage_buffer_declaration = true",
    "crossgl_source_location_fact_local_variable_declarations = true",
    "crossgl_source_location_fact_storage_buffer_read = true",
    "crossgl_source_location_fact_if_statement = true",
    "crossgl_source_location_fact_then_block_assignment = true",
    "crossgl_source_location_fact_else_block_assignment = true",
    "crossgl_source_location_fact_storage_buffer_write = true",
    "crossgl_source_location_fact_return_statement = true",
    "crossgl_type_fact_void_entry_point = true",
    "crossgl_type_fact_float_scalar = true",
    "crossgl_type_fact_float_pointer_storage_buffer = true",
    "crossgl_type_fact_storage_buffer_element_type = true",
    "crossgl_type_fact_comparison_expression_result_type = true",
    "crossgl_type_fact_branch_condition_bool = true",
    "crossgl_type_fact_assignment_expression_result_types = true",
    "crossgl_type_fact_unary_expression_result_types = true",
    "crossgl_resource_count = 1",
    "crossgl_descriptor_count = 1",
    'crossgl_descriptor_0_stage = "compute"',
    'crossgl_descriptor_0_name = "values"',
    'crossgl_descriptor_0_kind = "storageBuffer"',
    "crossgl_descriptor_0_set = 0",
    "crossgl_descriptor_0_binding = 0",
    "crossgl_storage_buffer_count = 1",
    'crossgl_storage_buffer_0_name = "values"',
    'crossgl_storage_buffer_0_type = "float*"',
    'crossgl_storage_buffer_0_element_type = "float"',
    'crossgl_storage_buffer_0_address_space = "storage"',
    "crossgl_storage_buffer_0_read_access = true",
    "crossgl_storage_buffer_0_write_access = true",
    "crossgl_storage_buffer_read_count = 1",
    'crossgl_storage_buffer_read_0_name = "values"',
    "crossgl_storage_buffer_read_0_index = 0",
    "crossgl_storage_buffer_write_count = 1",
    'crossgl_storage_buffer_write_0_name = "values"',
    "crossgl_storage_buffer_write_0_index = 1",
    "crossgl_resource_fact_storage_buffer_read = true",
    "crossgl_resource_fact_storage_buffer_write = true",
    "crossgl_resource_fact_storage_images_empty = true",
    "crossgl_resource_fact_textures_empty = true",
    "crossgl_resource_fact_samplers_empty = true",
    "crossgl_target_independent_resource_metadata_count = 1",
    'crossgl_target_independent_resource_metadata_0_stage = "compute"',
    'crossgl_target_independent_resource_metadata_0_name = "values"',
    'crossgl_target_independent_resource_metadata_0_kind = "storageBuffer"',
    'crossgl_target_independent_resource_metadata_0_source_type = "float*"',
    'crossgl_target_independent_resource_metadata_0_element_type = "float"',
    'crossgl_target_independent_resource_metadata_0_address_space = "storage"',
    'crossgl_target_independent_resource_metadata_0_access = "read_write"',
    "crossgl_target_independent_resource_metadata_0_set = 0",
    "crossgl_target_independent_resource_metadata_0_binding = 0",
    "crossgl_target_independent_resource_metadata_0_target_independent = true",
    "crossgl_control_flow_if_count = 1",
    "crossgl_control_flow_if_0_has_else = true",
    'crossgl_branch_condition_0_expression = "x > 0.0"',
    'crossgl_branch_condition_0_comparison = "greater_than"',
    'crossgl_branch_condition_0_result_type = "bool"',
    "crossgl_branch_local_assignment_count = 2",
    'crossgl_branch_then_0_assignment = "y = x"',
    'crossgl_branch_else_0_assignment = "y = -x"',
    "crossgl_branch_return_fact_return_after_if = true",
    'crossgl_resource_metadata = "target-independent:storageBuffer:compute:values:set=0:binding=0:type=float*:element=float:addressSpace=storage:access=read_write"',
    'crossgl_if_compute_metadata = "control-flow:structured-if-else,condition:x_gt_zero,then:y=x,else:y=-x,return:after-if,storage-buffer:values[0]->values[1]"',
    "crossgl_real_mlir_smoke = true",
)
TEXTURE_SAMPLER_REQUIRED_VERIFIER_MARKERS = (
    f'crossgl_fixture = "{TEXTURE_SAMPLER_FIXTURE}"',
    'crossgl_stage = "compute"',
    'crossgl_entry_point = "main"',
    'crossgl_local_size = "1,1,1"',
    "crossgl_source_location_fact_source_file = true",
    "crossgl_source_location_fact_shader_module = true",
    "crossgl_source_location_fact_compute_stage = true",
    "crossgl_source_location_fact_entry_point = true",
    "crossgl_source_location_fact_layout_local_size = true",
    "crossgl_source_location_fact_storage_buffer_declaration = true",
    "crossgl_source_location_fact_texture_declaration = true",
    "crossgl_source_location_fact_sampler_declaration = true",
    "crossgl_source_location_fact_local_variable_declarations = true",
    "crossgl_source_location_fact_scalar_expression_statements = true",
    "crossgl_source_location_fact_texture_sample_lod = true",
    "crossgl_source_location_fact_storage_buffer_write = true",
    "crossgl_source_location_fact_return_statement = true",
    "crossgl_type_fact_void_entry_point = true",
    "crossgl_type_fact_vec4_scalar = true",
    "crossgl_type_fact_vec4_pointer_storage_buffer = true",
    "crossgl_type_fact_storage_buffer_element_type = true",
    "crossgl_type_fact_texture_sample_result_type = true",
    "crossgl_type_fact_texture_coordinate_type = true",
    "crossgl_type_fact_explicit_lod_scalar = true",
    "crossgl_type_fact_constructor_cast_expression = true",
    "crossgl_type_fact_scalar_literals = true",
    "crossgl_resource_count = 3",
    "crossgl_descriptor_count = 3",
    'crossgl_descriptor_1_name = "shadowMap"',
    'crossgl_descriptor_1_kind = "sampledTexture"',
    'crossgl_descriptor_2_name = "comparisonSampler"',
    'crossgl_descriptor_2_kind = "sampler"',
    "crossgl_texture_count = 1",
    'crossgl_texture_0_name = "shadowMap"',
    'crossgl_texture_0_type = "sampler2D"',
    'crossgl_texture_0_sampled_type = "float"',
    'crossgl_texture_0_dimension = "2d"',
    "crossgl_sampler_count = 1",
    'crossgl_sampler_0_name = "comparisonSampler"',
    'crossgl_sampler_0_type = "sampler"',
    "crossgl_sampler_0_comparison = true",
    "crossgl_texture_sample_lod_count = 1",
    'crossgl_texture_sample_lod_0_texture = "shadowMap"',
    'crossgl_texture_sample_lod_0_sampler = "comparisonSampler"',
    'crossgl_texture_sample_lod_0_coordinate_type = "vec2"',
    'crossgl_texture_sample_lod_0_lod_type = "float"',
    'crossgl_texture_sample_lod_0_result_type = "vec4"',
    "crossgl_target_independent_resource_metadata_count = 3",
    'crossgl_target_independent_resource_metadata_1_kind = "sampledTexture"',
    'crossgl_target_independent_resource_metadata_1_source_type = "sampler2D"',
    'crossgl_target_independent_resource_metadata_1_address_space = "uniform_constant"',
    'crossgl_target_independent_resource_metadata_1_access = "read"',
    'crossgl_target_independent_resource_metadata_2_kind = "sampler"',
    'crossgl_target_independent_resource_metadata_2_source_type = "sampler"',
    'crossgl_target_independent_resource_metadata_2_address_space = "uniform_constant"',
    'crossgl_target_independent_resource_metadata_2_access = "read"',
    "target-independent:sampledTexture:compute:shadowMap",
    "target-independent:sampler:compute:comparisonSampler",
    'crossgl_texture_sampler_metadata = "texture-lod:shadowMap+comparisonSampler:coord=vec2:lod=float:result=vec4"',
    "crossgl_real_mlir_smoke = true",
)
REQUIRED_VERIFIER_MARKERS_BY_INPUT = {
    VERIFIER_INPUT: MINIMAL_REQUIRED_VERIFIER_MARKERS,
    SCALAR_EXPRESSION_VERIFIER_INPUT: SCALAR_EXPRESSION_REQUIRED_VERIFIER_MARKERS,
    STORAGE_BUFFER_VERIFIER_INPUT: STORAGE_BUFFER_REQUIRED_VERIFIER_MARKERS,
    IF_COMPUTE_VERIFIER_INPUT: IF_COMPUTE_REQUIRED_VERIFIER_MARKERS,
    TEXTURE_SAMPLER_VERIFIER_INPUT: TEXTURE_SAMPLER_REQUIRED_VERIFIER_MARKERS,
}
VERIFIER_FIXTURES = (
    {
        "key": "minimal_compute",
        "ctest": VERIFIER_TEST,
        "input": VERIFIER_INPUT,
        "fixture": MINIMAL_FIXTURE,
        "coveredFacts": (
            "sourceLocationFacts.source_file",
            "sourceLocationFacts.compute_stage",
            "sourceLocationFacts.entry_point",
            "sourceLocationFacts.layout_local_size",
            "typeFacts.void_entry_point",
            "resourceFacts.localSize",
            "resourceFacts.targetIndependentResourceMetadata",
        ),
    },
    {
        "key": "scalar_expression_compute",
        "ctest": SCALAR_EXPRESSION_VERIFIER_TEST,
        "input": SCALAR_EXPRESSION_VERIFIER_INPUT,
        "fixture": SCALAR_EXPRESSION_FIXTURE,
        "coveredFacts": (
            "sourceLocationFacts.source_file",
            "sourceLocationFacts.compute_stage",
            "sourceLocationFacts.entry_point",
            "sourceLocationFacts.layout_local_size",
            "sourceLocationFacts.local_variable_declarations",
            "sourceLocationFacts.scalar_expression_statements",
            "typeFacts.void_entry_point",
            "typeFacts.float_scalar",
            "typeFacts.int_scalar",
            "typeFacts.bool_scalar",
            "typeFacts.scalar_literals",
            "typeFacts.constructor_cast_expression",
            "typeFacts.binary_expression_result_types",
            "typeFacts.comparison_expression_result_type",
            "resourceFacts.localSize",
            "resourceFacts.targetIndependentResourceMetadata",
        ),
    },
    {
        "key": "storage_buffer_compute",
        "ctest": STORAGE_BUFFER_VERIFIER_TEST,
        "input": STORAGE_BUFFER_VERIFIER_INPUT,
        "fixture": STORAGE_BUFFER_FIXTURE,
        "coveredFacts": (
            "sourceLocationFacts.source_file",
            "sourceLocationFacts.compute_stage",
            "sourceLocationFacts.entry_point",
            "sourceLocationFacts.layout_local_size",
            "sourceLocationFacts.storage_buffer_declaration",
            "sourceLocationFacts.storage_buffer_write",
            "typeFacts.void_entry_point",
            "typeFacts.float_scalar",
            "typeFacts.float_pointer_storage_buffer",
            "typeFacts.storage_buffer_element_type",
            "typeFacts.binary_expression_result_types",
            "resourceFacts.localSize",
            "resourceFacts.descriptors",
            "resourceFacts.descriptors[].stage",
            "resourceFacts.descriptors[].name",
            "resourceFacts.descriptors[].kind",
            "resourceFacts.descriptors[].set",
            "resourceFacts.descriptors[].binding",
            "resourceFacts.storageBuffers",
            "resourceFacts.storageBuffers[].name",
            "resourceFacts.storageBuffers[].type",
            "resourceFacts.storageBuffers[].elementType",
            "resourceFacts.storageBuffers[].addressSpace",
            "resourceFacts.storageBuffers[].writeAccess",
            "resourceFacts.targetIndependentResourceMetadata",
            "resourceFacts.targetIndependentResourceMetadata[].stage",
            "resourceFacts.targetIndependentResourceMetadata[].name",
            "resourceFacts.targetIndependentResourceMetadata[].kind",
            "resourceFacts.targetIndependentResourceMetadata[].sourceType",
            "resourceFacts.targetIndependentResourceMetadata[].elementType",
            "resourceFacts.targetIndependentResourceMetadata[].addressSpace",
            "resourceFacts.targetIndependentResourceMetadata[].access",
            "resourceFacts.targetIndependentResourceMetadata[].set",
            "resourceFacts.targetIndependentResourceMetadata[].binding",
            "resourceFacts.targetIndependentResourceMetadata[].targetIndependent",
        ),
    },
    {
        "key": "if_compute",
        "ctest": IF_COMPUTE_VERIFIER_TEST,
        "input": IF_COMPUTE_VERIFIER_INPUT,
        "fixture": IF_COMPUTE_FIXTURE,
        "coveredFacts": (
            "sourceLocationFacts.source_file",
            "sourceLocationFacts.compute_stage",
            "sourceLocationFacts.entry_point",
            "sourceLocationFacts.layout_local_size",
            "sourceLocationFacts.storage_buffer_declaration",
            "sourceLocationFacts.local_variable_declarations",
            "sourceLocationFacts.storage_buffer_read",
            "sourceLocationFacts.if_statement",
            "sourceLocationFacts.then_block_assignment",
            "sourceLocationFacts.else_block_assignment",
            "sourceLocationFacts.storage_buffer_write",
            "sourceLocationFacts.return_statement",
            "typeFacts.void_entry_point",
            "typeFacts.float_scalar",
            "typeFacts.float_pointer_storage_buffer",
            "typeFacts.storage_buffer_element_type",
            "typeFacts.comparison_expression_result_type",
            "typeFacts.branch_condition_bool",
            "typeFacts.assignment_expression_result_types",
            "typeFacts.unary_expression_result_types",
            "resourceFacts.localSize",
            "resourceFacts.descriptors",
            "resourceFacts.descriptors[].stage",
            "resourceFacts.descriptors[].name",
            "resourceFacts.descriptors[].kind",
            "resourceFacts.descriptors[].set",
            "resourceFacts.descriptors[].binding",
            "resourceFacts.storageBuffers",
            "resourceFacts.storageBuffers[].name",
            "resourceFacts.storageBuffers[].type",
            "resourceFacts.storageBuffers[].elementType",
            "resourceFacts.storageBuffers[].addressSpace",
            "resourceFacts.storageBuffers[].readAccess",
            "resourceFacts.storageBuffers[].writeAccess",
            "resourceFacts.storageBufferRead",
            "resourceFacts.storageBufferWrite",
            "resourceFacts.targetIndependentResourceMetadata",
            "resourceFacts.targetIndependentResourceMetadata[].stage",
            "resourceFacts.targetIndependentResourceMetadata[].name",
            "resourceFacts.targetIndependentResourceMetadata[].kind",
            "resourceFacts.targetIndependentResourceMetadata[].sourceType",
            "resourceFacts.targetIndependentResourceMetadata[].elementType",
            "resourceFacts.targetIndependentResourceMetadata[].addressSpace",
            "resourceFacts.targetIndependentResourceMetadata[].access",
            "resourceFacts.targetIndependentResourceMetadata[].set",
            "resourceFacts.targetIndependentResourceMetadata[].binding",
            "resourceFacts.targetIndependentResourceMetadata[].targetIndependent",
        ),
    },
    {
        "key": "texture_sampler_compute",
        "ctest": TEXTURE_SAMPLER_VERIFIER_TEST,
        "input": TEXTURE_SAMPLER_VERIFIER_INPUT,
        "fixture": TEXTURE_SAMPLER_FIXTURE,
        "coveredFacts": (
            "sourceLocationFacts.source_file",
            "sourceLocationFacts.compute_stage",
            "sourceLocationFacts.entry_point",
            "sourceLocationFacts.layout_local_size",
            "sourceLocationFacts.storage_buffer_declaration",
            "sourceLocationFacts.texture_declaration",
            "sourceLocationFacts.sampler_declaration",
            "sourceLocationFacts.local_variable_declarations",
            "sourceLocationFacts.scalar_expression_statements",
            "sourceLocationFacts.texture_sample_lod",
            "sourceLocationFacts.storage_buffer_write",
            "sourceLocationFacts.return_statement",
            "typeFacts.void_entry_point",
            "typeFacts.vec4_scalar",
            "typeFacts.vec4_pointer_storage_buffer",
            "typeFacts.storage_buffer_element_type",
            "typeFacts.texture_sample_result_type",
            "typeFacts.texture_coordinate_type",
            "typeFacts.explicit_lod_scalar",
            "typeFacts.constructor_cast_expression",
            "typeFacts.scalar_literals",
            "resourceFacts.localSize",
            "resourceFacts.descriptors",
            "resourceFacts.descriptors[].stage",
            "resourceFacts.descriptors[].name",
            "resourceFacts.descriptors[].kind",
            "resourceFacts.descriptors[].set",
            "resourceFacts.descriptors[].binding",
            "resourceFacts.storageBuffers",
            "resourceFacts.storageBuffers[].name",
            "resourceFacts.storageBuffers[].type",
            "resourceFacts.storageBuffers[].elementType",
            "resourceFacts.storageBuffers[].addressSpace",
            "resourceFacts.storageBuffers[].writeAccess",
            "resourceFacts.storageImages",
            "resourceFacts.textures",
            "resourceFacts.textures[].name",
            "resourceFacts.textures[].type",
            "resourceFacts.textures[].sampledType",
            "resourceFacts.textures[].dimension",
            "resourceFacts.textures[].arrayed",
            "resourceFacts.textures[].comparison",
            "resourceFacts.textures[].set",
            "resourceFacts.textures[].binding",
            "resourceFacts.samplers",
            "resourceFacts.samplers[].name",
            "resourceFacts.samplers[].type",
            "resourceFacts.samplers[].comparison",
            "resourceFacts.samplers[].set",
            "resourceFacts.samplers[].binding",
            "resourceFacts.targetIndependentResourceMetadata",
            "resourceFacts.targetIndependentResourceMetadata[].stage",
            "resourceFacts.targetIndependentResourceMetadata[].name",
            "resourceFacts.targetIndependentResourceMetadata[].kind",
            "resourceFacts.targetIndependentResourceMetadata[].sourceType",
            "resourceFacts.targetIndependentResourceMetadata[].elementType",
            "resourceFacts.targetIndependentResourceMetadata[].addressSpace",
            "resourceFacts.targetIndependentResourceMetadata[].access",
            "resourceFacts.targetIndependentResourceMetadata[].set",
            "resourceFacts.targetIndependentResourceMetadata[].binding",
            "resourceFacts.targetIndependentResourceMetadata[].targetIndependent",
        ),
    },
)
VERIFIER_TESTS = tuple(str(fixture["ctest"]) for fixture in VERIFIER_FIXTURES)
VERIFIER_INPUTS = tuple(str(fixture["input"]) for fixture in VERIFIER_FIXTURES)
VERIFIER_FIXTURE_PATHS = tuple(str(fixture["fixture"]) for fixture in VERIFIER_FIXTURES)
REQUIRED_VERIFIER_FACT_MARKERS = (
    "crossgl_source_location_fact_source_file",
    "crossgl_source_location_fact_shader_module",
    "crossgl_source_location_fact_compute_stage",
    "crossgl_source_location_fact_entry_point",
    "crossgl_source_location_fact_layout_local_size",
    "crossgl_source_location_fact_local_variable_declarations",
    "crossgl_source_location_fact_scalar_expression_statements",
    "crossgl_source_location_fact_return_statement",
    "crossgl_type_fact_void_entry_point",
    "crossgl_type_fact_int_scalar",
    "crossgl_type_fact_bool_scalar",
    "crossgl_type_fact_scalar_literals",
    "crossgl_type_fact_constructor_cast_expression",
    "crossgl_type_fact_comparison_expression_result_type",
    "crossgl_scalar_local_count",
    "crossgl_scalar_expression_count",
    "crossgl_source_location_fact_storage_buffer_declaration",
    "crossgl_source_location_fact_storage_buffer_read",
    "crossgl_source_location_fact_if_statement",
    "crossgl_source_location_fact_then_block_assignment",
    "crossgl_source_location_fact_else_block_assignment",
    "crossgl_source_location_fact_storage_buffer_write",
    "crossgl_type_fact_float_pointer_storage_buffer",
    "crossgl_type_fact_branch_condition_bool",
    "crossgl_type_fact_assignment_expression_result_types",
    "crossgl_type_fact_unary_expression_result_types",
    "crossgl_descriptor_0_name",
    "crossgl_storage_buffer_0_type",
    "crossgl_storage_buffer_0_read_access",
    "crossgl_storage_buffer_read_count",
    "crossgl_resource_fact_storage_buffer_read",
    "crossgl_control_flow_if_count",
    "crossgl_branch_condition_0_expression",
    "crossgl_branch_then_0_assignment",
    "crossgl_branch_else_0_assignment",
    "crossgl_branch_return_fact_return_after_if",
    "crossgl_target_independent_resource_metadata_0_access",
    "crossgl_source_location_fact_texture_declaration",
    "crossgl_source_location_fact_sampler_declaration",
    "crossgl_source_location_fact_texture_sample_lod",
    "crossgl_type_fact_vec4_scalar",
    "crossgl_type_fact_vec4_pointer_storage_buffer",
    "crossgl_type_fact_texture_sample_result_type",
    "crossgl_type_fact_texture_coordinate_type",
    "crossgl_type_fact_explicit_lod_scalar",
    "crossgl_descriptor_1_name",
    "crossgl_descriptor_2_name",
    "crossgl_texture_count",
    "crossgl_texture_0_type",
    "crossgl_sampler_count",
    "crossgl_texture_sample_lod_count",
    "crossgl_texture_sampler_metadata",
)
FORBIDDEN_VERIFIER_MARKERS = (
    "CrossGL pseudo-MLIR",
    'crossgl.real_mlir = "false"',
    "not a registered MLIR dialect",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from error


def parse_cmake_values(body: str) -> list[str]:
    values: list[str] = []
    for raw in re.findall(r'"((?:[^"\\]|\\.)*)"|([^\s#)]+)', body):
        value = raw[0] or raw[1]
        if not value:
            continue
        values.append(value.replace(r"\"", '"').replace(r"\\", "\\"))
    return values


def iter_cmake_set_bodies(text: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    for match in re.finditer(r"(?m)^set\(", text):
        position = match.end()
        while position < len(text) and text[position].isspace():
            position += 1
        name_start = position
        while position < len(text) and (
            text[position].isalnum() or text[position] == "_"
        ):
            position += 1
        name = text[name_start:position]
        if not name:
            continue
        body_start = position
        depth = 1
        in_quote = False
        escaped = False
        while position < len(text):
            character = text[position]
            if in_quote:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_quote = False
            else:
                if character == '"':
                    in_quote = True
                elif character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                    if depth == 0:
                        bodies.append((name, text[body_start:position]))
                        break
            position += 1
    return bodies


def cmake_list_values(text: str, name: str) -> list[str]:
    for set_name, body in iter_cmake_set_bodies(text):
        if set_name == name:
            return parse_cmake_values(body)
    return []


def cmake_set_values(text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for name, body in iter_cmake_set_bodies(text):
        values[name] = parse_cmake_values(body)
    return values


def resolve_cmake_value(value: str, variables: dict[str, list[str]]) -> str:
    resolved = value
    for _attempt in range(10):
        changed = False

        def replace(match: re.Match[str]) -> str:
            nonlocal changed
            name = match.group(1)
            replacements = variables.get(name)
            if not replacements:
                return match.group(0)
            changed = True
            return replacements[0]

        next_value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, resolved)
        resolved = next_value
        if not changed:
            break
    return resolved


def cmake_verifier_inputs(root: Path, errors: list[str]) -> list[str]:
    path = root / CMAKE_PATH
    if not path.exists():
        errors.append(f"missing {CMAKE_PATH}")
        return []
    values = cmake_list_values(read_text(path), VERIFIER_INPUT_LIST)
    if not values:
        errors.append(f"{CMAKE_PATH}: missing {VERIFIER_INPUT_LIST} entries")
    return values


def cmake_verifier_records(root: Path, errors: list[str]) -> list[dict[str, Any]]:
    path = root / CTEST_PATH
    if not path.exists():
        errors.append(f"missing {CTEST_PATH}")
        return []
    text = read_text(path)
    variables = cmake_set_values(text)
    raw_records = variables.get("CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS", [])
    if not raw_records:
        errors.append(f"{CTEST_PATH}: missing CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS")
        return []
    records: list[dict[str, Any]] = []
    for index, raw_record in enumerate(raw_records):
        fields = [
            resolve_cmake_value(field, variables) for field in raw_record.split("|")
        ]
        if len(fields) != 8:
            errors.append(
                f"{CTEST_PATH}: CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS[{index}] "
                "must have 8 pipe-separated fields"
            )
            continue
        key, ctest, fixture, input_path, _absolute_input = fields[:5]
        required_markers_var = fields[5]
        output_markers_var = fields[6]
        required_markers = variables.get(required_markers_var, [])
        if not required_markers:
            errors.append(
                f"{CTEST_PATH}: {required_markers_var} must list required verifier "
                f"markers for {input_path}"
            )
        records.append(
            {
                "key": key,
                "ctest": ctest,
                "fixture": fixture,
                "input": input_path,
                "requiredMarkersVar": required_markers_var,
                "requiredMarkers": required_markers,
                "outputMarkersVar": output_markers_var,
                "description": fields[7],
            }
        )
    input_order = {
        input_path: index
        for index, input_path in enumerate(cmake_verifier_inputs(root, errors))
    }
    records.sort(
        key=lambda record: input_order.get(str(record.get("input")), len(input_order))
    )
    return records


def fixture_inventory_verifier_records(
    root: Path, errors: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = root / FIXTURE_INVENTORY_PATH
    if not path.exists():
        errors.append(f"missing {FIXTURE_INVENTORY_PATH}")
        return [], []
    try:
        inventory = load_json(path)
    except ValueError as error:
        errors.append(f"{FIXTURE_INVENTORY_PATH}: {error}")
        return [], []
    inventory = require_object(inventory, str(FIXTURE_INVENTORY_PATH), errors)
    fixtures = require_list(
        inventory.get("fixtures"), f"{FIXTURE_INVENTORY_PATH}: fixtures", errors
    )
    cmake_inputs = cmake_verifier_inputs(root, errors)
    cmake_input_set = set(cmake_inputs)
    covered: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen_inputs: set[str] = set()
    for index, item in enumerate(fixtures):
        fixture = require_object(
            item, f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]", errors
        )
        fixture_path = require_string(
            fixture.get("path"),
            f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}].path",
            errors,
        )
        coverage = require_object(
            fixture.get("verifierInputCoverage"),
            f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}].verifierInputCoverage",
            errors,
        )
        status = require_string(
            coverage.get("status"),
            f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}].verifierInputCoverage.status",
            errors,
        )
        if status == "covered":
            input_path = validate_relative_path(
                coverage.get("input"),
                f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                "verifierInputCoverage.input",
                errors,
            )
            ctest = require_string(
                coverage.get("ctest"),
                f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                "verifierInputCoverage.ctest",
                errors,
            )
            key = require_string(
                coverage.get("key"),
                f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                "verifierInputCoverage.key",
                errors,
            )
            if coverage.get("sourceList") != VERIFIER_INPUT_LIST:
                errors.append(
                    f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                    f"verifierInputCoverage.sourceList must be {VERIFIER_INPUT_LIST!r}"
                )
            if coverage.get("fixture") != fixture_path:
                errors.append(
                    f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                    "verifierInputCoverage.fixture must match fixture path"
                )
            if input_path is not None:
                if input_path not in cmake_input_set:
                    errors.append(
                        f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                        f"verifierInputCoverage.input {input_path!r} missing from "
                        f"{VERIFIER_INPUT_LIST}"
                    )
                if input_path in seen_inputs:
                    errors.append(
                        f"{FIXTURE_INVENTORY_PATH}: duplicate verifier input "
                        f"coverage for {input_path!r}"
                    )
                seen_inputs.add(input_path)
            covered.append(
                {
                    "key": key,
                    "ctest": ctest,
                    "fixture": fixture_path,
                    "input": input_path,
                }
            )
        elif status == "blocked":
            blocker = require_object(
                coverage.get("blocker"),
                f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                "verifierInputCoverage.blocker",
                errors,
            )
            require_string(
                blocker.get("id"),
                f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                "verifierInputCoverage.blocker.id",
                errors,
            )
            require_string(
                blocker.get("reason"),
                f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                "verifierInputCoverage.blocker.reason",
                errors,
            )
            blocked.append({"fixture": fixture_path, "blocker": blocker})
        else:
            errors.append(
                f"{FIXTURE_INVENTORY_PATH}: fixtures[{index}]."
                "verifierInputCoverage.status must be 'covered' or 'blocked'"
            )
    missing_inputs = sorted(cmake_input_set - seen_inputs)
    if missing_inputs:
        errors.append(
            f"{FIXTURE_INVENTORY_PATH}: {VERIFIER_INPUT_LIST} entries without "
            "covered inventory fixtures: " + ", ".join(missing_inputs)
        )
    input_order = {input_path: index for index, input_path in enumerate(cmake_inputs)}
    covered.sort(
        key=lambda record: input_order.get(str(record.get("input")), len(input_order))
    )
    return covered, blocked


def dynamic_required_gate_facts(verifier_fixtures: list[dict[str, Any]]) -> list[str]:
    return [
        f"{GATE_OPTION}=ON",
        "MLIR_FOUND=TRUE",
        f"target {GATE_TARGET}",
        *(str(fixture["input"]) for fixture in verifier_fixtures),
        "mlir-opt discovery",
        "mlir-opt --version probe",
    ]


def require_object(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def require_string(value: object, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty string")
        return None
    return value


def require_optional_string(value: object, field: str, errors: list[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    errors.append(f"{field} must be a string or null")
    return None


def require_bool(value: object, field: str, errors: list[str]) -> bool | None:
    if not isinstance(value, bool):
        errors.append(f"{field} must be a boolean")
        return None
    return value


def require_list(value: object, field: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty list")
        return []
    return value


def require_string_list(value: object, field: str, errors: list[str]) -> list[str]:
    values = require_list(value, field, errors)
    strings: list[str] = []
    for index, item in enumerate(values):
        if isinstance(item, str) and item:
            strings.append(item)
        else:
            errors.append(f"{field}[{index}] must be a non-empty string")
    return strings


def require_string_list_allow_empty(
    value: object, field: str, errors: list[str]
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return []
    strings: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str) and item:
            strings.append(item)
        else:
            errors.append(f"{field}[{index}] must be a non-empty string")
    return strings


def validate_relative_path(value: object, field: str, errors: list[str]) -> str | None:
    path_text = require_string(value, field, errors)
    if path_text is None:
        return None
    if "\\" in path_text:
        errors.append(f"{field} must use POSIX separators")
        return None
    path = Path(path_text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        errors.append(f"{field} must be repository-relative without dot segments")
        return None
    return path_text


def find_verifier_manifest_records(
    manifest: dict[str, Any], errors: list[str]
) -> dict[str, dict[str, Any]]:
    checks = require_list(
        manifest.get("optionalToolGatedChecks"),
        f"{MANIFEST_PATH}: optionalToolGatedChecks",
        errors,
    )
    records: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(checks):
        record = require_object(
            item, f"{MANIFEST_PATH}: optionalToolGatedChecks[{index}]", errors
        )
        name = record.get("name")
        if name in VERIFIER_TESTS:
            records[str(name)] = record
    for test in VERIFIER_TESTS:
        if test not in records:
            errors.append(
                f"{MANIFEST_PATH}: optionalToolGatedChecks must include {test!r}"
            )
    return records


def check_manifest_contract(root: Path, errors: list[str]) -> None:
    path = root / MANIFEST_PATH
    if not path.exists():
        errors.append(f"missing {MANIFEST_PATH}")
        return
    try:
        manifest = load_json(path)
    except ValueError as error:
        errors.append(f"{MANIFEST_PATH}: {error}")
        return
    if not isinstance(manifest, dict):
        errors.append(f"{MANIFEST_PATH}: manifest must be an object")
        return

    manifest_records = find_verifier_manifest_records(manifest, errors)
    expected_scalars: dict[str, object] = {
        "kind": KIND,
        "generatedPath": "mlir/optional_tool_evidence.v0.json",
        "generatedBy": CTEST_PATH.as_posix(),
        "checker": "tools/check_mlir_optional_tool_evidence.py",
        "normalBuildRequired": False,
        "productionLinked": False,
    }
    required_records = {
        f"{GATE_OPTION} default",
        f"{GATE_OPTION} actual",
        "MLIR_FOUND",
        f"target {GATE_TARGET}",
        VERIFIER_INPUT_LIST,
        "verifierInputs",
        "verifierRegistrations",
        "mlir-opt discovery",
        "default-off no mlir-opt probe proof",
        "CTest skip labels and regex",
        "structured verifier skip diagnostics",
        "report-only source/resource catalog",
        "source/resource/entrypoint preservation fields",
        "scalar expression metadata facts",
        "storage-buffer resource facts",
        "storage-buffer read/write resource facts",
        "if-compute control-flow facts",
        "texture-sampler resource facts",
    }
    for fixture in VERIFIER_FIXTURES:
        test = str(fixture["ctest"])
        record = manifest_records.get(test, {})
        evidence = require_object(
            record.get("evidenceRecord"),
            f"{MANIFEST_PATH}: optionalToolGatedChecks[{test}].evidenceRecord",
            errors,
        )
        for key, expected in expected_scalars.items():
            if evidence.get(key) != expected:
                errors.append(
                    f"{MANIFEST_PATH}: {test}.evidenceRecord.{key} must be {expected!r}"
                )

        status_values = require_string_list(
            evidence.get("statusValues"),
            f"{MANIFEST_PATH}: {test}.evidenceRecord.statusValues",
            errors,
        )
        if status_values != list(STATUS_VALUES):
            errors.append(
                f"{MANIFEST_PATH}: {test}.evidenceRecord.statusValues "
                f"must be {list(STATUS_VALUES)!r}"
            )

        records = set(
            require_string_list(
                evidence.get("records"),
                f"{MANIFEST_PATH}: {test}.evidenceRecord.records",
                errors,
            )
        )
        missing = sorted(required_records - records)
        if missing:
            errors.append(
                f"{MANIFEST_PATH}: {test}.evidenceRecord.records missing "
                + ", ".join(missing)
            )

    real_mlir = require_object(
        manifest.get("realMlirExperimentPath"),
        f"{MANIFEST_PATH}: realMlirExperimentPath",
        errors,
    )
    inventory = require_list(
        real_mlir.get("verifierInputInventory"),
        f"{MANIFEST_PATH}: realMlirExperimentPath.verifierInputInventory",
        errors,
    )
    inventory_by_path: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(inventory):
        record = require_object(
            item,
            f"{MANIFEST_PATH}: realMlirExperimentPath.verifierInputInventory[{index}]",
            errors,
        )
        path_value = record.get("path")
        if isinstance(path_value, str):
            inventory_by_path[path_value] = record
    for fixture in VERIFIER_FIXTURES:
        input_path = str(fixture["input"])
        record = inventory_by_path.get(input_path)
        if record is None:
            errors.append(
                f"{MANIFEST_PATH}: verifierInputInventory must include {input_path!r}"
            )
            continue
        expected_inventory_scalars: dict[str, object] = {
            "sourceList": VERIFIER_INPUT_LIST,
            "fixture": fixture["fixture"],
            "verifierTool": "mlir-opt",
            "verifierTest": fixture["ctest"],
            "loweringStatus": "optional-tool-gated-smoke",
            "productionLinked": False,
            "pseudoMlirInput": False,
            "mustMatchCMake": True,
        }
        for key, expected in expected_inventory_scalars.items():
            if record.get(key) != expected:
                errors.append(
                    f"{MANIFEST_PATH}: verifierInputInventory[{input_path}].{key} "
                    f"must be {expected!r}"
                )
        covered = set(
            require_string_list(
                record.get("coveredFixtureFacts"),
                f"{MANIFEST_PATH}: verifierInputInventory[{input_path}]."
                "coveredFixtureFacts",
                errors,
            )
        )
        missing_facts = sorted(set(fixture["coveredFacts"]) - covered)
        if missing_facts:
            errors.append(
                f"{MANIFEST_PATH}: verifierInputInventory[{input_path}]."
                "coveredFixtureFacts missing " + ", ".join(missing_facts)
            )


def check_cmake_metadata_contract(root: Path, errors: list[str]) -> None:
    ctest_path = root / CTEST_PATH
    cmake_path = root / CMAKE_PATH
    if not ctest_path.exists():
        errors.append(f"missing {CTEST_PATH}")
        return
    if not cmake_path.exists():
        errors.append(f"missing {CMAKE_PATH}")
        return
    ctest_text = read_text(ctest_path)
    cmake_text = read_text(cmake_path)
    for token in (
        "CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE",
        "optional_tool_evidence.v0.json",
        KIND,
        "mlirDiscovery",
        "optionDefault",
        "optionActual",
        "verifierInput",
        "verifierInputs",
        "verifierTool",
        "verifierRegistration",
        "verifierRegistrations",
        "ctests",
        "invokesMlirOpt",
        "usesVerifyDiagnostics",
        "buildsExperimentTarget",
        "requiredFiles",
        "reportOnlyCatalogs",
        "sourceResourceCatalog",
        SOURCE_RESOURCE_CATALOG,
        SOURCE_RESOURCE_CATALOG_CHECKER,
        SOURCE_RESOURCE_PRESERVATION_SECTION,
        "toolProbeEvidence",
        "defaultOffMayRunFindProgram",
        "defaultOffMayRunVersionProbe",
        "skipEvidence",
        "skipDiagnostics",
        "missingReasons",
        "findProgramAttempted",
        "versionProbeAttempted",
        "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_REQUIRED_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_OUTPUT_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_REQUIRED_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_OUTPUT_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_REQUIRED_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_OUTPUT_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_REQUIRED_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_OUTPUT_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS",
        "crossgl_mlir_json_string_list",
        "tools/check_mlir_optional_tool_evidence.py",
        EVIDENCE_TEST,
        "--evidence",
        AVAILABLE_TOOL_LABEL,
        UNAVAILABLE_TOOL_LABEL,
    ):
        if token not in ctest_text:
            errors.append(
                f"{CTEST_PATH}: missing optional-tool evidence token {token!r}"
            )

    default_condition = f"if(NOT {GATE_OPTION})"
    default_start = ctest_text.find(default_condition)
    default_else = ctest_text.find("\nelse()", default_start)
    if default_start == -1 or default_else == -1:
        errors.append(f"{CTEST_PATH}: missing default-off verifier branch")
    else:
        default_body = ctest_text[default_start:default_else]
        for forbidden in ("find_program(", "mlir-opt", "MLIR_OPT"):
            if forbidden in default_body:
                errors.append(
                    f"{CTEST_PATH}: default-off branch must not probe optional "
                    f"MLIR tooling via {forbidden!r}"
                )

    for token in (f"set({VERIFIER_INPUT_LIST}", *VERIFIER_INPUTS):
        if token not in cmake_text:
            errors.append(f"{CMAKE_PATH}: missing verifier input authority {token!r}")
    for fixture in VERIFIER_FIXTURES:
        for token in (
            str(fixture["ctest"]),
            str(fixture["fixture"]),
            str(fixture["input"]),
        ):
            if token not in ctest_text:
                errors.append(f"{CTEST_PATH}: missing verifier fixture token {token!r}")

    for token in REQUIRED_VERIFIER_FACT_MARKERS:
        if token not in ctest_text:
            errors.append(
                f"{CTEST_PATH}: missing fact-preservation verifier token {token!r}"
            )


def check_verifier_input_markers(root: Path, errors: list[str]) -> None:
    covered_fixtures, _blocked_fixtures = fixture_inventory_verifier_records(
        root, errors
    )
    verifier_records = cmake_verifier_records(root, errors)
    records_by_input = {
        str(record["input"]): record
        for record in verifier_records
        if isinstance(record.get("input"), str)
    }
    covered_inputs = {
        str(fixture["input"])
        for fixture in covered_fixtures
        if isinstance(fixture.get("input"), str)
    }
    cmake_inputs = set(cmake_verifier_inputs(root, errors))
    missing_record_inputs = sorted(cmake_inputs - set(records_by_input))
    if missing_record_inputs:
        errors.append(
            f"{CTEST_PATH}: CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS missing "
            "CMake verifier inputs: " + ", ".join(missing_record_inputs)
        )
    missing_coverage_inputs = sorted(cmake_inputs - covered_inputs)
    if missing_coverage_inputs:
        errors.append(
            f"{FIXTURE_INVENTORY_PATH}: covered verifier inventory missing "
            "CMake verifier inputs: " + ", ".join(missing_coverage_inputs)
        )

    for fixture in covered_fixtures:
        input_path = fixture.get("input")
        if not isinstance(input_path, str):
            continue
        record = records_by_input.get(input_path)
        if record is None:
            errors.append(f"{CTEST_PATH}: missing verifier record for {input_path}")
            continue
        for field in ("key", "ctest", "fixture"):
            if fixture.get(field) != record.get(field):
                errors.append(
                    f"{FIXTURE_INVENTORY_PATH}: verifierInputCoverage for "
                    f"{input_path} must match CMake verifier record field {field}"
                )
        required_markers = [
            marker
            for marker in record.get("requiredMarkers", [])
            if isinstance(marker, str) and marker
        ]
        if not required_markers:
            errors.append(
                f"{CTEST_PATH}: {record.get('requiredMarkersVar')} must provide "
                f"non-empty marker coverage for {input_path}"
            )
            continue
        required_anchors = (
            f'crossgl_fixture = "{fixture.get("fixture")}"',
            "crossgl_real_mlir_smoke = true",
        )
        for marker in required_anchors:
            if marker not in required_markers:
                errors.append(
                    f"{CTEST_PATH}: {record.get('requiredMarkersVar')} for "
                    f"{input_path} must include marker {marker!r}"
                )
        path = root / input_path
        if not path.exists():
            errors.append(f"missing MLIR verifier input {input_path}")
            continue
        text = read_text(path)
        for marker in required_markers:
            if marker not in text:
                errors.append(
                    f"{input_path}: missing required fact-preservation marker "
                    f"{marker!r}"
                )
        for marker in FORBIDDEN_VERIFIER_MARKERS:
            if marker in text:
                errors.append(f"{input_path}: contains pseudo-MLIR marker {marker!r}")


def check_evidence_file(root: Path, evidence_path: Path, errors: list[str]) -> None:
    if not evidence_path.exists():
        errors.append(f"optional MLIR evidence file missing: {evidence_path}")
        return
    try:
        evidence = load_json(evidence_path)
    except ValueError as error:
        errors.append(f"{evidence_path}: {error}")
        return
    evidence = require_object(evidence, str(evidence_path), errors)
    verifier_fixtures, _blocked_verifier_fixtures = fixture_inventory_verifier_records(
        root, errors
    )
    if not verifier_fixtures:
        verifier_fixtures = list(VERIFIER_FIXTURES)
    expected_required_gate_facts = dynamic_required_gate_facts(verifier_fixtures)
    if evidence.get("schemaVersion") != 1:
        errors.append(f"{evidence_path}: schemaVersion must be 1")
    if evidence.get("kind") != KIND:
        errors.append(f"{evidence_path}: kind must be {KIND!r}")
    status = require_string(evidence.get("status"), f"{evidence_path}: status", errors)
    if status is not None and status not in STATUS_VALUES:
        errors.append(
            f"{evidence_path}: status must be one of {', '.join(STATUS_VALUES)}"
        )
    if evidence.get("normalBuildRequired") is not False:
        errors.append(f"{evidence_path}: normalBuildRequired must be false")
    if evidence.get("productionLinked") is not False:
        errors.append(f"{evidence_path}: productionLinked must be false")

    discovery = require_object(
        evidence.get("mlirDiscovery"), f"{evidence_path}: mlirDiscovery", errors
    )
    option_enabled = require_bool(
        discovery.get("optionEnabled"),
        f"{evidence_path}: mlirDiscovery.optionEnabled",
        errors,
    )
    option_default = require_string(
        discovery.get("optionDefault"),
        f"{evidence_path}: mlirDiscovery.optionDefault",
        errors,
    )
    option_actual = require_string(
        discovery.get("optionActual"),
        f"{evidence_path}: mlirDiscovery.optionActual",
        errors,
    )
    mlir_found = require_bool(
        discovery.get("mlirFound"), f"{evidence_path}: mlirDiscovery.mlirFound", errors
    )
    target_created = require_bool(
        discovery.get("targetCreated"),
        f"{evidence_path}: mlirDiscovery.targetCreated",
        errors,
    )
    expected_discovery: dict[str, object] = {
        "cmakeOption": GATE_OPTION,
        "cmakePackage": "MLIR",
        "target": GATE_TARGET,
    }
    for key, expected in expected_discovery.items():
        if discovery.get(key) != expected:
            errors.append(f"{evidence_path}: mlirDiscovery.{key} must be {expected!r}")
    if option_default is not None and option_default != OPTION_DEFAULT:
        errors.append(
            f"{evidence_path}: mlirDiscovery.optionDefault must be {OPTION_DEFAULT!r}"
        )
    if option_actual is not None and option_actual not in OPTION_ACTUAL_VALUES:
        errors.append(
            f"{evidence_path}: mlirDiscovery.optionActual must be one of "
            f"{', '.join(OPTION_ACTUAL_VALUES)}"
        )
    if option_enabled is not None and option_actual is not None:
        expected_actual = "ON" if option_enabled else "OFF"
        if option_actual != expected_actual:
            errors.append(
                f"{evidence_path}: mlirDiscovery.optionActual must match "
                "mlirDiscovery.optionEnabled"
            )

    verifier_input = require_object(
        evidence.get("verifierInput"), f"{evidence_path}: verifierInput", errors
    )
    input_path = validate_relative_path(
        verifier_input.get("path"), f"{evidence_path}: verifierInput.path", errors
    )
    if input_path != VERIFIER_INPUT:
        errors.append(f"{evidence_path}: verifierInput.path must be {VERIFIER_INPUT!r}")
    if verifier_input.get("fixture") != MINIMAL_FIXTURE:
        errors.append(
            f"{evidence_path}: verifierInput.fixture must be {MINIMAL_FIXTURE!r}"
        )
    if verifier_input.get("sourceList") != VERIFIER_INPUT_LIST:
        errors.append(
            f"{evidence_path}: verifierInput.sourceList must be {VERIFIER_INPUT_LIST!r}"
        )
    input_present = require_bool(
        verifier_input.get("present"),
        f"{evidence_path}: verifierInput.present",
        errors,
    )
    if input_path is not None and input_present != (root / input_path).exists():
        errors.append(
            f"{evidence_path}: verifierInput.present must match repository fixture "
            f"presence for {input_path}"
        )

    verifier_inputs = require_list(
        evidence.get("verifierInputs"), f"{evidence_path}: verifierInputs", errors
    )
    verifier_inputs_by_key: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(verifier_inputs):
        record = require_object(
            item, f"{evidence_path}: verifierInputs[{index}]", errors
        )
        key = require_string(
            record.get("key"), f"{evidence_path}: verifierInputs[{index}].key", errors
        )
        if key is not None:
            verifier_inputs_by_key[key] = record
    verifier_input_present_by_key: dict[str, bool | None] = {}
    for fixture in verifier_fixtures:
        key = str(fixture["key"])
        record = verifier_inputs_by_key.get(key)
        if record is None:
            errors.append(f"{evidence_path}: verifierInputs must include key {key!r}")
            continue
        record_path = validate_relative_path(
            record.get("path"), f"{evidence_path}: verifierInputs[{key}].path", errors
        )
        if record_path != fixture["input"]:
            errors.append(
                f"{evidence_path}: verifierInputs[{key}].path must be "
                f"{fixture['input']!r}"
            )
        if record.get("fixture") != fixture["fixture"]:
            errors.append(
                f"{evidence_path}: verifierInputs[{key}].fixture must be "
                f"{fixture['fixture']!r}"
            )
        if record.get("sourceList") != VERIFIER_INPUT_LIST:
            errors.append(
                f"{evidence_path}: verifierInputs[{key}].sourceList must be "
                f"{VERIFIER_INPUT_LIST!r}"
            )
        present = require_bool(
            record.get("present"),
            f"{evidence_path}: verifierInputs[{key}].present",
            errors,
        )
        verifier_input_present_by_key[key] = present
        if record_path is not None and present != (root / record_path).exists():
            errors.append(
                f"{evidence_path}: verifierInputs[{key}].present must match "
                f"repository fixture presence for {record_path}"
            )

    tool = require_object(
        evidence.get("verifierTool"), f"{evidence_path}: verifierTool", errors
    )
    tool_found = require_bool(
        tool.get("found"), f"{evidence_path}: verifierTool.found", errors
    )
    discovery_status = require_string(
        tool.get("discoveryStatus"),
        f"{evidence_path}: verifierTool.discoveryStatus",
        errors,
    )
    if (
        discovery_status is not None
        and discovery_status not in TOOL_DISCOVERY_STATUS_VALUES
    ):
        errors.append(
            f"{evidence_path}: verifierTool.discoveryStatus must be one of "
            + ", ".join(TOOL_DISCOVERY_STATUS_VALUES)
        )
    if tool.get("name") != "mlir-opt":
        errors.append(f"{evidence_path}: verifierTool.name must be 'mlir-opt'")
    if tool.get("requiredForNormalBuild") is not False:
        errors.append(
            f"{evidence_path}: verifierTool.requiredForNormalBuild must be false"
        )
    tool_path = require_optional_string(
        tool.get("path"), f"{evidence_path}: verifierTool.path", errors
    )
    if tool_found is False and tool_path is not None:
        errors.append(f"{evidence_path}: verifierTool.path must be null when not found")
    if tool_found is True and not tool_path:
        errors.append(f"{evidence_path}: verifierTool.path must be recorded when found")

    registration = require_object(
        evidence.get("verifierRegistration"),
        f"{evidence_path}: verifierRegistration",
        errors,
    )
    if registration.get("ctest") != VERIFIER_TEST:
        errors.append(
            f"{evidence_path}: verifierRegistration.ctest must be {VERIFIER_TEST!r}"
        )
    registration_mode = require_string(
        registration.get("mode"),
        f"{evidence_path}: verifierRegistration.mode",
        errors,
    )
    if (
        registration_mode is not None
        and registration_mode not in VERIFIER_REGISTRATION_MODES
    ):
        errors.append(
            f"{evidence_path}: verifierRegistration.mode must be one of "
            + ", ".join(VERIFIER_REGISTRATION_MODES)
        )
    invokes_mlir_opt = require_bool(
        registration.get("invokesMlirOpt"),
        f"{evidence_path}: verifierRegistration.invokesMlirOpt",
        errors,
    )
    uses_verify_diagnostics = require_bool(
        registration.get("usesVerifyDiagnostics"),
        f"{evidence_path}: verifierRegistration.usesVerifyDiagnostics",
        errors,
    )
    builds_experiment_target = require_bool(
        registration.get("buildsExperimentTarget"),
        f"{evidence_path}: verifierRegistration.buildsExperimentTarget",
        errors,
    )
    build_target = require_optional_string(
        registration.get("buildTarget"),
        f"{evidence_path}: verifierRegistration.buildTarget",
        errors,
    )
    registration_input = validate_relative_path(
        registration.get("input"),
        f"{evidence_path}: verifierRegistration.input",
        errors,
    )
    if registration_input != VERIFIER_INPUT:
        errors.append(
            f"{evidence_path}: verifierRegistration.input must be {VERIFIER_INPUT!r}"
        )
    required_files = require_string_list_allow_empty(
        registration.get("requiredFiles"),
        f"{evidence_path}: verifierRegistration.requiredFiles",
        errors,
    )
    if registration.get("normalBuildRequired") is not False:
        errors.append(
            f"{evidence_path}: verifierRegistration.normalBuildRequired must be false"
        )
    if registration.get("productionLinked") is not False:
        errors.append(
            f"{evidence_path}: verifierRegistration.productionLinked must be false"
        )

    verifier_registrations = require_list(
        evidence.get("verifierRegistrations"),
        f"{evidence_path}: verifierRegistrations",
        errors,
    )
    verifier_registrations_by_key: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(verifier_registrations):
        record = require_object(
            item, f"{evidence_path}: verifierRegistrations[{index}]", errors
        )
        key = require_string(
            record.get("key"),
            f"{evidence_path}: verifierRegistrations[{index}].key",
            errors,
        )
        if key is not None:
            verifier_registrations_by_key[key] = record
    verifier_registration_infos: list[dict[str, Any]] = []
    for fixture in verifier_fixtures:
        key = str(fixture["key"])
        record = verifier_registrations_by_key.get(key)
        if record is None:
            errors.append(
                f"{evidence_path}: verifierRegistrations must include key {key!r}"
            )
            continue
        if record.get("ctest") != fixture["ctest"]:
            errors.append(
                f"{evidence_path}: verifierRegistrations[{key}].ctest must be "
                f"{fixture['ctest']!r}"
            )
        record_mode = require_string(
            record.get("mode"),
            f"{evidence_path}: verifierRegistrations[{key}].mode",
            errors,
        )
        if record_mode is not None and record_mode not in VERIFIER_REGISTRATION_MODES:
            errors.append(
                f"{evidence_path}: verifierRegistrations[{key}].mode must be one of "
                + ", ".join(VERIFIER_REGISTRATION_MODES)
            )
        record_invokes_mlir_opt = require_bool(
            record.get("invokesMlirOpt"),
            f"{evidence_path}: verifierRegistrations[{key}].invokesMlirOpt",
            errors,
        )
        record_uses_verify_diagnostics = require_bool(
            record.get("usesVerifyDiagnostics"),
            f"{evidence_path}: verifierRegistrations[{key}].usesVerifyDiagnostics",
            errors,
        )
        record_builds_experiment_target = require_bool(
            record.get("buildsExperimentTarget"),
            f"{evidence_path}: verifierRegistrations[{key}].buildsExperimentTarget",
            errors,
        )
        record_build_target = require_optional_string(
            record.get("buildTarget"),
            f"{evidence_path}: verifierRegistrations[{key}].buildTarget",
            errors,
        )
        record_input = validate_relative_path(
            record.get("input"),
            f"{evidence_path}: verifierRegistrations[{key}].input",
            errors,
        )
        if record_input != fixture["input"]:
            errors.append(
                f"{evidence_path}: verifierRegistrations[{key}].input must be "
                f"{fixture['input']!r}"
            )
        record_required_files = require_string_list_allow_empty(
            record.get("requiredFiles"),
            f"{evidence_path}: verifierRegistrations[{key}].requiredFiles",
            errors,
        )
        if record.get("normalBuildRequired") is not False:
            errors.append(
                f"{evidence_path}: verifierRegistrations[{key}]."
                "normalBuildRequired must be false"
            )
        if record.get("productionLinked") is not False:
            errors.append(
                f"{evidence_path}: verifierRegistrations[{key}]."
                "productionLinked must be false"
            )
        verifier_registration_infos.append(
            {
                "key": key,
                "input": fixture["input"],
                "mode": record_mode,
                "invokesMlirOpt": record_invokes_mlir_opt,
                "usesVerifyDiagnostics": record_uses_verify_diagnostics,
                "buildsExperimentTarget": record_builds_experiment_target,
                "buildTarget": record_build_target,
                "requiredFiles": record_required_files,
            }
        )

    report_only_catalogs = require_object(
        evidence.get("reportOnlyCatalogs"),
        f"{evidence_path}: reportOnlyCatalogs",
        errors,
    )
    source_resource_catalog = require_object(
        report_only_catalogs.get("sourceResourceCatalog"),
        f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog",
        errors,
    )
    catalog_path = validate_relative_path(
        source_resource_catalog.get("path"),
        f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.path",
        errors,
    )
    expected_catalog_scalars: dict[str, object] = {
        "checker": SOURCE_RESOURCE_CATALOG_CHECKER,
        "requiredFixtureSection": SOURCE_RESOURCE_PRESERVATION_SECTION,
        "optionalMlirToolingRequired": False,
        "normalBuildRequired": False,
        "productionLinked": False,
    }
    for key, expected in expected_catalog_scalars.items():
        if source_resource_catalog.get(key) != expected:
            errors.append(
                f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.{key} "
                f"must be {expected!r}"
            )
    if catalog_path != SOURCE_RESOURCE_CATALOG:
        errors.append(
            f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.path "
            f"must be {SOURCE_RESOURCE_CATALOG!r}"
        )
    if catalog_path is not None:
        full_catalog_path = root / catalog_path
        if not full_catalog_path.exists():
            errors.append(
                f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.path "
                f"does not exist: {catalog_path}"
            )
        else:
            try:
                catalog = load_json(full_catalog_path)
            except ValueError as error:
                errors.append(f"{catalog_path}: {error}")
                catalog = {}
            catalog = require_object(catalog, str(catalog_path), errors)
            if catalog.get("kind") != SOURCE_RESOURCE_CATALOG_KIND:
                errors.append(
                    f"{catalog_path}: kind must be {SOURCE_RESOURCE_CATALOG_KIND!r}"
                )
            fixtures = require_list(
                catalog.get("fixtures"), f"{catalog_path}: fixtures", errors
            )
            for index, item in enumerate(fixtures):
                fixture = require_object(
                    item, f"{catalog_path}: fixtures[{index}]", errors
                )
                preservation = require_object(
                    fixture.get(SOURCE_RESOURCE_PRESERVATION_SECTION),
                    f"{catalog_path}: fixtures[{index}]."
                    f"{SOURCE_RESOURCE_PRESERVATION_SECTION}",
                    errors,
                )
                if preservation.get("missingManifestFields") != []:
                    errors.append(
                        f"{catalog_path}: fixtures[{index}]."
                        f"{SOURCE_RESOURCE_PRESERVATION_SECTION}."
                        "missingManifestFields must be empty"
                    )

    tool_probe = require_object(
        evidence.get("toolProbeEvidence"),
        f"{evidence_path}: toolProbeEvidence",
        errors,
    )
    if tool_probe.get("defaultOffBranch") != DEFAULT_OFF_BRANCH:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.defaultOffBranch must be "
            f"{DEFAULT_OFF_BRANCH!r}"
        )
    if tool_probe.get("findProgramCommand") != FIND_PROGRAM_COMMAND:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.findProgramCommand must be "
            f"{FIND_PROGRAM_COMMAND!r}"
        )
    if tool_probe.get("versionProbeCommand") != VERSION_PROBE_COMMAND:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.versionProbeCommand must be "
            f"{VERSION_PROBE_COMMAND!r}"
        )
    if tool_probe.get("defaultOffMayRunFindProgram") is not False:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.defaultOffMayRunFindProgram "
            "must be false"
        )
    if tool_probe.get("defaultOffMayRunVersionProbe") is not False:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.defaultOffMayRunVersionProbe "
            "must be false"
        )
    tool_probe_find_program_attempted = require_bool(
        tool_probe.get("findProgramAttempted"),
        f"{evidence_path}: toolProbeEvidence.findProgramAttempted",
        errors,
    )
    tool_probe_version_probe_attempted = require_bool(
        tool_probe.get("versionProbeAttempted"),
        f"{evidence_path}: toolProbeEvidence.versionProbeAttempted",
        errors,
    )

    skip = require_object(
        evidence.get("skipEvidence"), f"{evidence_path}: skipEvidence", errors
    )
    skip_registered = require_bool(
        skip.get("skipRegistered"),
        f"{evidence_path}: skipEvidence.skipRegistered",
        errors,
    )
    labels = set(
        require_string_list(
            skip.get("labels"), f"{evidence_path}: skipEvidence.labels", errors
        )
    )
    if BASE_SKIP_LABELS - labels:
        errors.append(
            f"{evidence_path}: skipEvidence.labels must include mlir and optional-mlir"
        )
    if AVAILABLE_TOOL_LABEL in labels and UNAVAILABLE_TOOL_LABEL in labels:
        errors.append(
            f"{evidence_path}: skipEvidence.labels must not mix "
            f"{AVAILABLE_TOOL_LABEL} and {UNAVAILABLE_TOOL_LABEL}"
        )
    if skip.get("ctest") != VERIFIER_TEST:
        errors.append(f"{evidence_path}: skipEvidence.ctest must be {VERIFIER_TEST!r}")
    skip_ctests = require_string_list(
        skip.get("ctests"), f"{evidence_path}: skipEvidence.ctests", errors
    )
    expected_verifier_tests = [str(fixture["ctest"]) for fixture in verifier_fixtures]
    if skip_ctests != expected_verifier_tests:
        errors.append(
            f"{evidence_path}: skipEvidence.ctests must be {expected_verifier_tests!r}"
        )
    reason = require_optional_string(
        skip.get("reason"), f"{evidence_path}: skipEvidence.reason", errors
    )
    skip_regex = require_optional_string(
        skip.get("skipRegularExpression"),
        f"{evidence_path}: skipEvidence.skipRegularExpression",
        errors,
    )
    if skip_registered is True and skip_regex != SKIP_REGEX:
        errors.append(
            f"{evidence_path}: skipped optional MLIR verifier evidence must use "
            f"skip regex {SKIP_REGEX!r}"
        )
    if skip_registered is False and skip_regex not in (None, ""):
        errors.append(
            f"{evidence_path}: available optional MLIR verifier evidence must not "
            "carry a skip regex"
        )

    skip_diagnostics = require_object(
        evidence.get("skipDiagnostics"), f"{evidence_path}: skipDiagnostics", errors
    )
    diagnostics_status = require_string(
        skip_diagnostics.get("status"),
        f"{evidence_path}: skipDiagnostics.status",
        errors,
    )
    if (
        status is not None
        and diagnostics_status is not None
        and diagnostics_status != status
    ):
        errors.append(
            f"{evidence_path}: skipDiagnostics.status must match top-level status"
        )
    if skip_diagnostics.get("reportOnly") is not True:
        errors.append(f"{evidence_path}: skipDiagnostics.reportOnly must be true")
    required_gate_facts = require_string_list(
        skip_diagnostics.get("requiredGateFacts"),
        f"{evidence_path}: skipDiagnostics.requiredGateFacts",
        errors,
    )
    if required_gate_facts != expected_required_gate_facts:
        errors.append(
            f"{evidence_path}: skipDiagnostics.requiredGateFacts must be "
            f"{expected_required_gate_facts!r}"
        )
    missing_reasons = require_string_list_allow_empty(
        skip_diagnostics.get("missingReasons"),
        f"{evidence_path}: skipDiagnostics.missingReasons",
        errors,
    )
    find_program_attempted = require_bool(
        skip_diagnostics.get("findProgramAttempted"),
        f"{evidence_path}: skipDiagnostics.findProgramAttempted",
        errors,
    )
    version_probe_attempted = require_bool(
        skip_diagnostics.get("versionProbeAttempted"),
        f"{evidence_path}: skipDiagnostics.versionProbeAttempted",
        errors,
    )
    if (
        tool_probe_find_program_attempted is not None
        and find_program_attempted is not None
        and tool_probe_find_program_attempted != find_program_attempted
    ):
        errors.append(
            f"{evidence_path}: toolProbeEvidence.findProgramAttempted must match "
            "skipDiagnostics.findProgramAttempted"
        )
    if (
        tool_probe_version_probe_attempted is not None
        and version_probe_attempted is not None
        and tool_probe_version_probe_attempted != version_probe_attempted
    ):
        errors.append(
            f"{evidence_path}: toolProbeEvidence.versionProbeAttempted must match "
            "skipDiagnostics.versionProbeAttempted"
        )
    if version_probe_attempted is True and find_program_attempted is not True:
        errors.append(
            f"{evidence_path}: skipDiagnostics.versionProbeAttempted requires "
            "findProgramAttempted=true"
        )
    if skip_registered is True:
        if not missing_reasons:
            errors.append(
                f"{evidence_path}: skipped optional MLIR verifier evidence must "
                "record missing reasons"
            )
        if reason is not None:
            for missing_reason in missing_reasons:
                if missing_reason not in reason:
                    errors.append(
                        f"{evidence_path}: skipDiagnostics.missingReasons item "
                        f"{missing_reason!r} must appear in skipEvidence.reason"
                    )
    if skip_registered is False and missing_reasons:
        errors.append(
            f"{evidence_path}: available optional MLIR verifier evidence must not "
            "record missing reasons"
        )
    if registration_mode == "skipped":
        if skip_registered is not True:
            errors.append(
                f"{evidence_path}: skipped verifier registration must match "
                "skipRegistered=true"
            )
        if invokes_mlir_opt is not False:
            errors.append(
                f"{evidence_path}: skipped verifier registration must not invoke "
                "mlir-opt"
            )
        if uses_verify_diagnostics is not False:
            errors.append(
                f"{evidence_path}: skipped verifier registration must not use "
                "--verify-diagnostics"
            )
        if builds_experiment_target is not False:
            errors.append(
                f"{evidence_path}: skipped verifier registration must not build "
                f"{GATE_TARGET}"
            )
        if build_target is not None:
            errors.append(
                f"{evidence_path}: skipped verifier registration buildTarget "
                "must be null"
            )
        if required_files:
            errors.append(
                f"{evidence_path}: skipped verifier registration requiredFiles "
                "must be empty"
            )
    elif registration_mode == "executable":
        if skip_registered is not False:
            errors.append(
                f"{evidence_path}: executable verifier registration must match "
                "skipRegistered=false"
            )
        if invokes_mlir_opt is not True:
            errors.append(
                f"{evidence_path}: executable verifier registration must invoke "
                "mlir-opt"
            )
        if uses_verify_diagnostics is not True:
            errors.append(
                f"{evidence_path}: executable verifier registration must use "
                "--verify-diagnostics"
            )
        if builds_experiment_target is not True:
            errors.append(
                f"{evidence_path}: executable verifier registration must build "
                f"{GATE_TARGET}"
            )
        if build_target != GATE_TARGET:
            errors.append(
                f"{evidence_path}: executable verifier registration buildTarget "
                f"must be {GATE_TARGET!r}"
            )
        if required_files != [VERIFIER_INPUT]:
            errors.append(
                f"{evidence_path}: executable verifier registration requiredFiles "
                f"must be {[VERIFIER_INPUT]!r}"
            )
    for info in verifier_registration_infos:
        key = info["key"]
        if info["mode"] == "skipped":
            if skip_registered is not True:
                errors.append(
                    f"{evidence_path}: skipped verifier registration {key} must "
                    "match skipRegistered=true"
                )
            if info["invokesMlirOpt"] is not False:
                errors.append(
                    f"{evidence_path}: skipped verifier registration {key} must "
                    "not invoke mlir-opt"
                )
            if info["usesVerifyDiagnostics"] is not False:
                errors.append(
                    f"{evidence_path}: skipped verifier registration {key} must "
                    "not use --verify-diagnostics"
                )
            if info["buildsExperimentTarget"] is not False:
                errors.append(
                    f"{evidence_path}: skipped verifier registration {key} must "
                    f"not build {GATE_TARGET}"
                )
            if info["buildTarget"] is not None:
                errors.append(
                    f"{evidence_path}: skipped verifier registration {key} "
                    "buildTarget must be null"
                )
            if info["requiredFiles"]:
                errors.append(
                    f"{evidence_path}: skipped verifier registration {key} "
                    "requiredFiles must be empty"
                )
        elif info["mode"] == "executable":
            if skip_registered is not False:
                errors.append(
                    f"{evidence_path}: executable verifier registration {key} "
                    "must match skipRegistered=false"
                )
            if info["invokesMlirOpt"] is not True:
                errors.append(
                    f"{evidence_path}: executable verifier registration {key} "
                    "must invoke mlir-opt"
                )
            if info["usesVerifyDiagnostics"] is not True:
                errors.append(
                    f"{evidence_path}: executable verifier registration {key} "
                    "must use --verify-diagnostics"
                )
            if info["buildsExperimentTarget"] is not True:
                errors.append(
                    f"{evidence_path}: executable verifier registration {key} "
                    f"must build {GATE_TARGET}"
                )
            if info["buildTarget"] != GATE_TARGET:
                errors.append(
                    f"{evidence_path}: executable verifier registration {key} "
                    f"buildTarget must be {GATE_TARGET!r}"
                )
            if info["requiredFiles"] != [info["input"]]:
                errors.append(
                    f"{evidence_path}: executable verifier registration {key} "
                    f"requiredFiles must be {[info['input']]!r}"
                )

    all_verifier_inputs_present = input_present is True and all(
        verifier_input_present_by_key.get(str(fixture["key"])) is True
        for fixture in verifier_fixtures
    )

    if status == "default-off":
        if option_enabled is not False:
            errors.append(
                f"{evidence_path}: default-off status requires optionEnabled=false"
            )
        if target_created is not False:
            errors.append(
                f"{evidence_path}: default-off status must not create {GATE_TARGET}"
            )
        if discovery_status != "not-run-default-off":
            errors.append(
                f"{evidence_path}: default-off status must record not-run-default-off"
            )
        if skip_registered is not True:
            errors.append(f"{evidence_path}: default-off status must register a skip")
        if reason is None or f"{GATE_OPTION}=OFF" not in reason:
            errors.append(
                f"{evidence_path}: default-off skip must report {GATE_OPTION}=OFF"
            )
        if missing_reasons != [DEFAULT_OFF_MISSING_REASON]:
            errors.append(
                f"{evidence_path}: default-off skip diagnostics must record only "
                f"{DEFAULT_OFF_MISSING_REASON!r}"
            )
        if find_program_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off skip diagnostics must not run "
                "find_program"
            )
        if tool_probe_find_program_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off tool probe evidence must not run "
                "find_program"
            )
        if version_probe_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off skip diagnostics must not probe "
                "mlir-opt --version"
            )
        if tool_probe_version_probe_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off tool probe evidence must not probe "
                "mlir-opt --version"
            )
        if UNAVAILABLE_TOOL_LABEL not in labels:
            errors.append(
                f"{evidence_path}: default-off labels must include "
                f"{UNAVAILABLE_TOOL_LABEL}"
            )
        if AVAILABLE_TOOL_LABEL in labels:
            errors.append(
                f"{evidence_path}: default-off labels must not include "
                f"{AVAILABLE_TOOL_LABEL}"
            )
        if registration_mode != "skipped":
            errors.append(
                f"{evidence_path}: default-off status must record skipped verifier "
                "registration"
            )
    elif status == "toolchain-unavailable":
        if option_enabled is not True:
            errors.append(
                f"{evidence_path}: toolchain-unavailable requires optionEnabled=true"
            )
        if skip_registered is not True:
            errors.append(
                f"{evidence_path}: toolchain-unavailable status must register a skip"
            )
        if reason is None or not reason:
            errors.append(
                f"{evidence_path}: toolchain-unavailable skip must explain why"
            )
        if not missing_reasons:
            errors.append(
                f"{evidence_path}: toolchain-unavailable skip diagnostics must "
                "record missing reasons"
            )
        if DEFAULT_OFF_MISSING_REASON in missing_reasons:
            errors.append(
                f"{evidence_path}: toolchain-unavailable skip diagnostics must not "
                f"record {DEFAULT_OFF_MISSING_REASON!r}"
            )
        if discovery_status == "not-run-toolchain-incomplete":
            if find_program_attempted is not False:
                errors.append(
                    f"{evidence_path}: incomplete toolchain skip must not probe "
                    "mlir-opt"
                )
            if version_probe_attempted is not False:
                errors.append(
                    f"{evidence_path}: incomplete toolchain skip must not probe "
                    "mlir-opt --version"
                )
        if discovery_status in {"not-found", "probe-failed"}:
            if find_program_attempted is not True:
                errors.append(
                    f"{evidence_path}: mlir-opt unavailable diagnostics must record "
                    "findProgramAttempted=true"
                )
        if discovery_status == "not-found" and version_probe_attempted is not False:
            errors.append(
                f"{evidence_path}: mlir-opt not-found diagnostics must not record "
                "versionProbeAttempted=true"
            )
        if discovery_status == "probe-failed" and version_probe_attempted is not True:
            errors.append(
                f"{evidence_path}: mlir-opt probe-failed diagnostics must record "
                "versionProbeAttempted=true"
            )
        if discovery_status == "available":
            errors.append(
                f"{evidence_path}: toolchain-unavailable cannot record available tool"
            )
        if UNAVAILABLE_TOOL_LABEL not in labels:
            errors.append(
                f"{evidence_path}: toolchain-unavailable labels must include "
                f"{UNAVAILABLE_TOOL_LABEL}"
            )
        if AVAILABLE_TOOL_LABEL in labels:
            errors.append(
                f"{evidence_path}: toolchain-unavailable labels must not include "
                f"{AVAILABLE_TOOL_LABEL}"
            )
        if registration_mode != "skipped":
            errors.append(
                f"{evidence_path}: toolchain-unavailable status must record skipped "
                "verifier registration"
            )
    elif status == "toolchain-available":
        if not (
            option_enabled
            and mlir_found
            and target_created
            and all_verifier_inputs_present
        ):
            errors.append(
                f"{evidence_path}: toolchain-available requires enabled option, "
                "MLIR_FOUND, target creation, and all verifier inputs"
            )
        if tool_found is not True or discovery_status != "available":
            errors.append(
                f"{evidence_path}: toolchain-available requires mlir-opt availability"
            )
        if skip_registered is not False:
            errors.append(
                f"{evidence_path}: toolchain-available must not register a skip"
            )
        if reason not in (None, ""):
            errors.append(
                f"{evidence_path}: toolchain-available must not carry a skip reason"
            )
        if missing_reasons:
            errors.append(
                f"{evidence_path}: toolchain-available skip diagnostics must have "
                "no missing reasons"
            )
        if find_program_attempted is not True:
            errors.append(
                f"{evidence_path}: toolchain-available diagnostics must record "
                "findProgramAttempted=true"
            )
        if version_probe_attempted is not True:
            errors.append(
                f"{evidence_path}: toolchain-available diagnostics must record "
                "versionProbeAttempted=true"
            )
        if AVAILABLE_TOOL_LABEL not in labels:
            errors.append(
                f"{evidence_path}: toolchain-available labels must include "
                f"{AVAILABLE_TOOL_LABEL}"
            )
        if UNAVAILABLE_TOOL_LABEL in labels:
            errors.append(
                f"{evidence_path}: toolchain-available labels must not include "
                f"{UNAVAILABLE_TOOL_LABEL}"
            )
        if registration_mode != "executable":
            errors.append(
                f"{evidence_path}: toolchain-available status must record "
                "executable verifier registration"
            )


def run_checks(root: Path, evidence: Path | None) -> list[str]:
    errors: list[str] = []
    check_manifest_contract(root, errors)
    check_cmake_metadata_contract(root, errors)
    check_verifier_input_markers(root, errors)
    if evidence is not None:
        check_evidence_file(root, evidence, errors)
    return errors


def verifier_input_text(required_markers: tuple[str, ...]) -> str:
    return (
        "// Builtin-MLIR verifier smoke fixture for the optional CrossGL MLIR "
        "experiment.\n"
        "// It intentionally uses only builtin module syntax and metadata "
        "attributes.\n"
        "module attributes {\n  " + ",\n  ".join(required_markers) + "\n} {\n}\n"
    )


def cmake_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cmake_string_list(name: str, values: tuple[str, ...]) -> str:
    lines = [f"set({name}"]
    lines.extend(f"  {cmake_quote(value)}" for value in values)
    lines.append(")")
    return "\n".join(lines)


def write_minimal_repo(root: Path) -> Path:
    (root / MANIFEST_PATH.parent).mkdir(parents=True, exist_ok=True)
    (root / CTEST_PATH.parent).mkdir(parents=True, exist_ok=True)
    (root / VERIFIER_INPUT).parent.mkdir(parents=True, exist_ok=True)
    (root / VERIFIER_INPUT).write_text(
        verifier_input_text(MINIMAL_REQUIRED_VERIFIER_MARKERS), encoding="utf-8"
    )
    (root / SCALAR_EXPRESSION_VERIFIER_INPUT).write_text(
        verifier_input_text(SCALAR_EXPRESSION_REQUIRED_VERIFIER_MARKERS),
        encoding="utf-8",
    )
    (root / STORAGE_BUFFER_VERIFIER_INPUT).write_text(
        verifier_input_text(STORAGE_BUFFER_REQUIRED_VERIFIER_MARKERS),
        encoding="utf-8",
    )
    (root / IF_COMPUTE_VERIFIER_INPUT).write_text(
        verifier_input_text(IF_COMPUTE_REQUIRED_VERIFIER_MARKERS),
        encoding="utf-8",
    )
    (root / TEXTURE_SAMPLER_VERIFIER_INPUT).write_text(
        verifier_input_text(TEXTURE_SAMPLER_REQUIRED_VERIFIER_MARKERS),
        encoding="utf-8",
    )
    (root / SOURCE_RESOURCE_CATALOG).parent.mkdir(parents=True, exist_ok=True)
    (root / SOURCE_RESOURCE_CATALOG).write_text(
        json.dumps(
            {
                "kind": SOURCE_RESOURCE_CATALOG_KIND,
                "fixtures": [
                    {
                        "sourceResourceEntrypointPreservation": {
                            "missingManifestFields": []
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / CMAKE_PATH).write_text(
        f"""
set({VERIFIER_INPUT_LIST}
  {VERIFIER_INPUT}
  {SCALAR_EXPRESSION_VERIFIER_INPUT}
  {STORAGE_BUFFER_VERIFIER_INPUT}
  {IF_COMPUTE_VERIFIER_INPUT}
  {TEXTURE_SAMPLER_VERIFIER_INPUT}
)
""",
        encoding="utf-8",
    )
    (root / FIXTURE_INVENTORY_PATH).write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "path": fixture["fixture"],
                        "verifierInputCoverage": {
                            "status": "covered",
                            "key": fixture["key"],
                            "input": fixture["input"],
                            "fixture": fixture["fixture"],
                            "ctest": fixture["ctest"],
                            "sourceList": VERIFIER_INPUT_LIST,
                        },
                    }
                    for fixture in VERIFIER_FIXTURES
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / MANIFEST_PATH).write_text(
        json.dumps(
            {
                "realMlirExperimentPath": {
                    "verifierInputInventory": [
                        {
                            "path": fixture["input"],
                            "sourceList": VERIFIER_INPUT_LIST,
                            "fixture": fixture["fixture"],
                            "coveredFixtureFacts": list(fixture["coveredFacts"]),
                            "verifierTool": "mlir-opt",
                            "verifierTest": fixture["ctest"],
                            "loweringStatus": "optional-tool-gated-smoke",
                            "productionLinked": False,
                            "pseudoMlirInput": False,
                            "mustMatchCMake": True,
                        }
                        for fixture in VERIFIER_FIXTURES
                    ]
                },
                "optionalToolGatedChecks": [
                    {
                        "name": fixture["ctest"],
                        "evidenceRecord": {
                            "kind": KIND,
                            "generatedPath": "mlir/optional_tool_evidence.v0.json",
                            "generatedBy": CTEST_PATH.as_posix(),
                            "checker": "tools/check_mlir_optional_tool_evidence.py",
                            "statusValues": list(STATUS_VALUES),
                            "records": [
                                GATE_OPTION,
                                f"{GATE_OPTION} default",
                                f"{GATE_OPTION} actual",
                                "MLIR_FOUND",
                                f"target {GATE_TARGET}",
                                VERIFIER_INPUT_LIST,
                                "verifierInputs",
                                "verifierRegistrations",
                                "mlir-opt discovery",
                                "default-off no mlir-opt probe proof",
                                "CTest skip labels and regex",
                                "structured verifier skip diagnostics",
                                "report-only source/resource catalog",
                                "source/resource/entrypoint preservation fields",
                                "scalar expression metadata facts",
                                "storage-buffer resource facts",
                                "storage-buffer read/write resource facts",
                                "if-compute control-flow facts",
                                "texture-sampler resource facts",
                            ],
                            "normalBuildRequired": False,
                            "productionLinked": False,
                        },
                    }
                    for fixture in VERIFIER_FIXTURES
                ],
            }
        ),
        encoding="utf-8",
    )
    minimal_output_markers = (
        "crossgl_fixture",
        MINIMAL_FIXTURE,
        "crossgl_entry_point",
        *REQUIRED_VERIFIER_FACT_MARKERS,
        "crossgl_resource_count",
        "target-independent:none",
        "crossgl_real_mlir_smoke",
    )
    scalar_output_markers = (
        "crossgl_fixture",
        SCALAR_EXPRESSION_FIXTURE,
        "crossgl_entry_point",
        "crossgl_source_location_fact_local_variable_declarations",
        "crossgl_source_location_fact_scalar_expression_statements",
        "crossgl_type_fact_int_scalar",
        "crossgl_type_fact_bool_scalar",
        "crossgl_type_fact_constructor_cast_expression",
        "crossgl_type_fact_comparison_expression_result_type",
        "crossgl_scalar_local_count",
        "crossgl_scalar_expression_count",
        "locals:base:float,scaled:float,count:int,keep:bool",
        "crossgl_real_mlir_smoke",
    )
    storage_output_markers = (
        "crossgl_fixture",
        STORAGE_BUFFER_FIXTURE,
        "crossgl_entry_point",
        "crossgl_source_location_fact_storage_buffer_declaration",
        "crossgl_source_location_fact_storage_buffer_write",
        "crossgl_type_fact_float_pointer_storage_buffer",
        "crossgl_resource_count",
        "crossgl_descriptor_count",
        "crossgl_descriptor_0_name",
        "values",
        "crossgl_storage_buffer_0_type",
        "float*",
        "crossgl_target_independent_resource_metadata_0_access",
        "read_write",
        "crossgl_real_mlir_smoke",
    )
    if_output_markers = (
        "crossgl_fixture",
        IF_COMPUTE_FIXTURE,
        "crossgl_entry_point",
        "crossgl_source_location_fact_storage_buffer_read",
        "crossgl_source_location_fact_if_statement",
        "crossgl_source_location_fact_then_block_assignment",
        "crossgl_source_location_fact_else_block_assignment",
        "crossgl_source_location_fact_storage_buffer_write",
        "crossgl_type_fact_branch_condition_bool",
        "crossgl_type_fact_assignment_expression_result_types",
        "crossgl_type_fact_unary_expression_result_types",
        "crossgl_storage_buffer_0_read_access",
        "crossgl_storage_buffer_read_count",
        "crossgl_resource_fact_storage_buffer_read",
        "crossgl_control_flow_if_count",
        "crossgl_branch_condition_0_expression",
        "x > 0.0",
        "crossgl_branch_then_0_assignment",
        "y = x",
        "crossgl_branch_else_0_assignment",
        "y = -x",
        "crossgl_branch_return_fact_return_after_if",
        "control-flow:structured-if-else",
        "storage-buffer:values[0]->values[1]",
        "crossgl_real_mlir_smoke",
    )
    texture_output_markers = (
        "crossgl_fixture",
        TEXTURE_SAMPLER_FIXTURE,
        "crossgl_entry_point",
        "crossgl_source_location_fact_texture_declaration",
        "crossgl_source_location_fact_sampler_declaration",
        "crossgl_source_location_fact_texture_sample_lod",
        "crossgl_type_fact_vec4_scalar",
        "crossgl_type_fact_vec4_pointer_storage_buffer",
        "crossgl_type_fact_texture_sample_result_type",
        "crossgl_type_fact_texture_coordinate_type",
        "crossgl_type_fact_explicit_lod_scalar",
        "crossgl_descriptor_1_name",
        "shadowMap",
        "crossgl_descriptor_2_name",
        "comparisonSampler",
        "crossgl_texture_count",
        "crossgl_texture_0_type",
        "sampler2D",
        "crossgl_sampler_count",
        "crossgl_texture_sample_lod_count",
        "texture-lod:shadowMap+comparisonSampler",
        "crossgl_real_mlir_smoke",
    )
    ctest_text = (
        cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS",
            MINIMAL_REQUIRED_VERIFIER_MARKERS,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS",
            minimal_output_markers,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_REQUIRED_MARKERS",
            SCALAR_EXPRESSION_REQUIRED_VERIFIER_MARKERS,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_OUTPUT_MARKERS",
            scalar_output_markers,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_REQUIRED_MARKERS",
            STORAGE_BUFFER_REQUIRED_VERIFIER_MARKERS,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_OUTPUT_MARKERS",
            storage_output_markers,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_REQUIRED_MARKERS",
            IF_COMPUTE_REQUIRED_VERIFIER_MARKERS,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_OUTPUT_MARKERS",
            if_output_markers,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_REQUIRED_MARKERS",
            TEXTURE_SAMPLER_REQUIRED_VERIFIER_MARKERS,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_OUTPUT_MARKERS",
            texture_output_markers,
        )
        + f"""
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS
  "minimal_compute|{VERIFIER_TEST}|{MINIMAL_FIXTURE}|{VERIFIER_INPUT}|{VERIFIER_INPUT}|CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS|minimal compute"
  "scalar_expression_compute|{SCALAR_EXPRESSION_VERIFIER_TEST}|{SCALAR_EXPRESSION_FIXTURE}|{SCALAR_EXPRESSION_VERIFIER_INPUT}|{SCALAR_EXPRESSION_VERIFIER_INPUT}|CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_OUTPUT_MARKERS|scalar-expression compute"
  "storage_buffer_compute|{STORAGE_BUFFER_VERIFIER_TEST}|{STORAGE_BUFFER_FIXTURE}|{STORAGE_BUFFER_VERIFIER_INPUT}|{STORAGE_BUFFER_VERIFIER_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_OUTPUT_MARKERS|storage-buffer compute"
  "if_compute|{IF_COMPUTE_VERIFIER_TEST}|{IF_COMPUTE_FIXTURE}|{IF_COMPUTE_VERIFIER_INPUT}|{IF_COMPUTE_VERIFIER_INPUT}|CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_OUTPUT_MARKERS|if-compute"
  "texture_sampler_compute|{TEXTURE_SAMPLER_VERIFIER_TEST}|{TEXTURE_SAMPLER_FIXTURE}|{TEXTURE_SAMPLER_VERIFIER_INPUT}|{TEXTURE_SAMPLER_VERIFIER_INPUT}|CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_OUTPUT_MARKERS|texture-sampler compute")
set(CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE
  "${{CMAKE_CURRENT_BINARY_DIR}}/mlir/optional_tool_evidence.v0.json")
function(crossgl_mlir_json_string_list out)
endfunction()
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
  "[\\"mlir\\", \\"optional-mlir\\", \\"{UNAVAILABLE_TOOL_LABEL}\\"]")
if(NOT {GATE_OPTION})
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "default-off")
else()
  find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
    "[\\"mlir\\", \\"optional-mlir\\", \\"{AVAILABLE_TOOL_LABEL}\\"]")
endif()
file(WRITE "${{CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}}"
  "{{\\"kind\\": \\"{KIND}\\", \\"mlirDiscovery\\": "
  "{{\\"optionDefault\\": \\"OFF\\", \\"optionActual\\": \\"OFF\\"}}, "
  "\\"verifierInput\\": {{}}, \\"verifierTool\\": {{}}, "
  "\\"verifierInputs\\": [], "
  "\\"verifierRegistration\\": {{\\"mode\\": \\"skipped\\", "
  "\\"invokesMlirOpt\\": false, \\"usesVerifyDiagnostics\\": false, "
  "\\"buildsExperimentTarget\\": false, \\"requiredFiles\\": []}}, "
  "\\"verifierRegistrations\\": [], "
  "\\"reportOnlyCatalogs\\": {{\\"sourceResourceCatalog\\": "
  "{{\\"path\\": \\"{SOURCE_RESOURCE_CATALOG}\\", "
  "\\"checker\\": \\"{SOURCE_RESOURCE_CATALOG_CHECKER}\\", "
  "\\"requiredFixtureSection\\": "
  "\\"{SOURCE_RESOURCE_PRESERVATION_SECTION}\\", "
  "\\"optionalMlirToolingRequired\\": false, "
  "\\"normalBuildRequired\\": false, \\"productionLinked\\": false}}}}, "
  "\\"toolProbeEvidence\\": {{\\"defaultOffMayRunFindProgram\\": false, "
  "\\"defaultOffMayRunVersionProbe\\": false}}, "
  "\\"skipEvidence\\": {{\\"ctests\\": []}}, \\"skipDiagnostics\\": "
  "{{\\"missingReasons\\": [], \\"findProgramAttempted\\": false, "
  "\\"versionProbeAttempted\\": false}}}}")
add_test(NAME {EVIDENCE_TEST}
  COMMAND python tools/check_mlir_optional_tool_evidence.py
    --evidence "${{CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}}")
"""
    )
    (root / CTEST_PATH).write_text(ctest_text, encoding="utf-8")
    evidence_path = root / "mlir/optional_tool_evidence.v0.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": KIND,
                "status": "default-off",
                "normalBuildRequired": False,
                "productionLinked": False,
                "mlirDiscovery": {
                    "cmakeOption": GATE_OPTION,
                    "optionDefault": OPTION_DEFAULT,
                    "optionActual": "OFF",
                    "optionEnabled": False,
                    "cmakePackage": "MLIR",
                    "mlirFound": False,
                    "target": GATE_TARGET,
                    "targetCreated": False,
                },
                "verifierInput": {
                    "sourceList": VERIFIER_INPUT_LIST,
                    "path": VERIFIER_INPUT,
                    "fixture": MINIMAL_FIXTURE,
                    "present": True,
                },
                "verifierInputs": [
                    {
                        "key": fixture["key"],
                        "sourceList": VERIFIER_INPUT_LIST,
                        "path": fixture["input"],
                        "fixture": fixture["fixture"],
                        "present": True,
                    }
                    for fixture in VERIFIER_FIXTURES
                ],
                "verifierTool": {
                    "name": "mlir-opt",
                    "requiredForNormalBuild": False,
                    "found": False,
                    "path": None,
                    "discoveryStatus": "not-run-default-off",
                },
                "verifierRegistration": {
                    "ctest": VERIFIER_TEST,
                    "mode": "skipped",
                    "invokesMlirOpt": False,
                    "usesVerifyDiagnostics": False,
                    "buildsExperimentTarget": False,
                    "buildTarget": None,
                    "input": VERIFIER_INPUT,
                    "requiredFiles": [],
                    "normalBuildRequired": False,
                    "productionLinked": False,
                },
                "verifierRegistrations": [
                    {
                        "key": fixture["key"],
                        "ctest": fixture["ctest"],
                        "mode": "skipped",
                        "invokesMlirOpt": False,
                        "usesVerifyDiagnostics": False,
                        "buildsExperimentTarget": False,
                        "buildTarget": None,
                        "input": fixture["input"],
                        "requiredFiles": [],
                        "normalBuildRequired": False,
                        "productionLinked": False,
                    }
                    for fixture in VERIFIER_FIXTURES
                ],
                "reportOnlyCatalogs": {
                    "sourceResourceCatalog": {
                        "path": SOURCE_RESOURCE_CATALOG,
                        "checker": SOURCE_RESOURCE_CATALOG_CHECKER,
                        "requiredFixtureSection": SOURCE_RESOURCE_PRESERVATION_SECTION,
                        "optionalMlirToolingRequired": False,
                        "normalBuildRequired": False,
                        "productionLinked": False,
                    }
                },
                "toolProbeEvidence": {
                    "defaultOffBranch": DEFAULT_OFF_BRANCH,
                    "findProgramCommand": FIND_PROGRAM_COMMAND,
                    "versionProbeCommand": VERSION_PROBE_COMMAND,
                    "defaultOffMayRunFindProgram": False,
                    "defaultOffMayRunVersionProbe": False,
                    "findProgramAttempted": False,
                    "versionProbeAttempted": False,
                },
                "skipEvidence": {
                    "ctest": VERIFIER_TEST,
                    "ctests": list(VERIFIER_TESTS),
                    "skipRegistered": True,
                    "reason": (
                        f"{GATE_OPTION}=OFF; real MLIR verifier disabled by default"
                    ),
                    "labels": ["mlir", "optional-mlir", UNAVAILABLE_TOOL_LABEL],
                    "skipRegularExpression": SKIP_REGEX,
                },
                "skipDiagnostics": {
                    "status": "default-off",
                    "reportOnly": True,
                    "requiredGateFacts": list(REQUIRED_GATE_FACTS),
                    "missingReasons": [DEFAULT_OFF_MISSING_REASON],
                    "findProgramAttempted": False,
                    "versionProbeAttempted": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return evidence_path


def run_self_test() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        evidence_path = write_minimal_repo(root)
        if run_checks(root, evidence_path):
            errors.append("self-test: valid optional-tool evidence was rejected")

        data = load_json(evidence_path)
        data["skipEvidence"]["skipRegistered"] = False
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must register a skip" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: default-off non-skip evidence was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["skipDiagnostics"]["missingReasons"] = []
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must record missing reasons" in error
            or "default-off skip diagnostics" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: missing skip diagnostics reasons were accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["mlirDiscovery"]["optionDefault"] = "ON"
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "mlirDiscovery.optionDefault" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: changed MLIR option default was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["toolProbeEvidence"]["findProgramAttempted"] = True
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "toolProbeEvidence.findProgramAttempted" in error
            or "default-off tool probe evidence" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: default-off tool probe evidence was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["reportOnlyCatalogs"]["sourceResourceCatalog"][
            "requiredFixtureSection"
        ] = "sourceLocations"
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "requiredFixtureSection" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append(
                "self-test: stale source/resource catalog section was accepted"
            )

        evidence_path = write_minimal_repo(root)
        catalog = load_json(root / SOURCE_RESOURCE_CATALOG)
        catalog["fixtures"][0][SOURCE_RESOURCE_PRESERVATION_SECTION][
            "missingManifestFields"
        ] = ["sourceLocationFacts.entry_point"]
        (root / SOURCE_RESOURCE_CATALOG).write_text(
            json.dumps(catalog), encoding="utf-8"
        )
        if not any(
            "missingManifestFields must be empty" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append(
                "self-test: incomplete source/resource catalog evidence was accepted"
            )

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["status"] = "toolchain-available"
        data["mlirDiscovery"]["optionEnabled"] = True
        data["mlirDiscovery"]["optionActual"] = "ON"
        data["mlirDiscovery"]["mlirFound"] = True
        data["mlirDiscovery"]["targetCreated"] = True
        data["verifierTool"]["found"] = True
        data["verifierTool"]["path"] = "/opt/mlir/bin/mlir-opt"
        data["verifierTool"]["discoveryStatus"] = "available"
        data["verifierRegistration"]["mode"] = "executable"
        data["verifierRegistration"]["invokesMlirOpt"] = True
        data["verifierRegistration"]["usesVerifyDiagnostics"] = True
        data["verifierRegistration"]["buildsExperimentTarget"] = True
        data["verifierRegistration"]["buildTarget"] = GATE_TARGET
        data["verifierRegistration"]["requiredFiles"] = [VERIFIER_INPUT]
        for registration_record in data["verifierRegistrations"]:
            registration_record["mode"] = "executable"
            registration_record["invokesMlirOpt"] = True
            registration_record["usesVerifyDiagnostics"] = True
            registration_record["buildsExperimentTarget"] = True
            registration_record["buildTarget"] = GATE_TARGET
            registration_record["requiredFiles"] = [registration_record["input"]]
        data["toolProbeEvidence"]["findProgramAttempted"] = True
        data["toolProbeEvidence"]["versionProbeAttempted"] = True
        data["skipEvidence"]["skipRegistered"] = False
        data["skipEvidence"]["reason"] = ""
        data["skipEvidence"]["labels"] = [
            "mlir",
            "optional-mlir",
            AVAILABLE_TOOL_LABEL,
        ]
        data["skipEvidence"]["skipRegularExpression"] = ""
        data["skipDiagnostics"]["status"] = "toolchain-available"
        data["skipDiagnostics"]["missingReasons"] = []
        data["skipDiagnostics"]["findProgramAttempted"] = True
        data["skipDiagnostics"]["versionProbeAttempted"] = True
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if run_checks(root, evidence_path):
            errors.append("self-test: valid toolchain-available evidence was rejected")

        data["skipEvidence"]["skipRegularExpression"] = SKIP_REGEX
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must not carry a skip regex" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: tool-available skip regex was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["verifierRegistration"]["mode"] = "executable"
        data["verifierRegistration"]["invokesMlirOpt"] = True
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "executable verifier registration" in error
            or "default-off status must record skipped verifier registration" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append(
                "self-test: contradictory default-off executable verifier "
                "registration was accepted"
            )

        evidence_path = write_minimal_repo(root)
        manifest = load_json(root / MANIFEST_PATH)
        del manifest["optionalToolGatedChecks"][0]["evidenceRecord"]
        (root / MANIFEST_PATH).write_text(json.dumps(manifest), encoding="utf-8")
        if not any(
            "evidenceRecord" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: manifest without evidenceRecord was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["skipEvidence"]["labels"].append(AVAILABLE_TOOL_LABEL)
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must not mix" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: mixed tool availability labels were accepted")

        evidence_path = write_minimal_repo(root)
        ctest_text = read_text(root / CTEST_PATH).replace(
            f"if(NOT {GATE_OPTION})\n",
            f"if(NOT {GATE_OPTION})\n  find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)\n",
        )
        (root / CTEST_PATH).write_text(ctest_text, encoding="utf-8")
        if not any(
            "default-off branch" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: default-off mlir-opt probe was accepted")

        evidence_path = write_minimal_repo(root)
        verifier_input = read_text(root / VERIFIER_INPUT).replace(
            "  crossgl_type_fact_void_entry_point = true,\n", ""
        )
        (root / VERIFIER_INPUT).write_text(verifier_input, encoding="utf-8")
        if not any(
            "missing required fact-preservation marker" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: verifier input missing fact marker was accepted")

        evidence_path = write_minimal_repo(root)
        (root / TEXTURE_SAMPLER_VERIFIER_INPUT).unlink()
        if not any(
            "missing MLIR verifier input" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: missing verifier input file was accepted")

        evidence_path = write_minimal_repo(root)
        ctest_text = read_text(root / CTEST_PATH).replace(
            "crossgl_source_location_fact_layout_local_size",
            "crossgl_source_location_fact_missing_local_size",
        )
        (root / CTEST_PATH).write_text(ctest_text, encoding="utf-8")
        if not any(
            "missing fact-preservation verifier token" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: CMake verifier missing fact marker was accepted")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root to validate.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Configured build-tree optional-tool evidence JSON to validate.",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    errors = run_self_test() if args.self_test else run_checks(args.root, args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.self_test:
        print("MLIR optional-tool evidence checker self-test passed")
    else:
        print("MLIR optional-tool evidence is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
