// Builtin-MLIR verifier smoke fixture for the optional CrossGL MLIR experiment.
// It intentionally uses only builtin module syntax and metadata attributes.
module attributes {
  crossgl_fixture = "tests/fixtures/MinimalComputeShader.cgl",
  crossgl_stage = "compute",
  crossgl_entry_point = "main",
  crossgl_local_size = "1,1,1",
  crossgl_source_location_fact_source_file = true,
  crossgl_source_location_fact_shader_module = true,
  crossgl_source_location_fact_compute_stage = true,
  crossgl_source_location_fact_entry_point = true,
  crossgl_source_location_fact_layout_local_size = true,
  crossgl_source_location_fact_return_statement = true,
  crossgl_type_fact_void_entry_point = true,
  crossgl_resource_count = 0,
  crossgl_resource_fact_descriptors_empty = true,
  crossgl_resource_fact_storage_buffers_empty = true,
  crossgl_resource_fact_storage_images_empty = true,
  crossgl_resource_fact_textures_empty = true,
  crossgl_resource_fact_samplers_empty = true,
  crossgl_target_independent_resource_metadata_empty = true,
  crossgl_resource_metadata = "target-independent:none",
  crossgl_real_mlir_smoke = true
} {
}
