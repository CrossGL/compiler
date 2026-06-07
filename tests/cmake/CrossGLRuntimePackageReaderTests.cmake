crossgl_add_python_script_test(
  NAME crossgl_runtime_package_reader
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_package_reader.py
  ARGS
    --cglc $<TARGET_FILE:cglc>)

crossgl_add_python_script_test(
  NAME crossgl_runtime_compiler_package_smoke
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_compiler_package_smoke.py
  ARGS
    --cglc $<TARGET_FILE:cglc>)

crossgl_add_python_script_test(
  NAME crossgl_runtime_loader
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_loader.py
  ARGS
    --cglc $<TARGET_FILE:cglc>)

crossgl_add_python_script_test(
  NAME crossgl_runtime_backend_loader
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_backend_loader.py)

crossgl_add_python_script_test(
  NAME crossgl_runtime_source_free_loader_example
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_source_free_loader_example.py)

crossgl_add_python_script_test(
  NAME crossgl_runtime_metal_loader
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_metal_loader.py)

crossgl_add_python_script_test(
  NAME crossgl_runtime_vulkan_loader
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_vulkan_loader.py)

crossgl_add_python_script_test(
  NAME crossgl_runtime_directx_loader
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_directx_loader.py)

crossgl_add_python_script_test(
  NAME crossgl_runtime_opengl_loader
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/test_opengl_loader.py)
