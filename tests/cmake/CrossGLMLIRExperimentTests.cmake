set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/MinimalComputeShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_source_file = true"
  "crossgl_source_location_fact_shader_module = true"
  "crossgl_source_location_fact_compute_stage = true"
  "crossgl_source_location_fact_entry_point = true"
  "crossgl_source_location_fact_layout_local_size = true"
  "crossgl_source_location_fact_return_statement = true"
  "crossgl_type_fact_void_entry_point = true"
  "crossgl_resource_count = 0"
  "crossgl_resource_fact_descriptors_empty = true"
  "crossgl_resource_fact_storage_buffers_empty = true"
  "crossgl_resource_fact_storage_images_empty = true"
  "crossgl_resource_fact_textures_empty = true"
  "crossgl_resource_fact_samplers_empty = true"
  "crossgl_target_independent_resource_metadata_empty = true"
  "crossgl_resource_metadata = \"target-independent:none\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/MinimalComputeShader.cgl"
  "crossgl_stage"
  "compute"
  "crossgl_entry_point"
  "crossgl_local_size"
  "1,1,1"
  "crossgl_source_location_fact_source_file"
  "crossgl_source_location_fact_shader_module"
  "crossgl_source_location_fact_compute_stage"
  "crossgl_source_location_fact_entry_point"
  "crossgl_source_location_fact_layout_local_size"
  "crossgl_source_location_fact_return_statement"
  "crossgl_type_fact_void_entry_point"
  "crossgl_resource_count"
  "crossgl_resource_fact_descriptors_empty"
  "crossgl_resource_fact_storage_buffers_empty"
  "crossgl_resource_fact_storage_images_empty"
  "crossgl_resource_fact_textures_empty"
  "crossgl_resource_fact_samplers_empty"
  "crossgl_target_independent_resource_metadata_empty"
  "target-independent:none"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/ScalarExpressionComputeShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_source_file = true"
  "crossgl_source_location_fact_shader_module = true"
  "crossgl_source_location_fact_compute_stage = true"
  "crossgl_source_location_fact_entry_point = true"
  "crossgl_source_location_fact_layout_local_size = true"
  "crossgl_source_location_fact_local_variable_declarations = true"
  "crossgl_source_location_fact_scalar_expression_statements = true"
  "crossgl_source_location_fact_return_statement = true"
  "crossgl_type_fact_void_entry_point = true"
  "crossgl_type_fact_float_scalar = true"
  "crossgl_type_fact_int_scalar = true"
  "crossgl_type_fact_bool_scalar = true"
  "crossgl_type_fact_scalar_literals = true"
  "crossgl_type_fact_constructor_cast_expression = true"
  "crossgl_type_fact_binary_expression_result_types = true"
  "crossgl_type_fact_comparison_expression_result_type = true"
  "crossgl_scalar_local_count = 4"
  "crossgl_scalar_local_0_name = \"base\""
  "crossgl_scalar_local_0_type = \"float\""
  "crossgl_scalar_local_1_name = \"scaled\""
  "crossgl_scalar_local_1_type = \"float\""
  "crossgl_scalar_local_2_name = \"count\""
  "crossgl_scalar_local_2_type = \"int\""
  "crossgl_scalar_local_3_name = \"keep\""
  "crossgl_scalar_local_3_type = \"bool\""
  "crossgl_scalar_expression_count = 4"
  "crossgl_scalar_expression_fact_float_literal = true"
  "crossgl_scalar_expression_fact_int_literal = true"
  "crossgl_scalar_expression_fact_binary_add = true"
  "crossgl_scalar_expression_fact_binary_multiply = true"
  "crossgl_scalar_expression_fact_constructor_cast = true"
  "crossgl_scalar_expression_fact_comparison_greater_than = true"
  "crossgl_scalar_expression_fact_comparison_result_bool = true"
  "crossgl_resource_count = 0"
  "crossgl_resource_fact_descriptors_empty = true"
  "crossgl_resource_fact_storage_buffers_empty = true"
  "crossgl_resource_fact_storage_images_empty = true"
  "crossgl_resource_fact_textures_empty = true"
  "crossgl_resource_fact_samplers_empty = true"
  "crossgl_target_independent_resource_metadata_empty = true"
  "crossgl_resource_metadata = \"target-independent:none\""
  "crossgl_scalar_expression_metadata = \"locals:base:float,scaled:float,count:int,keep:bool;expressions:literal,binary,constructor_cast,comparison\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/ScalarExpressionComputeShader.cgl"
  "crossgl_stage"
  "compute"
  "crossgl_entry_point"
  "crossgl_local_size"
  "1,1,1"
  "crossgl_source_location_fact_local_variable_declarations"
  "crossgl_source_location_fact_scalar_expression_statements"
  "crossgl_type_fact_float_scalar"
  "crossgl_type_fact_int_scalar"
  "crossgl_type_fact_bool_scalar"
  "crossgl_type_fact_scalar_literals"
  "crossgl_type_fact_constructor_cast_expression"
  "crossgl_type_fact_binary_expression_result_types"
  "crossgl_type_fact_comparison_expression_result_type"
  "crossgl_scalar_local_count"
  "crossgl_scalar_local_0_name"
  "base"
  "crossgl_scalar_local_1_name"
  "scaled"
  "crossgl_scalar_local_2_name"
  "count"
  "crossgl_scalar_local_3_name"
  "keep"
  "crossgl_scalar_expression_count"
  "crossgl_scalar_expression_fact_binary_add"
  "crossgl_scalar_expression_fact_binary_multiply"
  "crossgl_scalar_expression_fact_constructor_cast"
  "crossgl_scalar_expression_fact_comparison_greater_than"
  "crossgl_scalar_expression_fact_comparison_result_bool"
  "crossgl_resource_count"
  "crossgl_target_independent_resource_metadata_empty"
  "locals:base:float,scaled:float,count:int,keep:bool"
  "expressions:literal,binary,constructor_cast,comparison"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/StorageBufferComputeShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_source_file = true"
  "crossgl_source_location_fact_shader_module = true"
  "crossgl_source_location_fact_compute_stage = true"
  "crossgl_source_location_fact_entry_point = true"
  "crossgl_source_location_fact_layout_local_size = true"
  "crossgl_source_location_fact_storage_buffer_declaration = true"
  "crossgl_source_location_fact_local_variable_declarations = true"
  "crossgl_source_location_fact_scalar_expression_statements = true"
  "crossgl_source_location_fact_storage_buffer_write = true"
  "crossgl_source_location_fact_return_statement = true"
  "crossgl_type_fact_void_entry_point = true"
  "crossgl_type_fact_float_scalar = true"
  "crossgl_type_fact_float_pointer_storage_buffer = true"
  "crossgl_type_fact_storage_buffer_element_type = true"
  "crossgl_type_fact_binary_expression_result_types = true"
  "crossgl_resource_count = 1"
  "crossgl_descriptor_count = 1"
  "crossgl_descriptor_0_stage = \"compute\""
  "crossgl_descriptor_0_name = \"values\""
  "crossgl_descriptor_0_kind = \"storageBuffer\""
  "crossgl_descriptor_0_set = 0"
  "crossgl_descriptor_0_binding = 0"
  "crossgl_storage_buffer_count = 1"
  "crossgl_storage_buffer_0_name = \"values\""
  "crossgl_storage_buffer_0_type = \"float*\""
  "crossgl_storage_buffer_0_element_type = \"float\""
  "crossgl_storage_buffer_0_address_space = \"storage\""
  "crossgl_storage_buffer_0_write_access = true"
  "crossgl_resource_fact_storage_images_empty = true"
  "crossgl_resource_fact_textures_empty = true"
  "crossgl_resource_fact_samplers_empty = true"
  "crossgl_target_independent_resource_metadata_count = 1"
  "crossgl_target_independent_resource_metadata_0_stage = \"compute\""
  "crossgl_target_independent_resource_metadata_0_name = \"values\""
  "crossgl_target_independent_resource_metadata_0_kind = \"storageBuffer\""
  "crossgl_target_independent_resource_metadata_0_source_type = \"float*\""
  "crossgl_target_independent_resource_metadata_0_element_type = \"float\""
  "crossgl_target_independent_resource_metadata_0_address_space = \"storage\""
  "crossgl_target_independent_resource_metadata_0_access = \"read_write\""
  "crossgl_target_independent_resource_metadata_0_set = 0"
  "crossgl_target_independent_resource_metadata_0_binding = 0"
  "crossgl_target_independent_resource_metadata_0_target_independent = true"
  "crossgl_resource_metadata = \"target-independent:storageBuffer:compute:values:set=0:binding=0:type=float*:element=float:addressSpace=storage:access=read_write\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/StorageBufferComputeShader.cgl"
  "crossgl_stage"
  "compute"
  "crossgl_entry_point"
  "crossgl_local_size"
  "1,1,1"
  "crossgl_source_location_fact_storage_buffer_declaration"
  "crossgl_source_location_fact_storage_buffer_write"
  "crossgl_type_fact_float_pointer_storage_buffer"
  "crossgl_resource_count"
  "crossgl_descriptor_count"
  "crossgl_descriptor_0_name"
  "values"
  "crossgl_descriptor_0_kind"
  "storageBuffer"
  "crossgl_storage_buffer_count"
  "crossgl_storage_buffer_0_type"
  "float*"
  "crossgl_storage_buffer_0_element_type"
  "float"
  "crossgl_storage_buffer_0_address_space"
  "storage"
  "crossgl_storage_buffer_0_write_access"
  "crossgl_target_independent_resource_metadata_count"
  "crossgl_target_independent_resource_metadata_0_access"
  "read_write"
  "target-independent:storageBuffer:compute:values"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/IfComputeShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_source_file = true"
  "crossgl_source_location_fact_shader_module = true"
  "crossgl_source_location_fact_compute_stage = true"
  "crossgl_source_location_fact_entry_point = true"
  "crossgl_source_location_fact_layout_local_size = true"
  "crossgl_source_location_fact_storage_buffer_declaration = true"
  "crossgl_source_location_fact_local_variable_declarations = true"
  "crossgl_source_location_fact_storage_buffer_read = true"
  "crossgl_source_location_fact_if_statement = true"
  "crossgl_source_location_fact_then_block_assignment = true"
  "crossgl_source_location_fact_else_block_assignment = true"
  "crossgl_source_location_fact_storage_buffer_write = true"
  "crossgl_source_location_fact_return_statement = true"
  "crossgl_type_fact_void_entry_point = true"
  "crossgl_type_fact_float_scalar = true"
  "crossgl_type_fact_float_pointer_storage_buffer = true"
  "crossgl_type_fact_storage_buffer_element_type = true"
  "crossgl_type_fact_comparison_expression_result_type = true"
  "crossgl_type_fact_branch_condition_bool = true"
  "crossgl_type_fact_assignment_expression_result_types = true"
  "crossgl_type_fact_unary_expression_result_types = true"
  "crossgl_resource_count = 1"
  "crossgl_descriptor_count = 1"
  "crossgl_descriptor_0_stage = \"compute\""
  "crossgl_descriptor_0_name = \"values\""
  "crossgl_descriptor_0_kind = \"storageBuffer\""
  "crossgl_descriptor_0_set = 0"
  "crossgl_descriptor_0_binding = 0"
  "crossgl_storage_buffer_count = 1"
  "crossgl_storage_buffer_0_name = \"values\""
  "crossgl_storage_buffer_0_type = \"float*\""
  "crossgl_storage_buffer_0_element_type = \"float\""
  "crossgl_storage_buffer_0_address_space = \"storage\""
  "crossgl_storage_buffer_0_read_access = true"
  "crossgl_storage_buffer_0_write_access = true"
  "crossgl_storage_buffer_read_count = 1"
  "crossgl_storage_buffer_read_0_name = \"values\""
  "crossgl_storage_buffer_read_0_index = 0"
  "crossgl_storage_buffer_write_count = 1"
  "crossgl_storage_buffer_write_0_name = \"values\""
  "crossgl_storage_buffer_write_0_index = 1"
  "crossgl_resource_fact_storage_buffer_read = true"
  "crossgl_resource_fact_storage_buffer_write = true"
  "crossgl_resource_fact_storage_images_empty = true"
  "crossgl_resource_fact_textures_empty = true"
  "crossgl_resource_fact_samplers_empty = true"
  "crossgl_target_independent_resource_metadata_count = 1"
  "crossgl_target_independent_resource_metadata_0_stage = \"compute\""
  "crossgl_target_independent_resource_metadata_0_name = \"values\""
  "crossgl_target_independent_resource_metadata_0_kind = \"storageBuffer\""
  "crossgl_target_independent_resource_metadata_0_source_type = \"float*\""
  "crossgl_target_independent_resource_metadata_0_element_type = \"float\""
  "crossgl_target_independent_resource_metadata_0_address_space = \"storage\""
  "crossgl_target_independent_resource_metadata_0_access = \"read_write\""
  "crossgl_target_independent_resource_metadata_0_set = 0"
  "crossgl_target_independent_resource_metadata_0_binding = 0"
  "crossgl_target_independent_resource_metadata_0_target_independent = true"
  "crossgl_control_flow_if_count = 1"
  "crossgl_control_flow_if_0_has_else = true"
  "crossgl_branch_condition_0_expression = \"x > 0.0\""
  "crossgl_branch_condition_0_comparison = \"greater_than\""
  "crossgl_branch_condition_0_result_type = \"bool\""
  "crossgl_branch_local_assignment_count = 2"
  "crossgl_branch_then_0_assignment = \"y = x\""
  "crossgl_branch_else_0_assignment = \"y = -x\""
  "crossgl_branch_return_fact_return_after_if = true"
  "crossgl_resource_metadata = \"target-independent:storageBuffer:compute:values:set=0:binding=0:type=float*:element=float:addressSpace=storage:access=read_write\""
  "crossgl_if_compute_metadata = \"control-flow:structured-if-else,condition:x_gt_zero,then:y=x,else:y=-x,return:after-if,storage-buffer:values[0]->values[1]\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/IfComputeShader.cgl"
  "crossgl_stage"
  "compute"
  "crossgl_entry_point"
  "crossgl_local_size"
  "1,1,1"
  "crossgl_source_location_fact_storage_buffer_read"
  "crossgl_source_location_fact_if_statement"
  "crossgl_source_location_fact_then_block_assignment"
  "crossgl_source_location_fact_else_block_assignment"
  "crossgl_source_location_fact_storage_buffer_write"
  "crossgl_type_fact_branch_condition_bool"
  "crossgl_type_fact_assignment_expression_result_types"
  "crossgl_type_fact_unary_expression_result_types"
  "crossgl_storage_buffer_0_read_access"
  "crossgl_storage_buffer_0_write_access"
  "crossgl_storage_buffer_read_count"
  "crossgl_storage_buffer_read_0_index"
  "crossgl_storage_buffer_write_count"
  "crossgl_storage_buffer_write_0_index"
  "crossgl_resource_fact_storage_buffer_read"
  "crossgl_resource_fact_storage_buffer_write"
  "crossgl_control_flow_if_count"
  "crossgl_control_flow_if_0_has_else"
  "crossgl_branch_condition_0_expression"
  "x > 0.0"
  "crossgl_branch_condition_0_comparison"
  "greater_than"
  "crossgl_branch_condition_0_result_type"
  "bool"
  "crossgl_branch_then_0_assignment"
  "y = x"
  "crossgl_branch_else_0_assignment"
  "y = -x"
  "crossgl_branch_return_fact_return_after_if"
  "control-flow:structured-if-else"
  "storage-buffer:values[0]->values[1]"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/VulkanTextureSamplerLodShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_source_file = true"
  "crossgl_source_location_fact_shader_module = true"
  "crossgl_source_location_fact_compute_stage = true"
  "crossgl_source_location_fact_entry_point = true"
  "crossgl_source_location_fact_layout_local_size = true"
  "crossgl_source_location_fact_storage_buffer_declaration = true"
  "crossgl_source_location_fact_texture_declaration = true"
  "crossgl_source_location_fact_sampler_declaration = true"
  "crossgl_source_location_fact_local_variable_declarations = true"
  "crossgl_source_location_fact_scalar_expression_statements = true"
  "crossgl_source_location_fact_texture_sample_lod = true"
  "crossgl_source_location_fact_storage_buffer_write = true"
  "crossgl_source_location_fact_return_statement = true"
  "crossgl_type_fact_void_entry_point = true"
  "crossgl_type_fact_vec4_scalar = true"
  "crossgl_type_fact_vec4_pointer_storage_buffer = true"
  "crossgl_type_fact_storage_buffer_element_type = true"
  "crossgl_type_fact_texture_sample_result_type = true"
  "crossgl_type_fact_texture_coordinate_type = true"
  "crossgl_type_fact_explicit_lod_scalar = true"
  "crossgl_type_fact_constructor_cast_expression = true"
  "crossgl_type_fact_scalar_literals = true"
  "crossgl_resource_count = 3"
  "crossgl_descriptor_count = 3"
  "crossgl_descriptor_0_stage = \"compute\""
  "crossgl_descriptor_0_name = \"values\""
  "crossgl_descriptor_0_kind = \"storageBuffer\""
  "crossgl_descriptor_0_set = 0"
  "crossgl_descriptor_0_binding = 0"
  "crossgl_descriptor_1_stage = \"compute\""
  "crossgl_descriptor_1_name = \"shadowMap\""
  "crossgl_descriptor_1_kind = \"sampledTexture\""
  "crossgl_descriptor_1_set = 0"
  "crossgl_descriptor_1_binding = 2"
  "crossgl_descriptor_2_stage = \"compute\""
  "crossgl_descriptor_2_name = \"comparisonSampler\""
  "crossgl_descriptor_2_kind = \"sampler\""
  "crossgl_descriptor_2_set = 0"
  "crossgl_descriptor_2_binding = 5"
  "crossgl_storage_buffer_count = 1"
  "crossgl_storage_buffer_0_name = \"values\""
  "crossgl_storage_buffer_0_type = \"vec4*\""
  "crossgl_storage_buffer_0_element_type = \"vec4\""
  "crossgl_storage_buffer_0_address_space = \"storage\""
  "crossgl_storage_buffer_0_write_access = true"
  "crossgl_resource_fact_storage_images_empty = true"
  "crossgl_texture_count = 1"
  "crossgl_texture_0_name = \"shadowMap\""
  "crossgl_texture_0_type = \"sampler2D\""
  "crossgl_texture_0_sampled_type = \"float\""
  "crossgl_texture_0_dimension = \"2d\""
  "crossgl_texture_0_arrayed = false"
  "crossgl_texture_0_comparison = false"
  "crossgl_texture_0_set = 0"
  "crossgl_texture_0_binding = 2"
  "crossgl_sampler_count = 1"
  "crossgl_sampler_0_name = \"comparisonSampler\""
  "crossgl_sampler_0_type = \"sampler\""
  "crossgl_sampler_0_comparison = true"
  "crossgl_sampler_0_set = 0"
  "crossgl_sampler_0_binding = 5"
  "crossgl_texture_sample_lod_count = 1"
  "crossgl_texture_sample_lod_0_texture = \"shadowMap\""
  "crossgl_texture_sample_lod_0_sampler = \"comparisonSampler\""
  "crossgl_texture_sample_lod_0_coordinate_type = \"vec2\""
  "crossgl_texture_sample_lod_0_lod_type = \"float\""
  "crossgl_texture_sample_lod_0_result_type = \"vec4\""
  "crossgl_target_independent_resource_metadata_count = 3"
  "crossgl_target_independent_resource_metadata_0_stage = \"compute\""
  "crossgl_target_independent_resource_metadata_0_name = \"values\""
  "crossgl_target_independent_resource_metadata_0_kind = \"storageBuffer\""
  "crossgl_target_independent_resource_metadata_0_source_type = \"vec4*\""
  "crossgl_target_independent_resource_metadata_0_element_type = \"vec4\""
  "crossgl_target_independent_resource_metadata_0_address_space = \"storage\""
  "crossgl_target_independent_resource_metadata_0_access = \"read_write\""
  "crossgl_target_independent_resource_metadata_0_set = 0"
  "crossgl_target_independent_resource_metadata_0_binding = 0"
  "crossgl_target_independent_resource_metadata_0_target_independent = true"
  "crossgl_target_independent_resource_metadata_1_stage = \"compute\""
  "crossgl_target_independent_resource_metadata_1_name = \"shadowMap\""
  "crossgl_target_independent_resource_metadata_1_kind = \"sampledTexture\""
  "crossgl_target_independent_resource_metadata_1_source_type = \"sampler2D\""
  "crossgl_target_independent_resource_metadata_1_element_type = \"float\""
  "crossgl_target_independent_resource_metadata_1_address_space = \"uniform_constant\""
  "crossgl_target_independent_resource_metadata_1_access = \"read\""
  "crossgl_target_independent_resource_metadata_1_set = 0"
  "crossgl_target_independent_resource_metadata_1_binding = 2"
  "crossgl_target_independent_resource_metadata_1_target_independent = true"
  "crossgl_target_independent_resource_metadata_2_stage = \"compute\""
  "crossgl_target_independent_resource_metadata_2_name = \"comparisonSampler\""
  "crossgl_target_independent_resource_metadata_2_kind = \"sampler\""
  "crossgl_target_independent_resource_metadata_2_source_type = \"sampler\""
  "crossgl_target_independent_resource_metadata_2_element_type = \"sampler\""
  "crossgl_target_independent_resource_metadata_2_address_space = \"uniform_constant\""
  "crossgl_target_independent_resource_metadata_2_access = \"read\""
  "crossgl_target_independent_resource_metadata_2_set = 0"
  "crossgl_target_independent_resource_metadata_2_binding = 5"
  "crossgl_target_independent_resource_metadata_2_target_independent = true"
  "crossgl_resource_metadata = \"target-independent:storageBuffer:compute:values:set=0:binding=0:type=vec4*:element=vec4:addressSpace=storage:access=read_write;target-independent:sampledTexture:compute:shadowMap:set=0:binding=2:type=sampler2D:element=float:addressSpace=uniform_constant:access=read;target-independent:sampler:compute:comparisonSampler:set=0:binding=5:type=sampler:element=sampler:addressSpace=uniform_constant:access=read\""
  "crossgl_texture_sampler_metadata = \"texture-lod:shadowMap+comparisonSampler:coord=vec2:lod=float:result=vec4\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/VulkanTextureSamplerLodShader.cgl"
  "crossgl_stage"
  "compute"
  "crossgl_entry_point"
  "crossgl_local_size"
  "1,1,1"
  "crossgl_source_location_fact_texture_declaration"
  "crossgl_source_location_fact_sampler_declaration"
  "crossgl_source_location_fact_texture_sample_lod"
  "crossgl_type_fact_vec4_scalar"
  "crossgl_type_fact_vec4_pointer_storage_buffer"
  "crossgl_type_fact_texture_sample_result_type"
  "crossgl_type_fact_texture_coordinate_type"
  "crossgl_type_fact_explicit_lod_scalar"
  "crossgl_resource_count"
  "crossgl_descriptor_count"
  "crossgl_descriptor_1_name"
  "shadowMap"
  "crossgl_descriptor_1_kind"
  "sampledTexture"
  "crossgl_descriptor_2_name"
  "comparisonSampler"
  "crossgl_descriptor_2_kind"
  "sampler"
  "crossgl_texture_count"
  "crossgl_texture_0_type"
  "sampler2D"
  "crossgl_texture_0_dimension"
  "2d"
  "crossgl_sampler_count"
  "crossgl_sampler_0_comparison"
  "crossgl_texture_sample_lod_count"
  "crossgl_texture_sample_lod_0_coordinate_type"
  "vec2"
  "crossgl_texture_sample_lod_0_lod_type"
  "float"
  "crossgl_texture_sample_lod_0_result_type"
  "vec4"
  "crossgl_target_independent_resource_metadata_count"
  "crossgl_target_independent_resource_metadata_1_kind"
  "sampledTexture"
  "crossgl_target_independent_resource_metadata_2_kind"
  "sampler"
  "target-independent:sampledTexture:compute:shadowMap"
  "target-independent:sampler:compute:comparisonSampler"
  "texture-lod:shadowMap+comparisonSampler"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/StorageBufferStructArrayFieldDescriptorArrayShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_storage_buffer_read = true"
  "crossgl_source_location_fact_storage_buffer_write = true"
  "crossgl_type_fact_storage_buffer_element_type = true"
  "crossgl_descriptor_0_name = \"particles\""
  "crossgl_descriptor_0_descriptor_array = true"
  "crossgl_descriptor_0_array_size = 2"
  "crossgl_descriptor_0_fixed_descriptor_indices = \"0,1\""
  "crossgl_storage_buffer_0_type = \"Particle*[2]\""
  "crossgl_storage_buffer_0_descriptor_array = true"
  "crossgl_target_independent_resource_metadata_0_descriptor_array = true"
  "crossgl_descriptor_array_metadata = \"descriptor-array:storageBuffer:particles:size=2:indexing=fixed-literal:indices=0,1\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/StorageBufferStructArrayFieldDescriptorArrayShader.cgl"
  "crossgl_descriptor_0_descriptor_array"
  "crossgl_descriptor_0_array_size"
  "crossgl_storage_buffer_0_type"
  "Particle*[2]"
  "crossgl_storage_buffer_0_fixed_descriptor_indices"
  "0,1"
  "descriptor-array:storageBuffer:particles"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/VulkanTextureSamplerCubeArrayLodShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_texture_declaration = true"
  "crossgl_source_location_fact_sampler_declaration = true"
  "crossgl_source_location_fact_texture_sample_lod = true"
  "crossgl_descriptor_1_name = \"skyMaps\""
  "crossgl_descriptor_1_descriptor_array = true"
  "crossgl_descriptor_2_name = \"skySamplers\""
  "crossgl_descriptor_2_descriptor_array = true"
  "crossgl_texture_0_type = \"samplerCube[2]\""
  "crossgl_sampler_0_type = \"sampler[2]\""
  "crossgl_texture_sample_lod_0_coordinate_type = \"vec3\""
  "crossgl_texture_sampler_metadata = \"texture-lod:skyMaps+skySamplers:coord=vec3:lod=float:result=vec4:descriptorArray=true\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/VulkanTextureSamplerCubeArrayLodShader.cgl"
  "crossgl_descriptor_1_descriptor_array"
  "crossgl_descriptor_2_descriptor_array"
  "crossgl_texture_0_type"
  "samplerCube[2]"
  "crossgl_sampler_0_type"
  "sampler[2]"
  "crossgl_texture_sample_lod_0_coordinate_type"
  "vec3"
  "texture-lod:skyMaps+skySamplers"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/frontend/fixtures/StorageImageHIRShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"8,8,1\""
  "crossgl_source_location_fact_storage_image_declaration = true"
  "crossgl_source_location_fact_storage_image_load = true"
  "crossgl_source_location_fact_storage_image_store = true"
  "crossgl_type_fact_storage_image_result_type = true"
  "crossgl_type_fact_storage_image_coordinate_type = true"
  "crossgl_storage_image_count = 6"
  "crossgl_storage_image_0_name = \"colorImage\""
  "crossgl_storage_image_0_format = \"rgba32f\""
  "crossgl_storage_image_2_format = \"rgba32i\""
  "crossgl_storage_image_4_format = \"rgba32ui\""
  "crossgl_storage_image_load_count = 6"
  "crossgl_storage_image_store_count = 6"
  "crossgl_storage_image_metadata = \"storage-image:load-store:2d-and-2d-array:float-int-uint\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/frontend/fixtures/StorageImageHIRShader.cgl"
  "crossgl_source_location_fact_storage_image_load"
  "crossgl_source_location_fact_storage_image_store"
  "crossgl_storage_image_count"
  "crossgl_storage_image_0_name"
  "colorImage"
  "crossgl_storage_image_2_format"
  "rgba32i"
  "crossgl_storage_image_4_format"
  "rgba32ui"
  "storage-image:load-store"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/frontend/fixtures/StorageImageDescriptorArrayHIRShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"8,8,1\""
  "crossgl_source_location_fact_storage_image_load = true"
  "crossgl_source_location_fact_storage_image_store = true"
  "crossgl_storage_image_0_name = \"colorImages\""
  "crossgl_storage_image_0_descriptor_array = true"
  "crossgl_storage_image_0_fixed_descriptor_indices = \"0\""
  "crossgl_storage_image_1_name = \"labelAtlases\""
  "crossgl_storage_image_1_descriptor_array = true"
  "crossgl_storage_image_1_fixed_descriptor_indices = \"1\""
  "crossgl_descriptor_array_metadata = \"descriptor-array:storageImage:colorImages:size=2:indexing=fixed-literal:indices=0;descriptor-array:storageImage:labelAtlases:size=2:indexing=fixed-literal:indices=1\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/frontend/fixtures/StorageImageDescriptorArrayHIRShader.cgl"
  "crossgl_storage_image_0_descriptor_array"
  "crossgl_storage_image_0_fixed_descriptor_indices"
  "crossgl_storage_image_1_descriptor_array"
  "crossgl_storage_image_1_fixed_descriptor_indices"
  "descriptor-array:storageImage:colorImages"
  "descriptor-array:storageImage:labelAtlases"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/frontend/fixtures/StorageImageNonUniformDescriptorArrayHIRShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"8,8,1\""
  "crossgl_source_location_fact_nonuniform_descriptor_index = true"
  "crossgl_storage_image_0_indexing_mode = \"nonuniform-marker\""
  "crossgl_storage_image_0_index_expression = \"slot\""
  "crossgl_storage_image_0_nonuniform_marker = true"
  "crossgl_storage_image_1_indexing_mode = \"nonuniform-marker\""
  "crossgl_storage_image_1_nonuniform_marker = true"
  "crossgl_target_independent_resource_metadata_1_index_expression = \"slot\""
  "crossgl_descriptor_array_metadata = \"descriptor-array:storageImage:nonuniform-marker:slot\""
  "crossgl_nonuniform_metadata = \"nonuniform-descriptor-index:storageImage:slot\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/frontend/fixtures/StorageImageNonUniformDescriptorArrayHIRShader.cgl"
  "crossgl_source_location_fact_nonuniform_descriptor_index"
  "crossgl_storage_image_0_indexing_mode"
  "nonuniform-marker"
  "crossgl_storage_image_0_nonuniform_marker"
  "crossgl_target_independent_resource_metadata_1_index_expression"
  "slot"
  "nonuniform-descriptor-index:storageImage:slot"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/frontend/fixtures/StorageImageAccessQualifierHIRShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_storage_image_load = true"
  "crossgl_source_location_fact_storage_image_store = true"
  "crossgl_storage_image_0_access = \"read\""
  "crossgl_storage_image_1_access = \"write\""
  "crossgl_storage_image_2_access = \"read_write\""
  "crossgl_storage_image_3_access = \"read\""
  "crossgl_access_qualifier_metadata = \"storage-image-access:read,write,read_write\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/frontend/fixtures/StorageImageAccessQualifierHIRShader.cgl"
  "crossgl_storage_image_0_access"
  "read"
  "crossgl_storage_image_1_access"
  "write"
  "crossgl_storage_image_2_access"
  "read_write"
  "storage-image-access:read,write,read_write"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/StorageImageExplicitFormatShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"2,2,1\""
  "crossgl_storage_image_0_format = \"r32f\""
  "crossgl_storage_image_1_format = \"r32i\""
  "crossgl_storage_image_2_format = \"r32ui\""
  "crossgl_storage_image_3_format = \"r32ui\""
  "crossgl_storage_image_0_access = \"read\""
  "crossgl_storage_image_3_access = \"write\""
  "crossgl_explicit_format_metadata = \"storage-image-format:r32f,r32i,r32ui\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/StorageImageExplicitFormatShader.cgl"
  "crossgl_storage_image_0_format"
  "r32f"
  "crossgl_storage_image_1_format"
  "r32i"
  "crossgl_storage_image_2_format"
  "r32ui"
  "storage-image-format:r32f,r32i,r32ui"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/StorageImageAtomicShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"4,4,2\""
  "crossgl_source_location_fact_storage_image_atomic_add = true"
  "crossgl_source_location_fact_storage_image_atomic_min = true"
  "crossgl_source_location_fact_storage_image_atomic_max = true"
  "crossgl_source_location_fact_storage_image_atomic_and = true"
  "crossgl_source_location_fact_storage_image_atomic_or = true"
  "crossgl_source_location_fact_storage_image_atomic_exchange = true"
  "crossgl_source_location_fact_storage_image_atomic_xor = true"
  "crossgl_type_fact_storage_image_atomic_int_result_type = true"
  "crossgl_type_fact_storage_image_atomic_uint_result_type = true"
  "crossgl_storage_image_atomic_add_count = 3"
  "crossgl_storage_image_atomic_exchange_count = 3"
  "crossgl_storage_image_atomic_xor_count = 2"
  "crossgl_storage_image_atomic_metadata = \"atomic:add,min,max,and,or,exchange,xor:int,uint\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/StorageImageAtomicShader.cgl"
  "crossgl_source_location_fact_storage_image_atomic_add"
  "crossgl_source_location_fact_storage_image_atomic_exchange"
  "crossgl_storage_image_atomic_add_count"
  "crossgl_storage_image_atomic_xor_count"
  "atomic:add,min,max,and,or,exchange,xor:int,uint"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/frontend/fixtures/GraphicsProvenanceHIRShader.cgl\""
  "crossgl_stage = \"graphics\""
  "crossgl_entry_point = \"main\""
  "crossgl_source_location_fact_vertex_stage = true"
  "crossgl_source_location_fact_fragment_stage = true"
  "crossgl_source_location_fact_vertex_entry_point = true"
  "crossgl_source_location_fact_fragment_entry_point = true"
  "crossgl_type_fact_vertex_entry_point_io_structs = true"
  "crossgl_type_fact_fragment_entry_point_io_structs = true"
  "crossgl_debug_metadata_schema_version = 11"
  "crossgl_hir_source_map_schema_version = 7"
  "crossgl_source_map_debug_preservation = true"
  "crossgl_graphics_provenance_metadata = \"vertex:VertexInput->VertexOutput:position+varyings;fragment:FragmentInput->FragmentOutput:color\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/frontend/fixtures/GraphicsProvenanceHIRShader.cgl"
  "crossgl_stage"
  "graphics"
  "crossgl_source_location_fact_vertex_stage"
  "crossgl_source_location_fact_fragment_stage"
  "crossgl_type_fact_vertex_entry_point_io_structs"
  "crossgl_type_fact_fragment_output_vec4"
  "crossgl_source_map_debug_preservation"
  "graphics:vertex+fragment"
  "crossgl_real_mlir_smoke")

if(DEFINED CROSSGL_MLIR_EXPERIMENT_VERIFY_SCRIPT)
  foreach(required_var IN ITEMS
      MLIR_OPT
      INPUT_MLIR
      BUILD_DIR
      EXPERIMENT_TARGET
      REQUIRED_MARKERS_VAR
      OUTPUT_MARKERS_VAR)
    if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier missing ${required_var}")
    endif()
  endforeach()
  foreach(marker_var IN ITEMS REQUIRED_MARKERS_VAR OUTPUT_MARKERS_VAR)
    if(NOT DEFINED ${${marker_var}})
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier marker list ${${marker_var}} missing")
    endif()
  endforeach()

  if(NOT EXISTS "${INPUT_MLIR}")
    message(FATAL_ERROR
      "CrossGL MLIR experiment verifier input missing: ${INPUT_MLIR}")
  endif()
  file(READ "${INPUT_MLIR}" input_mlir)
  foreach(required_marker IN LISTS ${REQUIRED_MARKERS_VAR})
    string(FIND "${input_mlir}" "${required_marker}" marker_index)
    if(marker_index EQUAL -1)
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier input ${INPUT_MLIR} is missing "
        "required real-MLIR fact-preservation marker ${required_marker}")
    endif()
  endforeach()
  foreach(forbidden_marker IN ITEMS
      "CrossGL pseudo-MLIR"
      "crossgl.real_mlir = \"false\""
      "not a registered MLIR dialect")
    string(FIND "${input_mlir}" "${forbidden_marker}" marker_index)
    if(NOT marker_index EQUAL -1)
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier input ${INPUT_MLIR} contains "
        "pseudo-MLIR marker ${forbidden_marker}")
    endif()
  endforeach()

  set(build_command
    "${CMAKE_COMMAND}"
    --build "${BUILD_DIR}"
    --target "${EXPERIMENT_TARGET}")
  if(DEFINED BUILD_CONFIG AND NOT "${BUILD_CONFIG}" STREQUAL "")
    list(APPEND build_command --config "${BUILD_CONFIG}")
  endif()
  execute_process(
    COMMAND ${build_command}
    RESULT_VARIABLE build_result
    OUTPUT_VARIABLE build_output
    ERROR_VARIABLE build_error)
  if(NOT build_result EQUAL 0)
    message(FATAL_ERROR
      "failed to build ${EXPERIMENT_TARGET}; stdout: ${build_output}; "
      "stderr: ${build_error}")
  endif()

  execute_process(
    COMMAND "${MLIR_OPT}" --verify-diagnostics "${INPUT_MLIR}"
    RESULT_VARIABLE mlir_result
    OUTPUT_VARIABLE mlir_output
    ERROR_VARIABLE mlir_error)
  if(NOT mlir_result EQUAL 0)
    message(FATAL_ERROR
      "mlir-opt verifier failed for ${INPUT_MLIR}; stdout: ${mlir_output}; "
      "stderr: ${mlir_error}")
  endif()
  foreach(output_marker IN LISTS ${OUTPUT_MARKERS_VAR})
    string(FIND "${mlir_output}" "${output_marker}" marker_index)
    if(marker_index EQUAL -1)
      message(FATAL_ERROR
        "mlir-opt output did not preserve real-MLIR fact-preservation "
        "marker ${output_marker}; stdout: ${mlir_output}; stderr: ${mlir_error}")
    endif()
  endforeach()

  message(STATUS
    "CrossGL MLIR experiment verifier passed for ${INPUT_MLIR}")
  return()
endif()

function(crossgl_mlir_json_string out value)
  string(REPLACE "\\" "\\\\" escaped "${value}")
  string(REPLACE "\"" "\\\"" escaped "${escaped}")
  string(REPLACE "\n" "\\n" escaped "${escaped}")
  set(${out} "\"${escaped}\"" PARENT_SCOPE)
endfunction()

function(crossgl_mlir_json_string_or_null out value)
  if("${value}" STREQUAL "")
    set(${out} "null" PARENT_SCOPE)
  else()
    crossgl_mlir_json_string(json_value "${value}")
    set(${out} "${json_value}" PARENT_SCOPE)
  endif()
endfunction()

function(crossgl_mlir_json_bool out value)
  if(value)
    set(${out} "true" PARENT_SCOPE)
  else()
    set(${out} "false" PARENT_SCOPE)
  endif()
endfunction()

function(crossgl_mlir_json_string_list out)
  set(json "[")
  set(separator "")
  foreach(value IN LISTS ARGN)
    crossgl_mlir_json_string(json_value "${value}")
    string(APPEND json "${separator}${json_value}")
    set(separator ", ")
  endforeach()
  string(APPEND json "]")
  set(${out} "${json}" PARENT_SCOPE)
endfunction()

set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_FIXTURE
  "tests/fixtures/MinimalComputeShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/minimal_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST
  "cglc_mlir_experiment_minimal_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_FIXTURE
  "tests/fixtures/ScalarExpressionComputeShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/scalar_expression_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_TEST
  "cglc_mlir_experiment_scalar_expression_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_FIXTURE
  "tests/fixtures/StorageBufferComputeShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_buffer_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_TEST
  "cglc_mlir_experiment_storage_buffer_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_FIXTURE
  "tests/fixtures/IfComputeShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/if_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_TEST
  "cglc_mlir_experiment_if_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_FIXTURE
  "tests/fixtures/VulkanTextureSamplerLodShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/texture_sampler_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_TEST
  "cglc_mlir_experiment_texture_sampler_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_FIXTURE
  "tests/fixtures/StorageBufferStructArrayFieldDescriptorArrayShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_buffer_descriptor_array_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_TEST
  "cglc_mlir_experiment_storage_buffer_descriptor_array_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_FIXTURE
  "tests/fixtures/VulkanTextureSamplerCubeArrayLodShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/texture_sampler_cube_array_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_TEST
  "cglc_mlir_experiment_texture_sampler_cube_array_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_FIXTURE
  "tests/frontend/fixtures/StorageImageHIRShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_image_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_TEST
  "cglc_mlir_experiment_storage_image_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_FIXTURE
  "tests/frontend/fixtures/StorageImageDescriptorArrayHIRShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_image_descriptor_array_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_TEST
  "cglc_mlir_experiment_storage_image_descriptor_array_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_FIXTURE
  "tests/frontend/fixtures/StorageImageNonUniformDescriptorArrayHIRShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_image_nonuniform_descriptor_array_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_TEST
  "cglc_mlir_experiment_storage_image_nonuniform_descriptor_array_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_FIXTURE
  "tests/frontend/fixtures/StorageImageAccessQualifierHIRShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_image_access_qualifier_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_TEST
  "cglc_mlir_experiment_storage_image_access_qualifier_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_FIXTURE
  "tests/fixtures/StorageImageExplicitFormatShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_image_explicit_format_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_TEST
  "cglc_mlir_experiment_storage_image_explicit_format_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_FIXTURE
  "tests/fixtures/StorageImageAtomicShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_image_atomic_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_TEST
  "cglc_mlir_experiment_storage_image_atomic_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_FIXTURE
  "tests/frontend/fixtures/GraphicsProvenanceHIRShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/graphics_provenance_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_TEST
  "cglc_mlir_experiment_graphics_provenance_verifier")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS
  "minimal_compute|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS|minimal compute"
  "scalar_expression_compute|${CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_SCALAR_EXPRESSION_VERIFY_OUTPUT_MARKERS|scalar-expression compute"
  "storage_buffer_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_OUTPUT_MARKERS|storage-buffer compute"
  "if_compute|${CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_IF_COMPUTE_VERIFY_OUTPUT_MARKERS|if-compute"
  "texture_sampler_compute|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_VERIFY_OUTPUT_MARKERS|texture-sampler compute"
  "storage_buffer_descriptor_array_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_VERIFY_OUTPUT_MARKERS|storage-buffer descriptor-array compute"
  "texture_sampler_cube_array_compute|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_TEXTURE_SAMPLER_CUBE_ARRAY_VERIFY_OUTPUT_MARKERS|texture-sampler cube-array compute"
  "storage_image_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_VERIFY_OUTPUT_MARKERS|storage-image compute"
  "storage_image_descriptor_array_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_DESCRIPTOR_ARRAY_VERIFY_OUTPUT_MARKERS|storage-image descriptor-array compute"
  "storage_image_nonuniform_descriptor_array_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_VERIFY_OUTPUT_MARKERS|storage-image nonuniform descriptor-array compute"
  "storage_image_access_qualifier_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ACCESS_QUALIFIER_VERIFY_OUTPUT_MARKERS|storage-image access-qualifier compute"
  "storage_image_explicit_format_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_EXPLICIT_FORMAT_VERIFY_OUTPUT_MARKERS|storage-image explicit-format compute"
  "storage_image_atomic_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_IMAGE_ATOMIC_VERIFY_OUTPUT_MARKERS|storage-image atomic compute"
  "graphics_provenance|${CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_GRAPHICS_PROVENANCE_VERIFY_OUTPUT_MARKERS|graphics provenance")
set(CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE
  "${CMAKE_CURRENT_BINARY_DIR}/mlir/optional_tool_evidence.v0.json")
set(CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_fixture_parity_report.py")
set(CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_package_sidecar_boundary.py")
set(CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_optional_tool_evidence.py")
set(CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_textual_dialect_projection.py")
set(CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_op_type_catalog.py")
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG
  "experimental/mlir/source_resource_catalog.v0.json")
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_CHECKER
  "tools/check_mlir_source_resource_catalog.py")
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_CHECKER}")
set(CROSSGL_MLIR_SOURCE_RESOURCE_PRESERVATION_SECTION
  "sourceResourceEntrypointPreservation")
set(CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TESTS
  cglc_mlir_fixture_parity_report_compile
  cglc_mlir_fixture_parity_report
  cglc_mlir_fixture_parity_report_self_test)
set(CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TESTS
  cglc_mlir_fixture_hir_dump_parity)
set(CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TESTS
  cglc_mlir_package_sidecar_boundary_compile
  cglc_mlir_package_sidecar_boundary
  cglc_mlir_package_sidecar_boundary_self_test)
set(CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TESTS
  cglc_mlir_optional_tool_evidence_compile
  cglc_mlir_optional_tool_evidence
  cglc_mlir_optional_tool_evidence_self_test)
set(CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TESTS
  cglc_mlir_textual_dialect_projection_compile
  cglc_mlir_textual_dialect_projection
  cglc_mlir_textual_dialect_projection_self_test)
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TESTS
  cglc_mlir_source_resource_catalog_compile
  cglc_mlir_source_resource_catalog
  cglc_mlir_source_resource_catalog_self_test)
set(CROSSGL_MLIR_OP_TYPE_CATALOG_TESTS
  cglc_mlir_op_type_catalog_compile
  cglc_mlir_op_type_catalog
  cglc_mlir_op_type_catalog_self_test)

if(CROSSGL_PYTHON3)
  add_test(NAME cglc_mlir_fixture_parity_report_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}")
  add_test(NAME cglc_mlir_fixture_parity_report
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_fixture_parity_report_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_fixture_hir_dump_parity
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}"
      --cglc $<TARGET_FILE:cglc>
      --hir-dump-parity)
  add_test(NAME cglc_mlir_package_sidecar_boundary_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT}")
  add_test(NAME cglc_mlir_package_sidecar_boundary
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}"
      --cglc $<TARGET_FILE:cglc>)
  add_test(NAME cglc_mlir_package_sidecar_boundary_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_optional_tool_evidence_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT}")
  add_test(NAME cglc_mlir_optional_tool_evidence
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}"
      --evidence "${CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}")
  add_test(NAME cglc_mlir_optional_tool_evidence_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_textual_dialect_projection_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT}")
  add_test(NAME cglc_mlir_textual_dialect_projection
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_textual_dialect_projection_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_source_resource_catalog_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT}")
  add_test(NAME cglc_mlir_source_resource_catalog
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_source_resource_catalog_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_op_type_catalog_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT}")
  add_test(NAME cglc_mlir_op_type_catalog
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_op_type_catalog_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT}"
      --self-test)
  set_tests_properties(${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;hir-parity"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-tool-evidence"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-textual-dialect-projection"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-source-resource-catalog"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_OP_TYPE_CATALOG_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-op-type-catalog"
    PROCESSORS 1)
else()
  foreach(CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TEST IN LISTS
      CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TESTS)
    add_test(NAME "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR fixture parity report requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TEST IN LISTS
      CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TESTS)
    add_test(NAME "${CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR fixture HIR dump parity requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;hir-parity;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TEST IN LISTS
      CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TESTS)
    add_test(NAME "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR package sidecar boundary requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TEST IN LISTS
      CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TESTS)
    add_test(NAME "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR optional-tool evidence requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TEST IN LISTS
      CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TESTS)
    add_test(NAME "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR textual dialect projection requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TEST IN LISTS
      CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TESTS)
    add_test(NAME "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR source/resource catalog requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_OP_TYPE_CATALOG_TEST IN LISTS
      CROSSGL_MLIR_OP_TYPE_CATALOG_TESTS)
    add_test(NAME "${CROSSGL_MLIR_OP_TYPE_CATALOG_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR op/type catalog requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_OP_TYPE_CATALOG_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
endif()

set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS "")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_FOUND FALSE)
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_PATH "")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIND_PROGRAM_ATTEMPTED FALSE)
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_VERSION_PROBE_ATTEMPTED FALSE)
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
  "not-run-toolchain-incomplete")
if(NOT CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
  list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "default-off")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF; real MLIR verifier disabled by default")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
    "not-run-default-off")
else()
  if(NOT MLIR_FOUND)
    list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
      "MLIR_FOUND=FALSE")
  endif()
  if(NOT TARGET crossgl_mlir_experiment)
    list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
      "target crossgl_mlir_experiment not created")
  endif()
  foreach(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD IN LISTS
      CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS)
    string(REPLACE "|" ";" CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS
      "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD}")
    list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 2
      CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE)
    list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 3
      CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE)
    list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 4
      CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT)
    if(NOT EXISTS
        "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE}")
      list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
        "${CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE} fixture missing")
    endif()
    if(NOT EXISTS "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT}")
      list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
        "real MLIR verifier input missing: ${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}")
    endif()
  endforeach()

  if(NOT CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS)
    set(CROSSGL_MLIR_OPT_HINTS "")
    set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIND_PROGRAM_ATTEMPTED TRUE)
    foreach(CROSSGL_MLIR_OPT_HINT_VAR IN ITEMS MLIR_TOOLS_DIR LLVM_TOOLS_BINARY_DIR)
      if(DEFINED ${CROSSGL_MLIR_OPT_HINT_VAR}
          AND NOT "${${CROSSGL_MLIR_OPT_HINT_VAR}}" STREQUAL "")
        list(APPEND CROSSGL_MLIR_OPT_HINTS
          "${${CROSSGL_MLIR_OPT_HINT_VAR}}")
      endif()
    endforeach()
    if(CROSSGL_MLIR_OPT_HINTS)
      find_program(CROSSGL_MLIR_OPT
        NAMES mlir-opt
        HINTS ${CROSSGL_MLIR_OPT_HINTS}
        NO_CACHE
        DOC "MLIR optimizer/verifier used by optional CrossGL MLIR experiment tests")
    else()
      find_program(CROSSGL_MLIR_OPT
        NAMES mlir-opt
        NO_CACHE
        DOC "MLIR optimizer/verifier used by optional CrossGL MLIR experiment tests")
    endif()
    if(CROSSGL_MLIR_OPT)
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_FOUND TRUE)
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_PATH "${CROSSGL_MLIR_OPT}")
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_VERSION_PROBE_ATTEMPTED TRUE)
      execute_process(
        COMMAND "${CROSSGL_MLIR_OPT}" --version
        RESULT_VARIABLE CROSSGL_MLIR_OPT_VERSION_RESULT
        OUTPUT_VARIABLE CROSSGL_MLIR_OPT_VERSION_OUTPUT
        ERROR_VARIABLE CROSSGL_MLIR_OPT_VERSION_ERROR)
      if(CROSSGL_MLIR_OPT_VERSION_RESULT EQUAL 0)
        string(STRIP "${CROSSGL_MLIR_OPT_VERSION_OUTPUT}"
          CROSSGL_MLIR_OPT_VERSION_OUTPUT)
        set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "toolchain-available")
        set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
          "available")
      else()
        set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
          "probe-failed")
        list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
          "mlir-opt --version probe failed")
      endif()
    else()
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS "not-found")
      list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
        "mlir-opt not found")
    endif()
  endif()

  if(CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS)
    string(REPLACE ";" ", " CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON
      "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS}")
    set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "toolchain-unavailable")
  endif()
endif()

set(CROSSGL_MLIR_EXPERIMENT_TARGET_CREATED FALSE)
if(TARGET crossgl_mlir_experiment)
  set(CROSSGL_MLIR_EXPERIMENT_TARGET_CREATED TRUE)
endif()
set(CROSSGL_MLIR_EXPERIMENT_OPTION_DEFAULT "OFF")
if(CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
  set(CROSSGL_MLIR_EXPERIMENT_OPTION_ACTUAL "ON")
else()
  set(CROSSGL_MLIR_EXPERIMENT_OPTION_ACTUAL "OFF")
endif()
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_PRESENT FALSE)
if(EXISTS "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT}")
  set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_PRESENT TRUE)
endif()
if(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS STREQUAL "toolchain-available")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGISTERED FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGEX "")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
    "[\"mlir\", \"optional-mlir\", \"mlir-tool-available\"]")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_EVIDENCE_REASON "")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATION_MODE "executable")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INVOKES_MLIR_OPT TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_USES_VERIFY_DIAGNOSTICS TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILDS_TARGET TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILD_TARGET
    "crossgl_mlir_experiment")
else()
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGISTERED TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGEX "^SKIP:")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
    "[\"mlir\", \"optional-mlir\", \"mlir-tool-unavailable\"]")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_EVIDENCE_REASON
    "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON}")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATION_MODE "skipped")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INVOKES_MLIR_OPT FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_USES_VERIFY_DIAGNOSTICS FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILDS_TARGET FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILD_TARGET "")
endif()
crossgl_mlir_json_bool(CROSSGL_MLIR_OPTION_ENABLED_JSON
  "${CROSSGL_ENABLE_MLIR_EXPERIMENTAL}")
crossgl_mlir_json_bool(CROSSGL_MLIR_FOUND_JSON "${MLIR_FOUND}")
crossgl_mlir_json_bool(CROSSGL_MLIR_TARGET_CREATED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_TARGET_CREATED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_VERIFY_INPUT_PRESENT_JSON
  "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_PRESENT}")
crossgl_mlir_json_bool(CROSSGL_MLIR_TOOL_FOUND_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_FOUND}")
crossgl_mlir_json_bool(CROSSGL_MLIR_SKIP_REGISTERED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGISTERED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_FIND_PROGRAM_ATTEMPTED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIND_PROGRAM_ATTEMPTED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_VERSION_PROBE_ATTEMPTED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_VERSION_PROBE_ATTEMPTED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_REGISTRATION_INVOKES_MLIR_OPT_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_INVOKES_MLIR_OPT}")
crossgl_mlir_json_bool(CROSSGL_MLIR_REGISTRATION_USES_VERIFY_DIAGNOSTICS_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_USES_VERIFY_DIAGNOSTICS}")
crossgl_mlir_json_bool(CROSSGL_MLIR_REGISTRATION_BUILDS_TARGET_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILDS_TARGET}")
crossgl_mlir_json_string(CROSSGL_MLIR_OPTION_DEFAULT_JSON
  "${CROSSGL_MLIR_EXPERIMENT_OPTION_DEFAULT}")
crossgl_mlir_json_string(CROSSGL_MLIR_OPTION_ACTUAL_JSON
  "${CROSSGL_MLIR_EXPERIMENT_OPTION_ACTUAL}")
crossgl_mlir_json_string(CROSSGL_MLIR_STATUS_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS}")
crossgl_mlir_json_string(CROSSGL_MLIR_TOOL_DISCOVERY_STATUS_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS}")
crossgl_mlir_json_string(CROSSGL_MLIR_REGISTRATION_MODE_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATION_MODE}")
crossgl_mlir_json_string_or_null(CROSSGL_MLIR_TOOL_PATH_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_PATH}")
crossgl_mlir_json_string_or_null(CROSSGL_MLIR_REGISTRATION_BUILD_TARGET_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILD_TARGET}")
crossgl_mlir_json_string(CROSSGL_MLIR_SKIP_REASON_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_EVIDENCE_REASON}")
crossgl_mlir_json_string(CROSSGL_MLIR_SKIP_REGEX_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGEX}")
crossgl_mlir_json_string_list(CROSSGL_MLIR_MISSING_REASONS_JSON
  ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS})
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS_JSON "")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATIONS_JSON "")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_JSON_SEPARATOR "")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_CTESTS "")
set(CROSSGL_MLIR_EXPERIMENT_REQUIRED_GATE_FACTS
  "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON"
  "MLIR_FOUND=TRUE"
  "target crossgl_mlir_experiment")
foreach(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD IN LISTS
    CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS)
  string(REPLACE "|" ";" CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS
    "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD}")
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 0
    CROSSGL_MLIR_EXPERIMENT_RECORD_KEY)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 1
    CROSSGL_MLIR_EXPERIMENT_RECORD_TEST)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 2
    CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 3
    CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 4
    CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT)

  set(CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_PRESENT FALSE)
  if(EXISTS "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT}")
    set(CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_PRESENT TRUE)
  endif()
  crossgl_mlir_json_bool(CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_PRESENT_JSON
    "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_PRESENT}")
  if(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS STREQUAL "toolchain-available")
    crossgl_mlir_json_string_list(
      CROSSGL_MLIR_EXPERIMENT_RECORD_REQUIRED_FILES_JSON
      "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}")
  else()
    crossgl_mlir_json_string_list(
      CROSSGL_MLIR_EXPERIMENT_RECORD_REQUIRED_FILES_JSON)
  endif()
  string(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS_JSON
    "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_JSON_SEPARATOR}"
    "    {\n"
    "      \"key\": \"${CROSSGL_MLIR_EXPERIMENT_RECORD_KEY}\",\n"
    "      \"sourceList\": \"CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS\",\n"
    "      \"path\": \"${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}\",\n"
    "      \"fixture\": \"${CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE}\",\n"
    "      \"present\": ${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_PRESENT_JSON}\n"
    "    }")
  string(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATIONS_JSON
    "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_JSON_SEPARATOR}"
    "    {\n"
    "      \"key\": \"${CROSSGL_MLIR_EXPERIMENT_RECORD_KEY}\",\n"
    "      \"ctest\": \"${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}\",\n"
    "      \"mode\": ${CROSSGL_MLIR_REGISTRATION_MODE_JSON},\n"
    "      \"invokesMlirOpt\": ${CROSSGL_MLIR_REGISTRATION_INVOKES_MLIR_OPT_JSON},\n"
    "      \"usesVerifyDiagnostics\": ${CROSSGL_MLIR_REGISTRATION_USES_VERIFY_DIAGNOSTICS_JSON},\n"
    "      \"buildsExperimentTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILDS_TARGET_JSON},\n"
    "      \"buildTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILD_TARGET_JSON},\n"
    "      \"input\": \"${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}\",\n"
    "      \"requiredFiles\": ${CROSSGL_MLIR_EXPERIMENT_RECORD_REQUIRED_FILES_JSON},\n"
    "      \"normalBuildRequired\": false,\n"
    "      \"productionLinked\": false\n"
    "    }")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_JSON_SEPARATOR ",\n")
  list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_CTESTS
    "${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}")
  list(APPEND CROSSGL_MLIR_EXPERIMENT_REQUIRED_GATE_FACTS
    "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}")
endforeach()
list(APPEND CROSSGL_MLIR_EXPERIMENT_REQUIRED_GATE_FACTS
  "mlir-opt discovery"
  "mlir-opt --version probe")
if(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS STREQUAL "toolchain-available")
  crossgl_mlir_json_string_list(CROSSGL_MLIR_REGISTRATION_REQUIRED_FILES_JSON
    "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}")
else()
  crossgl_mlir_json_string_list(CROSSGL_MLIR_REGISTRATION_REQUIRED_FILES_JSON)
endif()
crossgl_mlir_json_string_list(CROSSGL_MLIR_VERIFIER_CTESTS_JSON
  ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_CTESTS})
crossgl_mlir_json_string_list(CROSSGL_MLIR_REQUIRED_GATE_FACTS_JSON
  ${CROSSGL_MLIR_EXPERIMENT_REQUIRED_GATE_FACTS})
file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/mlir")
file(WRITE "${CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}"
  "{\n"
  "  \"schemaVersion\": 1,\n"
  "  \"kind\": \"crossgl-mlir-optional-tool-evidence-v0\",\n"
  "  \"status\": ${CROSSGL_MLIR_STATUS_JSON},\n"
  "  \"normalBuildRequired\": false,\n"
  "  \"productionLinked\": false,\n"
  "  \"mlirDiscovery\": {\n"
  "    \"cmakeOption\": \"CROSSGL_ENABLE_MLIR_EXPERIMENTAL\",\n"
  "    \"optionDefault\": ${CROSSGL_MLIR_OPTION_DEFAULT_JSON},\n"
  "    \"optionActual\": ${CROSSGL_MLIR_OPTION_ACTUAL_JSON},\n"
  "    \"optionEnabled\": ${CROSSGL_MLIR_OPTION_ENABLED_JSON},\n"
  "    \"cmakePackage\": \"MLIR\",\n"
  "    \"mlirFound\": ${CROSSGL_MLIR_FOUND_JSON},\n"
  "    \"target\": \"crossgl_mlir_experiment\",\n"
  "    \"targetCreated\": ${CROSSGL_MLIR_TARGET_CREATED_JSON}\n"
  "  },\n"
  "  \"verifierInput\": {\n"
  "    \"sourceList\": \"CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS\",\n"
  "    \"path\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}\",\n"
  "    \"fixture\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_FIXTURE}\",\n"
  "    \"present\": ${CROSSGL_MLIR_VERIFY_INPUT_PRESENT_JSON}\n"
  "  },\n"
  "  \"verifierInputs\": [\n"
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS_JSON}\n"
  "  ],\n"
  "  \"verifierTool\": {\n"
  "    \"name\": \"mlir-opt\",\n"
  "    \"requiredForNormalBuild\": false,\n"
  "    \"found\": ${CROSSGL_MLIR_TOOL_FOUND_JSON},\n"
  "    \"path\": ${CROSSGL_MLIR_TOOL_PATH_JSON},\n"
  "    \"discoveryStatus\": ${CROSSGL_MLIR_TOOL_DISCOVERY_STATUS_JSON}\n"
  "  },\n"
  "  \"verifierRegistration\": {\n"
  "    \"ctest\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}\",\n"
  "    \"mode\": ${CROSSGL_MLIR_REGISTRATION_MODE_JSON},\n"
  "    \"invokesMlirOpt\": ${CROSSGL_MLIR_REGISTRATION_INVOKES_MLIR_OPT_JSON},\n"
  "    \"usesVerifyDiagnostics\": ${CROSSGL_MLIR_REGISTRATION_USES_VERIFY_DIAGNOSTICS_JSON},\n"
  "    \"buildsExperimentTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILDS_TARGET_JSON},\n"
  "    \"buildTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILD_TARGET_JSON},\n"
  "    \"input\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}\",\n"
  "    \"requiredFiles\": ${CROSSGL_MLIR_REGISTRATION_REQUIRED_FILES_JSON},\n"
  "    \"normalBuildRequired\": false,\n"
  "    \"productionLinked\": false\n"
  "  },\n"
  "  \"verifierRegistrations\": [\n"
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATIONS_JSON}\n"
  "  ],\n"
  "  \"reportOnlyCatalogs\": {\n"
  "    \"sourceResourceCatalog\": {\n"
  "      \"path\": \"${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG}\",\n"
  "      \"checker\": \"${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_CHECKER}\",\n"
  "      \"requiredFixtureSection\": \"${CROSSGL_MLIR_SOURCE_RESOURCE_PRESERVATION_SECTION}\",\n"
  "      \"optionalMlirToolingRequired\": false,\n"
  "      \"normalBuildRequired\": false,\n"
  "      \"productionLinked\": false\n"
  "    }\n"
  "  },\n"
  "  \"toolProbeEvidence\": {\n"
  "    \"defaultOffBranch\": \"if(NOT CROSSGL_ENABLE_MLIR_EXPERIMENTAL)\",\n"
  "    \"findProgramCommand\": \"find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)\",\n"
  "    \"versionProbeCommand\": \"mlir-opt --version\",\n"
  "    \"defaultOffMayRunFindProgram\": false,\n"
  "    \"defaultOffMayRunVersionProbe\": false,\n"
  "    \"findProgramAttempted\": ${CROSSGL_MLIR_FIND_PROGRAM_ATTEMPTED_JSON},\n"
  "    \"versionProbeAttempted\": ${CROSSGL_MLIR_VERSION_PROBE_ATTEMPTED_JSON}\n"
  "  },\n"
  "  \"skipEvidence\": {\n"
  "    \"ctest\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}\",\n"
  "    \"ctests\": ${CROSSGL_MLIR_VERIFIER_CTESTS_JSON},\n"
  "    \"skipRegistered\": ${CROSSGL_MLIR_SKIP_REGISTERED_JSON},\n"
  "    \"reason\": ${CROSSGL_MLIR_SKIP_REASON_JSON},\n"
  "    \"labels\": ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON},\n"
  "    \"skipRegularExpression\": ${CROSSGL_MLIR_SKIP_REGEX_JSON}\n"
  "  },\n"
  "  \"skipDiagnostics\": {\n"
  "    \"status\": ${CROSSGL_MLIR_STATUS_JSON},\n"
  "    \"reportOnly\": true,\n"
  "    \"requiredGateFacts\": ${CROSSGL_MLIR_REQUIRED_GATE_FACTS_JSON},\n"
  "    \"missingReasons\": ${CROSSGL_MLIR_MISSING_REASONS_JSON},\n"
  "    \"findProgramAttempted\": ${CROSSGL_MLIR_FIND_PROGRAM_ATTEMPTED_JSON},\n"
  "    \"versionProbeAttempted\": ${CROSSGL_MLIR_VERSION_PROBE_ATTEMPTED_JSON}\n"
  "  }\n"
  "}\n")

foreach(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD IN LISTS
    CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS)
  string(REPLACE "|" ";" CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS
    "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD}")
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 1
    CROSSGL_MLIR_EXPERIMENT_RECORD_TEST)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 2
    CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 3
    CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 4
    CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 5
    CROSSGL_MLIR_EXPERIMENT_RECORD_REQUIRED_MARKERS_VAR)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 6
    CROSSGL_MLIR_EXPERIMENT_RECORD_OUTPUT_MARKERS_VAR)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 7
    CROSSGL_MLIR_EXPERIMENT_RECORD_DESCRIPTION)

  if(NOT CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS STREQUAL
      "toolchain-available")
    add_test(NAME "${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR experiment real MLIR ${CROSSGL_MLIR_EXPERIMENT_RECORD_DESCRIPTION} verifier unavailable: ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON}")
    set_tests_properties("${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}" PROPERTIES
      LABELS "mlir;optional-mlir;mlir-tool-unavailable"
      SKIP_REGULAR_EXPRESSION "^SKIP:")
    message(STATUS
      "CrossGL MLIR experiment verifier harness skipped: "
      "test=${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}; "
      "status=${CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS}; "
      "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON}")
  else()
    add_test(NAME "${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}"
      COMMAND ${CMAKE_COMMAND}
        -DCROSSGL_MLIR_EXPERIMENT_VERIFY_SCRIPT=ON
        "-DMLIR_OPT=${CROSSGL_MLIR_OPT}"
        "-DINPUT_MLIR=${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT}"
        "-DREQUIRED_MARKERS_VAR=${CROSSGL_MLIR_EXPERIMENT_RECORD_REQUIRED_MARKERS_VAR}"
        "-DOUTPUT_MARKERS_VAR=${CROSSGL_MLIR_EXPERIMENT_RECORD_OUTPUT_MARKERS_VAR}"
        "-DBUILD_DIR=${CMAKE_CURRENT_BINARY_DIR}"
        -DEXPERIMENT_TARGET=crossgl_mlir_experiment
        "-DBUILD_CONFIG=$<CONFIG>"
        -P ${CMAKE_CURRENT_LIST_FILE})
    set_tests_properties("${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}" PROPERTIES
      LABELS "mlir;optional-mlir;mlir-tool-available"
      PROCESSORS 1
      REQUIRED_FILES "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT}")
    message(STATUS
      "CrossGL MLIR experiment verifier harness registered: "
      "test=${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}; "
      "fixture=${CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE}; "
      "verifier_input=${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}; "
      "mlir-opt=${CROSSGL_MLIR_OPT}; "
      "mlir-opt --version=${CROSSGL_MLIR_OPT_VERSION_OUTPUT}")
  endif()
endforeach()
