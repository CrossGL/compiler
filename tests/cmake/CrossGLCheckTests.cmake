add_test(NAME cglc_check_resources
  COMMAND cglc check ${CROSSGL_RESOURCE_SHADER})
add_test(NAME cglc_check_resource_group_layout_alias
  COMMAND cglc check ${CROSSGL_RESOURCE_GROUP_ALIAS_SHADER})
set(CROSSGL_RESOURCE_GROUP_ALIAS_HIR_REGEX [=[resource uniform Params materialParams set 1 binding 2.*resource buffer float\* values set 0 binding 0]=])
add_test(NAME cglc_check_resource_group_layout_alias_hir_canonical_set
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_GROUP_ALIAS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_RESOURCE_GROUP_ALIAS_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_resource_register_layout_alias
  COMMAND cglc check ${CROSSGL_RESOURCE_REGISTER_ALIAS_SHADER})
set(CROSSGL_RESOURCE_REGISTER_ALIAS_HIR_REGEX [=[resource uniform Params materialParams set 1 binding 2.*resource uniform Params fallbackParams set 1 binding 3.*resource buffer float\* values set 0 binding 0]=])
add_test(NAME cglc_check_resource_register_layout_alias_hir_canonical_binding
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_REGISTER_ALIAS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_RESOURCE_REGISTER_ALIAS_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_resource_location_layout_alias
  COMMAND cglc check ${CROSSGL_RESOURCE_LOCATION_ALIAS_SHADER})
set(CROSSGL_RESOURCE_LOCATION_ALIAS_HIR_REGEX [=[resource uniform Params materialParams set 1 binding 2.*resource buffer float\* values set 0 binding 0]=])
add_test(NAME cglc_check_resource_location_layout_alias_hir_canonical_set
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_LOCATION_ALIAS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_RESOURCE_LOCATION_ALIAS_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_resource_arrays
  COMMAND cglc check ${CROSSGL_RESOURCE_ARRAY_SHADER})
add_test(NAME cglc_check_resource_array_access
  COMMAND cglc check ${CROSSGL_RESOURCE_ARRAY_ACCESS_SHADER})
add_test(NAME cglc_check_storage_image_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_HIR_SHADER})
set(CROSSGL_STORAGE_IMAGE_HIR_REGEX [=[resource storage_image image2D colorImage access read_write format rgba32f set 0 binding 0.*resource storage_image uimage2DArray maskAtlas access read_write format rgba32ui set 0 binding 5.*decl vec4 color2D = imageLoad\(colorImage, pixel\) : vec4.*decl uvec4 maskArray = imageLoad\(maskAtlas, arrayPixel\) : uvec4.*expr imageStore\(maskAtlas, arrayPixel, maskArray\) : void.*assign masks\[index\] : uvec4 = mask2D \+ maskArray : uvec4]=])
add_test(NAME cglc_check_storage_image_hir_load_store_types
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_descriptor_array_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_DESCRIPTOR_ARRAY_HIR_SHADER})
set(CROSSGL_STORAGE_IMAGE_DESCRIPTOR_ARRAY_HIR_REGEX [=[resource storage_image image2D\[2\] colorImages access read_write format rgba32f set 0 binding 0.*resource storage_image uimage2DArray\[2\] maskAtlases access read_write format rgba32ui set 0 binding 5.*decl vec4 colorArray = imageLoad\(colorAtlases\[1\], arrayPixel\) : vec4.*decl ivec4 label2D = imageLoad\(labelImages\[dynamicSlot\], pixel\) : ivec4.*decl uvec4 maskArray = imageLoad\(maskAtlases\[dynamicSlot\], arrayPixel\) : uvec4.*expr imageStore\(maskAtlases\[dynamicSlot\], arrayPixel, maskArray\) : void.*assign masks\[index\] : uvec4 = mask2D \+ maskArray : uvec4]=])
add_test(NAME cglc_check_storage_image_descriptor_array_hir_load_store_paths
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_DESCRIPTOR_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_DESCRIPTOR_ARRAY_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_nonuniform_descriptor_array_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_HIR_SHADER})
set(CROSSGL_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_HIR_REGEX [=[resource storage_image image2D\[2\] colorImages access read_write format rgba32f set 0 binding 0.*resource storage_image uimage2DArray\[2\] maskAtlases access read_write format rgba32ui set 0 binding 1.*decl vec4 color = imageLoad\(colorImages\[nonuniform\(slot\)\], pixel\) : vec4.*decl uvec4 value = imageLoad\(maskAtlases\[nonuniform\(slot\)\], coords\) : uvec4.*expr imageStore\(colorImages\[nonuniform\(slot\)\], pixel, color\) : void.*expr imageStore\(maskAtlases\[nonuniform\(slot\)\], coords, value\) : void.*assign masks\[index\] : uvec4 = value : uvec4]=])
add_test(NAME cglc_check_storage_image_nonuniform_descriptor_array_hir_load_store_paths
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_access_qualifier_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_HIR_SHADER})
set(CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_HIR_REGEX [=[resource storage_image image2D readImage access read format rgba32f set 0 binding 0.*resource storage_image uimage2D writeImage access write format rgba32ui set 0 binding 1.*resource storage_image image2D readWriteImage access read_write format rgba32f set 0 binding 2.*resource storage_image image2D\[2\] readImages access read format rgba32f set 0 binding 3.*expr imageStore\(writeImage, pixel, uvec4\(1, 2, 3, 4\)\) : void.*expr imageStore\(readWriteImage, pixel, second\) : void.*assign colors\[0\] : vec4 = first \+ second \+ imageLoad\(readImages\[1\], pixel\) : vec4]=])
add_test(NAME cglc_check_storage_image_access_qualifier_hir_preserves_access
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_explicit_format_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SHADER})
set(CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_HIR_REGEX [=[resource storage_image image2D readColor access read format r32f set 0 binding 0.*resource storage_image iimage2D readLabel access read format r32i set 0 binding 1.*resource storage_image uimage2D readMask access read format r32ui set 0 binding 2.*resource storage_image uimage2D writeMask access write format r32ui set 0 binding 3.*decl vec4 color = imageLoad\(readColor, pixel\) : vec4.*decl ivec4 label = imageLoad\(readLabel, pixel\) : ivec4.*decl uvec4 mask = imageLoad\(readMask, pixel\) : uvec4.*expr imageStore\(writeMask, pixel, mask\) : void]=])
add_test(NAME cglc_check_storage_image_explicit_format_hir_preserves_format
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_explicit_format_descriptor_array_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER})
set(CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_HIR_REGEX [=[resource storage_image image2D\[IMAGE_COUNT\] colorImages access read format r32f set 0 binding 0.*resource storage_image iimage2D\[IMAGE_COUNT\] labelImages access read format r32i set 0 binding 1.*resource storage_image uimage2DArray\[ATLAS_COUNT\] maskAtlases access read format r32ui set 0 binding 2.*resource storage_image uimage2DArray\[ATLAS_COUNT\] outputAtlases access write format r32ui set 0 binding 3.*decl vec4 color = imageLoad\(colorImages\[nonuniform\(imageSlot\)\], pixel\) : vec4.*decl ivec4 label = imageLoad\(labelImages\[nonuniform\(imageSlot\)\], pixel\) : ivec4.*decl uvec4 mask = imageLoad\(maskAtlases\[nonuniform\(atlasSlot\)\], atlasPixel\) : uvec4.*expr imageStore\(outputAtlases\[nonuniform\(atlasSlot\)\], atlasPixel, mask\) : void]=])
add_test(NAME cglc_check_storage_image_explicit_format_descriptor_array_hir_preserves_format
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_atomic_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_ATOMIC_SHADER})
set(CROSSGL_STORAGE_IMAGE_ATOMIC_HIR_REGEX [=[resource storage_image iimage2D signedCounters access read_write format r32i set 0 binding 0.*resource storage_image uimage2D unsignedCounters access read_write format r32ui set 0 binding 1.*resource storage_image iimage2DArray signedAtlas access read_write format r32i set 0 binding 2.*resource storage_image uimage2DArray unsignedAtlas access read_write format r32ui set 0 binding 3.*decl int signedOld = imageAtomicAdd\(signedCounters, pixel, 1\) : int.*decl uint unsignedOld = imageAtomicAdd\(unsignedCounters, pixel, uint\(1\.0\)\) : uint.*decl int signedMin = imageAtomicMin\(signedCounters, pixel \+ ivec2\(1, 0\), signedOld\) : int.*decl int signedMax = imageAtomicMax\(signedAtlas, atlasPixel, signedMin \+ 2\) : int.*decl uint unsignedMin = imageAtomicMin\(unsignedCounters, pixel, unsignedOld\) : uint.*decl uint unsignedMax = imageAtomicMax\(unsignedAtlas, atlasPixel, unsignedMin\) : uint.*decl int signedAnd = imageAtomicAnd\(signedCounters, pixel, signedMax\) : int.*decl int signedOr = imageAtomicOr\(signedAtlas, atlasPixel, signedAnd\) : int.*decl uint unsignedAnd = imageAtomicAnd\(unsignedCounters, pixel \+ ivec2\(0, 1\), unsignedMax\) : uint.*decl uint unsignedOr = imageAtomicOr\(unsignedAtlas, atlasPixel, unsignedAnd\) : uint.*decl int atlasOld = imageAtomicExchange\(signedAtlas, atlasPixel, signedOr \+ 2\) : int.*decl uint unsignedAtlasOld = imageAtomicExchange\(unsignedAtlas, atlasPixel, unsignedOr\) : uint.*expr imageAtomicAdd\(signedCounters, pixel \+ ivec2\(1, 0\), atlasOld\) : int.*expr imageAtomicExchange\(unsignedCounters, pixel \+ ivec2\(0, 1\), unsignedAtlasOld\) : uint.*expr imageAtomicXor\(signedCounters, pixel, atlasOld\) : int.*expr imageAtomicXor\(unsignedCounters, pixel, unsignedAtlasOld\) : uint]=])
add_test(NAME cglc_check_storage_image_atomic_hir_preserves_scalar_return
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_ATOMIC_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_atomic_descriptor_array_hir
  COMMAND cglc check ${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER})
set(CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_HIR_REGEX [=[resource storage_image iimage2D\[IMAGE_COUNT\] signedCounters access read_write format r32i set 0 binding 1.*resource storage_image uimage2D\[IMAGE_COUNT\] unsignedCounters access read_write format r32ui set 0 binding 2.*resource storage_image iimage2DArray\[IMAGE_COUNT\] signedAtlases access read_write format r32i set 0 binding 3.*resource storage_image uimage2DArray\[IMAGE_COUNT\] unsignedAtlases access read_write format r32ui set 0 binding 4.*decl int signedOld = imageAtomicAdd\(signedCounters\[nonuniform\(slot\)\], pixel, 1\) : int.*decl uint unsignedOld = imageAtomicAdd\(unsignedCounters\[nonuniform\(slot\)\], pixel, uint\(1\.0\)\) : uint.*decl int signedMin = imageAtomicMin\(signedCounters\[nonuniform\(slot\)\], pixel, signedOld\) : int.*decl uint unsignedMax = imageAtomicMax\(unsignedCounters\[nonuniform\(slot\)\], pixel, unsignedOld\) : uint.*decl int atlasAnd = imageAtomicAnd\(signedAtlases\[nonuniform\(slot\)\], atlasPixel, signedMin\) : int.*decl uint atlasOr = imageAtomicOr\(unsignedAtlases\[nonuniform\(slot\)\], atlasPixel, unsignedMax\) : uint.*decl int atlasOld = imageAtomicExchange\(signedAtlases\[nonuniform\(slot\)\], atlasPixel, atlasAnd\) : int.*decl uint unsignedAtlasOld = imageAtomicExchange\(unsignedAtlases\[nonuniform\(slot\)\], atlasPixel, atlasOr\) : uint.*expr imageAtomicXor\(signedCounters\[nonuniform\(slot\)\], pixel, atlasOld\) : int.*expr imageAtomicXor\(unsignedCounters\[nonuniform\(slot\)\], pixel, unsignedAtlasOld\) : uint]=])
add_test(NAME cglc_check_storage_image_atomic_descriptor_array_hir_preserves_nonuniform
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_sampler_descriptor_array
  COMMAND cglc check ${CROSSGL_SAMPLER_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_only_descriptor_array_sample
  COMMAND cglc check ${CROSSGL_TEXTURE_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER})
add_test(NAME cglc_check_sampler_only_descriptor_array_sample
  COMMAND cglc check ${CROSSGL_SAMPLER_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_array_descriptors
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_DESCRIPTOR_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_array_access_unsupported
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_ACCESS_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_lod
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_3d_lod
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_LOD_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_3d_array_lod
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_cube_lod
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_LOD_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_cube_array_lod
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_vulkan_texture_sampler_array_lod
  COMMAND cglc check ${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_vulkan_integer_texture_sampler_lod
  COMMAND cglc check ${CROSSGL_VULKAN_INTEGER_TEXTURE_SAMPLER_LOD_SHADER})
add_test(NAME cglc_check_vulkan_integer_texture_array_sampler_lod
  COMMAND cglc check ${CROSSGL_VULKAN_INTEGER_TEXTURE_ARRAY_SAMPLER_LOD_SHADER})
add_test(NAME cglc_check_texture_array_dimensions
  COMMAND cglc check ${CROSSGL_TEXTURE_ARRAY_DIMENSION_SHADER})
add_test(NAME cglc_check_texture_compare_shadow
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_SHADOW_SHADER})
add_test(NAME cglc_check_texture_array_shadow_compare
  COMMAND cglc check ${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_SHADER})
add_test(NAME cglc_check_texture_compare_lod
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_LOD_SHADER})
add_test(NAME cglc_check_texture_compare_2d_lod
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_2D_LOD_SHADER})
add_test(NAME cglc_check_comparison_sampler_role
  COMMAND cglc check ${CROSSGL_COMPARISON_SAMPLER_ROLE_SHADER})
add_test(NAME cglc_check_texture_array_shadow_compare_lod_unsupported
  COMMAND cglc check ${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_texture_2d_array_shadow_compare_lod_unsupported
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_texture_cube_shadow_compare_lod_unsupported
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_texture_cube_array_shadow_compare_lod_unsupported
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_texture_2d_shadow_compare_lod_manual
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER})
add_test(NAME cglc_check_texture_2d_array_shadow_compare_lod_manual
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER})
add_test(NAME cglc_check_texture_2d_shadow_compare_lod_manual_offset
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER})
add_test(NAME cglc_check_texture_2d_array_shadow_compare_lod_manual_offset
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER})
add_test(NAME cglc_check_texture_2d_shadow_compare_lod_manual_gather_2x2
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER})
add_test(NAME cglc_check_texture_2d_array_shadow_compare_lod_manual_gather_2x2
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER})
add_test(NAME cglc_check_texture_2d_shadow_compare_lod_manual_kernel_4
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER})
add_test(NAME cglc_check_texture_2d_array_shadow_compare_lod_manual_kernel_4
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER})
add_test(NAME cglc_check_texture_2d_shadow_compare_lod_manual_kernel_8
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER})
add_test(NAME cglc_check_texture_2d_array_shadow_compare_lod_manual_kernel_8
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER})
add_test(NAME cglc_check_texture_2d_shadow_compare_lod_manual_kernel_list
  COMMAND cglc check ${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER})
add_test(NAME cglc_check_texture_cube_shadow_compare_lod_manual
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_MANUAL_SHADER})
add_test(NAME cglc_check_texture_cube_array_shadow_compare_lod_manual
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER})
add_test(NAME cglc_check_texture_compare_lod_manual_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_only_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_sampler_only_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_SAMPLER_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_compare_descriptor_array_lod
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_texture_array_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_array_compare_descriptor_array_lod
  COMMAND cglc check ${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_texture_cube_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_cube_compare_descriptor_array_lod
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_mixed_texture_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_mixed_resource_descriptor_array
  COMMAND cglc check ${CROSSGL_MIXED_RESOURCE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_mixed_resource_symbolic_descriptor_array
  COMMAND cglc check ${CROSSGL_MIXED_RESOURCE_SYMBOLIC_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_vulkan_dynamic_descriptor_array_index
  COMMAND cglc check ${CROSSGL_VULKAN_DYNAMIC_DESCRIPTOR_ARRAY_INDEX_SHADER})
add_test(NAME cglc_check_vulkan_nonuniform_descriptor_array_index
  COMMAND cglc check ${CROSSGL_VULKAN_NONUNIFORM_DESCRIPTOR_ARRAY_INDEX_SHADER})
add_test(NAME cglc_check_texture_only_nonuniform_descriptor_array_sample
  COMMAND cglc check ${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER})
add_test(NAME cglc_check_texture_only_nonuniform_uint_descriptor_array_sample
  COMMAND cglc check ${CROSSGL_TEXTURE_ONLY_NONUNIFORM_UINT_DESCRIPTOR_ARRAY_SAMPLE_SHADER})
add_test(NAME cglc_check_sampler_only_nonuniform_descriptor_array_sample
  COMMAND cglc check ${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER})
add_test(NAME cglc_check_texture_only_nonuniform_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_sampler_only_nonuniform_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_only_nonuniform_compare_descriptor_array_lod
  COMMAND cglc check ${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_sampler_only_nonuniform_compare_descriptor_array_lod
  COMMAND cglc check ${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_texture_only_nonuniform_compare_lod_manual_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_sampler_only_nonuniform_compare_lod_manual_descriptor_array
  COMMAND cglc check ${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_cube_family_only_nonuniform_compare_lod_manual_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_sampler_cube_family_only_nonuniform_compare_lod_manual_descriptor_array
  COMMAND cglc check ${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_family_only_nonuniform_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_sampler_family_only_nonuniform_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_compare_nonuniform_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_compare_nonuniform_descriptor_array_lod
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER})
add_test(NAME cglc_check_texture_compare_lod_manual_nonuniform_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array
  COMMAND cglc check ${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_only_nonuniform_descriptor_array_sample_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl vec4 color = texture_sample_lod\\(colorMaps\\[nonuniform\\(descriptor\\)\\], linearSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_only_nonuniform_descriptor_array_sample_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl vec4 color = texture_sample_lod\\(colorMap, linearSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_nonuniform_descriptor_array_hir_markers
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare\\(shadowMaps\\[nonuniform\\(descriptor\\)\\], shadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_lod_nonuniform_descriptor_array_hir_markers
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare_lod\\(shadowMaps\\[nonuniform\\(descriptor\\)\\], shadowSamplers\\[nonuniform\\(descriptor\\)\\].*2\\.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_lod_manual_nonuniform_descriptor_array_hir_markers
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare_lod_manual\\(shadowAtlases\\[nonuniform\\(descriptor\\)\\], rawShadowSamplers\\[nonuniform\\(descriptor\\)\\].*less_equal"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_only_nonuniform_compare_descriptor_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare\\(shadowMaps\\[nonuniform\\(descriptor\\)\\], shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_only_nonuniform_compare_descriptor_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare\\(shadowMap, shadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_only_nonuniform_compare_lod_descriptor_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare_lod\\(shadowMaps\\[nonuniform\\(descriptor\\)\\], shadowSampler.*2\\.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_only_nonuniform_compare_lod_descriptor_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare_lod\\(shadowMap, shadowSamplers\\[nonuniform\\(descriptor\\)\\].*2\\.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_only_nonuniform_compare_lod_manual_descriptor_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare_lod_manual\\(shadowAtlases\\[nonuniform\\(descriptor\\)\\], rawShadowSampler.*less_equal"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_only_nonuniform_compare_lod_manual_descriptor_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float visibility = texture_compare_lod_manual\\(shadowAtlas, rawShadowSamplers\\[nonuniform\\(descriptor\\)\\].*less_equal"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_family_nonuniform_compare_cube_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeVisibility = texture_compare\\(shadowCubes\\[nonuniform\\(descriptor\\)\\], shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_family_nonuniform_compare_cube_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeArrayVisibility = texture_compare\\(shadowCubeArrays\\[nonuniform\\(descriptor\\)\\], shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_family_nonuniform_compare_cube_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeVisibility = texture_compare\\(shadowCube, shadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_family_nonuniform_compare_cube_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeArrayVisibility = texture_compare\\(shadowCubeArray, shadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_cube_family_nonuniform_compare_lod_manual_cube_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeVisibility = texture_compare_lod_manual\\(shadowCubes\\[nonuniform\\(descriptor\\)\\], rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_cube_family_nonuniform_compare_lod_manual_cube_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeArrayVisibility = texture_compare_lod_manual\\(shadowCubeArrays\\[nonuniform\\(descriptor\\)\\], rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_cube_family_nonuniform_compare_lod_manual_cube_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeVisibility = texture_compare_lod_manual\\(shadowCube, rawShadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_sampler_cube_family_nonuniform_compare_lod_manual_cube_array_hir_marker
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeArrayVisibility = texture_compare_lod_manual\\(shadowCubeArray, rawShadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_cube_family_compare_lod_manual_nonuniform_cube_hir_markers
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeVisibility = texture_compare_lod_manual\\(shadowCubes\\[nonuniform\\(descriptor\\)\\], rawShadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_cube_family_compare_lod_manual_nonuniform_cube_array_hir_markers
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float cubeArrayVisibility = texture_compare_lod_manual\\(shadowCubeArrays\\[nonuniform\\(descriptor\\)\\], rawShadowSamplers\\[nonuniform\\(descriptor\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_mixed_texture_manual_compare_descriptor_array
  COMMAND cglc check ${CROSSGL_MIXED_TEXTURE_MANUAL_COMPARE_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_texture_sampler_descriptor_array_size_mismatch
  COMMAND cglc check ${CROSSGL_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SIZE_MISMATCH_SHADER})
add_test(NAME cglc_check_directx_mixed_manual_sampler_usage_unsupported
  COMMAND cglc check ${CROSSGL_DIRECTX_MIXED_MANUAL_SAMPLER_USAGE_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_directx_mixed_sampler_array_usage_unsupported
  COMMAND cglc check ${CROSSGL_DIRECTX_MIXED_SAMPLER_ARRAY_USAGE_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_metal_multi_set_resources
  COMMAND cglc check ${CROSSGL_METAL_MULTI_SET_RESOURCE_SHADER})
add_test(NAME cglc_check_metal_unsized_storage_buffer_array_unsupported
  COMMAND cglc check ${CROSSGL_METAL_STORAGE_BUFFER_ARRAY_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_metal_storage_buffer_dynamic_descriptor_array_unsupported
  COMMAND cglc check ${CROSSGL_METAL_STORAGE_BUFFER_DYNAMIC_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_metal_storage_buffer_folded_descriptor_array
  COMMAND cglc check ${CROSSGL_METAL_STORAGE_BUFFER_FOLDED_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_metal_storage_buffer_out_of_range_descriptor_array_unsupported
  COMMAND cglc check ${CROSSGL_METAL_STORAGE_BUFFER_OUT_OF_RANGE_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_arithmetic_compute
  COMMAND cglc check ${CROSSGL_ARITHMETIC_COMPUTE_SHADER})
add_test(NAME cglc_check_colon_var_compute
  COMMAND cglc check ${CROSSGL_COLON_VAR_COMPUTE_SHADER})
add_test(NAME cglc_check_colon_var_compute_hir_canonical_declaration
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COLON_VAR_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float base = values\\[1\\] : float[^\n]*\n      decl float scaled = base \\* 2\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_fn_style_function
  COMMAND cglc check ${CROSSGL_FN_STYLE_FUNCTION_SHADER})
add_test(NAME cglc_check_fn_style_function_hir_signatures
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FN_STYLE_FUNCTION_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn scale\\(float value, float factor\\) -> float[^\n]*\n      return value \\* factor : float[^\n]*\n    fn writeValue\\(int index, float value\\) -> void[^\n]*\n      assign values\\[index\\] : float = value : float[^\n]*\n      return[^\n]*\n    fn main\\(\\) -> void"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_fn_style_function_hir_calls
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FN_STYLE_FUNCTION_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float base = scale\\(values\\[1\\], 2\\.0\\) : float[^\n]*\n      expr writeValue\\(0, base\\) : void"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_numeric_float_literals
  COMMAND cglc check
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/NumericFloatLiteralShader.cgl)
add_test(NAME cglc_dump_hir_numeric_float_literals
  COMMAND cglc dump-ir
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/NumericFloatLiteralShader.cgl
    --stage hir)
set_tests_properties(cglc_dump_hir_numeric_float_literals
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float leadingDotExponent = \\.5e\\+2f : float[^\n]*\n      decl float hexExponent = 0x1p-2f : float")
add_test(NAME cglc_check_arithmetic_compute_hir_dead_code_cleanup
  COMMAND cglc dump-ir ${CROSSGL_ARITHMETIC_COMPUTE_SHADER} --stage hir)
set_tests_properties(cglc_check_arithmetic_compute_hir_dead_code_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "fn main\\(\\) -> void[^\n]*\n      return"
    FAIL_REGULAR_EXPRESSION "decl float|decl int|assign ")
add_test(NAME cglc_check_intrinsic_compute
  COMMAND cglc check ${CROSSGL_INTRINSIC_COMPUTE_SHADER})
add_test(NAME cglc_check_intrinsic_compute_hir_call_types
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl vec4 reflected = reflect\\(direction, normalize\\(vectors\\[1\\]\\)\\) : vec4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_atan_intrinsic_compute
  COMMAND cglc check ${CROSSGL_ATAN_INTRINSIC_COMPUTE_SHADER})
add_test(NAME cglc_check_storage_buffer_compute
  COMMAND cglc check ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER})
add_test(NAME cglc_check_read_modify_write_compute
  COMMAND cglc check ${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER})
add_test(NAME cglc_check_load_local_compute
  COMMAND cglc check ${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER})
add_test(NAME cglc_check_load_local_compute_hir_scalar_load_store
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float x = values\\[0\\] : float[^\n]*\n      assign values\\[1\\] : float = x \\+ 1\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_comparison_compute
  COMMAND cglc check ${CROSSGL_COMPARISON_COMPUTE_SHADER})
add_test(NAME cglc_check_comparison_compute_hir_dead_code_cleanup
  COMMAND cglc dump-ir ${CROSSGL_COMPARISON_COMPUTE_SHADER} --stage hir)
set_tests_properties(cglc_check_comparison_compute_hir_dead_code_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "fn main\\(\\) -> void[^\n]*\n      return"
    FAIL_REGULAR_EXPRESSION "decl bool|decl float x|decl int i|assign ")
add_test(NAME cglc_check_if_compute
  COMMAND cglc check ${CROSSGL_IF_COMPUTE_SHADER})
add_test(NAME cglc_check_if_compute_hir_branch_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=if x > 0\\.0 : bool[^\n]*\n        assign y : float = x : float[^\n]*\n      else[^\n]*\n        assign y : float = -x : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_if_scoped_compute
  COMMAND cglc check ${CROSSGL_IF_SCOPED_COMPUTE_SHADER})
add_test(NAME cglc_check_nested_if_compute
  COMMAND cglc check ${CROSSGL_NESTED_IF_COMPUTE_SHADER})
add_test(NAME cglc_check_nested_if_compute_hir_branch_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float scaled = x \\* 2\\.0 : float[^\n]*\n        if scaled > 3\\.0 : bool[^\n]*\n          assign y : float = scaled : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_if_return_compute
  COMMAND cglc check ${CROSSGL_IF_RETURN_COMPUTE_SHADER})
add_test(NAME cglc_check_if_return_compute_hir_branch_return_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=if x > 0\\.0 : bool[^\n]*\n        assign values\\[1\\] : float = x : float[^\n]*\n        return[^\n]*\n      else[^\n]*\n        assign values\\[1\\] : float = -x : float[^\n]*\n        return"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_read_modify_write_compute_hir_assignment_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign values\\[0\\] : float = values\\[0\\] \\+ 1\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_compute
  COMMAND cglc check ${CROSSGL_FOR_COMPUTE_SHADER})
add_test(NAME cglc_check_for_compute_hir_loop_contract
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for i < 4 : bool update i\\+\\+[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ 1 : int[^\n]*\n        decl float x = values\\[i\\] : float[^\n]*\n        assign values\\[i\\] : float = x \\+ 1\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_stride_compute
  COMMAND cglc check ${CROSSGL_FOR_STRIDE_COMPUTE_SHADER})
add_test(NAME cglc_check_for_stride_compute_hir_update_contract
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for i < 8 : bool update i\\+=2[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ 2 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_nested_for_compute
  COMMAND cglc check ${CROSSGL_NESTED_FOR_COMPUTE_SHADER})
add_test(NAME cglc_check_nested_for_compute_hir_body_placement
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for i < 2 : bool update i\\+\\+[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ 1 : int[^\n]*\n        for j < 2 : bool update j\\+\\+[^\n]*\n          init decl int j = 0 : int[^\n]*\n          update assign j : int = j \\+ 1 : int[^\n]*\n          decl int index = i \\* 2 \\+ j : int[^\n]*\n          decl float x = values\\[index\\] : float[^\n]*\n          assign values\\[index\\] : float = x \\+ 1\\.0 : float[^\n]*\n        assign values\\[i\\] : float = values\\[i\\] \\+ 2\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_dynamic_stride_compute
  COMMAND cglc check ${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER})
add_test(NAME cglc_check_for_dynamic_stride_compute_hir_update_contract
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl int stride = 2 : int[^\n]*\n      for i < 8 : bool update i\\+=stride[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ stride : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_constant_stride_compute
  COMMAND cglc check ${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER})
add_test(NAME cglc_check_for_constant_stride_compute_hir_update_contract
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=const int TILE_SIZE = 2 folded 2[^\n]*\n  stage compute entry main[^\n\\r]*[\n\\r]+    workgroup_size 1, 1, 1[^\n]*\n    resource buffer float\\* values set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      for i < 8 : bool update i\\+=TILE_SIZE[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ TILE_SIZE : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_folded_update_compute
  COMMAND cglc check ${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER})
add_test(NAME cglc_check_for_folded_update_compute_hir_simplified_update
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for i < 8 : bool[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ \\(3\\) : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_omitted_header_compute
  COMMAND cglc check ${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER})
add_test(NAME cglc_check_for_empty_condition_hir_true
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for true : bool[^\n]*\n        assign value : int = value \\+ 1 : int[^\n]*\n        if value >= 2 : bool[^\n]*\n          break"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_omitted_init_update_hir
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for value < 4 : bool[^\n]*\n        assign value : int = value \\+ 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_omitted_condition_with_update_hir
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for true : bool update i\\+\\+[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ 1 : int[^\n]*\n        if i >= 2 : bool[^\n]*\n          break"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_while_compute
  COMMAND cglc check ${CROSSGL_WHILE_COMPUTE_SHADER})
add_test(NAME cglc_check_do_while_compute
  COMMAND cglc check ${CROSSGL_DO_WHILE_COMPUTE_SHADER})
add_test(NAME cglc_check_do_while_hir_condition
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DO_WHILE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for true : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_do_while_hir_continue_rewrite
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DO_WHILE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=if value < 2 : bool[^\n]*\n          block[^\n]*\n            if value >= 4 : bool[^\n]*\n              break[^\n]*\n            continue"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_do_while_hir_trailing_condition_break
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DO_WHILE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign total : float = total \\+ float\\(value\\) : float[^\n]*\n        if value >= 4 : bool[^\n]*\n          break"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_switch_compute
  COMMAND cglc check ${CROSSGL_SWITCH_COMPUTE_SHADER})
add_test(NAME cglc_check_switch_grouped_labels_compute
  COMMAND cglc check ${CROSSGL_SWITCH_GROUPED_LABELS_COMPUTE_SHADER})
add_test(NAME cglc_check_switch_terminal_grouped_labels_compute
  COMMAND cglc check ${CROSSGL_SWITCH_TERMINAL_GROUPED_LABELS_COMPUTE_SHADER})
add_test(NAME cglc_check_switch_hir_if_chain
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SWITCH_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=block[^\n]*\n        decl int __crossgl_selector = mode : int[^\n]*\n        if __crossgl_selector == 0 : bool[^\n]*\n          assign total : int = 1 : int[^\n]*\n        else[^\n]*\n          if __crossgl_selector == 1 : bool[^\n]*\n            assign total : int = 2 : int[^\n]*\n          else[^\n]*\n            assign total : int = 3 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_switch_hir_no_switch_break
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SWITCH_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set_tests_properties(cglc_check_switch_hir_no_switch_break
  PROPERTIES FAIL_REGULAR_EXPRESSION "switch|case|default|break")
add_test(NAME cglc_check_switch_grouped_labels_hir_if_chain
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SWITCH_GROUPED_LABELS_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=block[^\n]*\n        decl int __crossgl_selector = mode : int[^\n]*\n        if __crossgl_selector == 0 \\|\\| __crossgl_selector == 1 : bool[^\n]*\n          assign total : int = 10 : int[^\n]*\n        else[^\n]*\n          if __crossgl_selector == 2 : bool[^\n]*\n            assign total : int = 20 : int[^\n]*\n          else[^\n]*\n            assign total : int = 30 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_switch_terminal_grouped_labels_hir_if_chain
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SWITCH_TERMINAL_GROUPED_LABELS_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=block[^\n]*\n        decl int __crossgl_selector = mode : int[^\n]*\n        if __crossgl_selector == 0 \\|\\| __crossgl_selector == 1 : bool[^\n]*\n          assign total : int = 10 : int[^\n]*\n      block[^\n]*\n        decl int __crossgl_selector = mode : int[^\n]*\n        if __crossgl_selector == 2 \\|\\| __crossgl_selector == 3 : bool[^\n]*\n          assign total : int = total \\+ 20 : int[^\n]*\n        else[^\n]*\n          assign total : int = total \\+ 30 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ForIncrementDecrementHIRShader.cgl)
add_test(NAME cglc_check_for_increment_decrement_hir
  COMMAND cglc check ${CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER})
add_test(NAME cglc_check_for_increment_decrement_hir_updates
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for i < 4 : bool update i\\+\\+[^\n]*\n        init decl int i = 0 : int[^\n]*\n        update assign i : int = i \\+ 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_prefix_increment_hir_update
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for j < 4 : bool update \\+\\+j[^\n]*\n        init decl int j = 0 : int[^\n]*\n        update assign j : int = j \\+ 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_postfix_decrement_hir_update
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for k > 0 : bool update k--[^\n]*\n        init decl int k = 4 : int[^\n]*\n        update assign k : int = k - 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_for_prefix_decrement_hir_update
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for m > 0 : bool update --m[^\n]*\n        init decl int m = 4 : int[^\n]*\n        update assign m : int = m - 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/WhileControlFlowHIRShader.cgl)
add_test(NAME cglc_check_while_control_flow_hir
  COMMAND cglc check ${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER})
add_test(NAME cglc_check_while_control_flow_hir_condition
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for i < 4 : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_while_control_flow_hir_scoped_block
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float sample = total : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_while_control_flow_hir_outer_scope_restored
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign sample : int = i : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_while_control_flow_hir_body_update
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign i : int = i \\+ 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_non_parenthesized_control_flow
  COMMAND cglc check ${CROSSGL_NON_PAREN_CONTROL_FLOW_SHADER})
add_test(NAME cglc_check_non_parenthesized_if_hir_condition
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NON_PAREN_CONTROL_FLOW_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=if values\\[0\\] > 0\\.0 : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_non_parenthesized_else_if_hir_condition
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NON_PAREN_CONTROL_FLOW_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=if values\\[1\\] > 0\\.0 : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_non_parenthesized_while_hir_condition
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NON_PAREN_CONTROL_FLOW_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for index < 4 : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_let_mut_compute
  COMMAND cglc check ${CROSSGL_LET_MUT_COMPUTE_SHADER})
add_test(NAME cglc_check_let_mut_int_hir_declaration
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LET_MUT_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl int value = int\\(values\\[1\\]\\) : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_let_mut_float_hir_declaration
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LET_MUT_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float total = values\\[0\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_let_mut_hir_update
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LET_MUT_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign value : int = value \\+ 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_loop_compute
  COMMAND cglc check ${CROSSGL_LOOP_COMPUTE_SHADER})
add_test(NAME cglc_check_loop_hir_lowered_condition
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOOP_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for true : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_loop_hir_control_transfer
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOOP_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=if value >= 4 : bool[^\n]*\n          break[^\n]*\n        if value == 2 : bool[^\n]*\n          continue"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_HIR_CONTROL_TRANSFER_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/HIRControlTransferShader.cgl)
add_test(NAME cglc_check_hir_control_transfer_explicit_statements
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_HIR_CONTROL_TRANSFER_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=continue[^\n]*\n        if i == 2 : bool[^\n]*\n          break"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_fragment_discard_hir_statement
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_HIR_CONTROL_TRANSFER_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=if input.uv.x < 0.0 : bool[^\n]*\n        discard"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_hir_control_transfer_unreachable_cleanup
  COMMAND cglc dump-ir ${CROSSGL_HIR_CONTROL_TRANSFER_SHADER} --stage hir)
set_tests_properties(cglc_check_hir_control_transfer_unreachable_cleanup
  PROPERTIES FAIL_REGULAR_EXPRESSION "99\\.0")
set(CROSSGL_WHILE_OPTIMIZER_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/WhileOptimizerBoundaryHIRShader.cgl)
add_test(NAME cglc_check_while_optimizer_boundary_hir
  COMMAND cglc check ${CROSSGL_WHILE_OPTIMIZER_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_while_optimizer_boundary_hir_loop_condition
  COMMAND cglc dump-ir ${CROSSGL_WHILE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_while_optimizer_boundary_hir_loop_condition
  PROPERTIES PASS_REGULAR_EXPRESSION "for i < 4 : bool")
add_test(NAME cglc_check_while_optimizer_boundary_hir_storage_index
  COMMAND cglc dump-ir ${CROSSGL_WHILE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_while_optimizer_boundary_hir_storage_index
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[i\\] : float = total : float")
add_test(NAME cglc_check_while_optimizer_boundary_hir_loop_carried_slot
  COMMAND cglc dump-ir ${CROSSGL_WHILE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_while_optimizer_boundary_hir_loop_carried_slot
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[slot\\] : float = total : float"
    FAIL_REGULAR_EXPRESSION "assign values\\[0\\] : float = total : float")
add_test(NAME cglc_check_while_optimizer_boundary_hir_inner_scalar_cleanup
  COMMAND cglc dump-ir ${CROSSGL_WHILE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_while_optimizer_boundary_hir_inner_scalar_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[1\\] : float = values\\[1\\] \\+ 1\\.0 : float"
    FAIL_REGULAR_EXPRESSION "foldedIndex|unusedLocal")
add_test(NAME cglc_check_while_optimizer_boundary_hir_branch_unreachable_cleanup
  COMMAND cglc dump-ir ${CROSSGL_WHILE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_while_optimizer_boundary_hir_branch_unreachable_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign total : float = total \\+ 2\\.0 : float"
    FAIL_REGULAR_EXPRESSION "if true : bool|99\\.0|100\\.0")
set(CROSSGL_FOR_OPTIMIZER_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ForOptimizerBoundaryHIRShader.cgl)
add_test(NAME cglc_check_for_optimizer_boundary_hir
  COMMAND cglc check ${CROSSGL_FOR_OPTIMIZER_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_for_optimizer_boundary_hir_loop_carried_storage_write
  COMMAND cglc dump-ir ${CROSSGL_FOR_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_for_optimizer_boundary_hir_loop_carried_storage_write
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign carry : float = carry \\+ values\\[dynamicBase \\+ i\\] : float.*assign values\\[dynamicBase \\+ i\\] : float = carry : float")
add_test(NAME cglc_check_for_optimizer_boundary_hir_nested_index_arithmetic
  COMMAND cglc dump-ir ${CROSSGL_FOR_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_for_optimizer_boundary_hir_nested_index_arithmetic
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl int nestedIndex = dynamicBase \\+ i \\+ j : int.*assign values\\[nestedIndex\\] : float = values\\[nestedIndex\\] \\+ carry : float")
add_test(NAME cglc_check_for_optimizer_boundary_hir_dynamic_stride_preserved
  COMMAND cglc dump-ir ${CROSSGL_FOR_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_for_optimizer_boundary_hir_dynamic_stride_preserved
  PROPERTIES
    PASS_REGULAR_EXPRESSION "update assign i : int = i \\+ dynamicStride : int"
    FAIL_REGULAR_EXPRESSION "update assign i : int = i \\+ \\(3\\) : int")
add_test(NAME cglc_check_for_optimizer_boundary_hir_folded_update_simplified
  COMMAND cglc dump-ir ${CROSSGL_FOR_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_for_optimizer_boundary_hir_folded_update_simplified
  PROPERTIES
    PASS_REGULAR_EXPRESSION "update assign k : int = k \\+ \\(3\\) : int"
    FAIL_REGULAR_EXPRESSION "1 \\+ 2")
add_test(NAME cglc_check_for_optimizer_boundary_hir_dead_local_cleanup
  COMMAND cglc dump-ir ${CROSSGL_FOR_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_for_optimizer_boundary_hir_dead_local_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[k\\] : float = values\\[k\\] \\+ carry : float.*assign values\\[dynamicBase\\] : float = carry : float"
    FAIL_REGULAR_EXPRESSION "deadLoopLocal|deadNestedLocal|deadFoldedLocal")
set(CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/AlgebraicSimplifyHIRShader.cgl)
add_test(NAME cglc_check_algebraic_simplify_hir
  COMMAND cglc check ${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER})
add_test(NAME cglc_check_algebraic_simplify_hir_add_zero
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float plusRight = base \\+ 0[.]0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_left_identity
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float plusLeft = 0[.]0 \\+ plusRight : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_sub_zero
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float minusRight = plusLeft : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_mul_identity
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float multiplyLeft = multiplyRight : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_mul_div_identity
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float divideRight = multiplyLeft : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_double_negation
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl bool visible = .*dynamicIndex > 0.* : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_select_cleanup
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl int selected = \\(dynamicIndex\\) : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_nonuniform_index
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=colorMaps\\[nonuniform\\(dynamicIndex\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_sampler_index
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=linearSamplers\\[selected\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_algebraic_simplify_hir_update_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ALGEBRAIC_SIMPLIFY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=update assign i : int = .*i.*\\+ 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/LocalScalarPropagationHIRShader.cgl)
add_test(NAME cglc_check_local_scalar_propagation_hir
  COMMAND cglc check ${CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER})
add_test(NAME cglc_check_local_scalar_propagation_hir_nonuniform_index
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=colorMaps\\[nonuniform\\(1\\)\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_scalar_propagation_hir_sampler_index
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=linearSamplers\\[1\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_scalar_propagation_hir_manual_payload
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=texture_compare_lod_manual\\(shadowAtlases\\[nonuniform\\(1\\)\\], rawShadowSamplers\\[1\\], vec3\\(0.25, 0.5, 1.0\\), depth, lod, less_equal\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_scalar_propagation_hir_resource_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign values\\[1\\] : float = sampled\\.x \\+ manual : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_scalar_propagation_hir_loop_update
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=update assign i : int = i \\+ 1 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_scalar_propagation_hir_math
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_SCALAR_PROPAGATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign values\\[i\\] : float = values\\[i\\] \\+ 3 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_TEXTURE_OPTIMIZER_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/TextureOptimizerBoundaryHIRShader.cgl)
add_test(NAME cglc_check_texture_optimizer_boundary_hir
  COMMAND cglc check ${CROSSGL_TEXTURE_OPTIMIZER_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_texture_optimizer_boundary_hir_sample_lod
  COMMAND cglc dump-ir ${CROSSGL_TEXTURE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_texture_optimizer_boundary_hir_sample_lod
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl vec4 sampled = texture_sample_lod\\(colorMaps\\[nonuniform\\(textureSlot\\)\\], linearSamplers\\[samplerSlot\\], uv, sampleLod\\) : vec4"
    FAIL_REGULAR_EXPRESSION "linearSamplers\\[nonuniform\\(")
add_test(NAME cglc_check_texture_optimizer_boundary_hir_compare_markers
  COMMAND cglc dump-ir ${CROSSGL_TEXTURE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_texture_optimizer_boundary_hir_compare_markers
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float hardwareVisibility = texture_compare\\(shadowMaps\\[textureSlot\\], shadowSamplers\\[nonuniform\\(samplerSlot\\)\\], uv, depth\\) : float.*decl float lodVisibility = texture_compare_lod\\(shadowMaps\\[nonuniform\\(textureSlot\\)\\], shadowSamplers\\[samplerSlot\\], uv, depth, compareLod\\) : float"
    FAIL_REGULAR_EXPRESSION "shadowMaps\\[nonuniform\\(samplerSlot\\)\\]|shadowSamplers\\[nonuniform\\(textureSlot\\)\\]")
add_test(NAME cglc_check_texture_optimizer_boundary_hir_manual_kernel4
  COMMAND cglc dump-ir ${CROSSGL_TEXTURE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_texture_optimizer_boundary_hir_manual_kernel4
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float kernelVisibility = texture_compare_lod_manual_kernel\\(shadowAtlases\\[nonuniform\\(textureSlot\\)\\], rawShadowSamplers\\[samplerSlot\\], shadowUv, depth, kernelLod, less_equal, texture_compare_kernel\\(ivec2\\(-1, -1\\), 0\\.25, ivec2\\(0, -1\\), 0\\.25, ivec2\\(-1, 0\\), 0\\.25, ivec2\\(0, 0\\), 0\\.25\\)\\) : float"
    FAIL_REGULAR_EXPRESSION "shadowAtlases\\[nonuniform\\(samplerSlot\\)\\]|rawShadowSamplers\\[nonuniform\\(textureSlot\\)\\]")
add_test(NAME cglc_check_texture_optimizer_boundary_hir_manual_kernel_list
  COMMAND cglc dump-ir ${CROSSGL_TEXTURE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_texture_optimizer_boundary_hir_manual_kernel_list
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float listVisibility = texture_compare_lod_manual_kernel\\(shadowMaps\\[textureSlot\\], rawShadowSamplers\\[nonuniform\\(samplerSlot\\)\\], uv, depth, compareLod, greater_equal, texture_compare_kernel\\(ivec2\\(0, 0\\), 0\\.40, ivec2\\(1, 0\\), 0\\.20, ivec2\\(0, 1\\), 0\\.20, ivec2\\(-1, 0\\), 0\\.20\\)\\) : float"
    FAIL_REGULAR_EXPRESSION "shadowMaps\\[nonuniform\\(samplerSlot\\)\\]|rawShadowSamplers\\[nonuniform\\(textureSlot\\)\\]")
add_test(NAME cglc_check_texture_optimizer_boundary_hir_storage_and_cleanup
  COMMAND cglc dump-ir ${CROSSGL_TEXTURE_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_texture_optimizer_boundary_hir_storage_and_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign pixels\\[0\\] : vec4 = sampled \\+ vec4\\(hardwareVisibility, lodVisibility, kernelVisibility, listVisibility\\) : vec4.*assign values\\[0\\] : float = hardwareVisibility \\+ lodVisibility : float.*assign values\\[1\\] : float = kernelVisibility \\+ listVisibility : float"
    FAIL_REGULAR_EXPRESSION "deadScalar|deadLocal")
set(CROSSGL_OPTIMIZER_INTRINSIC_SWIZZLE_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/OptimizerIntrinsicSwizzleBoundaryHIRShader.cgl)
add_test(NAME cglc_check_optimizer_intrinsic_swizzle_boundary_hir
  COMMAND cglc check ${CROSSGL_OPTIMIZER_INTRINSIC_SWIZZLE_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_optimizer_intrinsic_swizzle_boundary_hir_dynamic_abs_intrinsic
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTRINSIC_SWIZZLE_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_intrinsic_swizzle_boundary_hir_dynamic_abs_intrinsic
  PROPERTIES PASS_REGULAR_EXPRESSION "decl float dynamicAbs = abs\\(values\\[0\\]\\) : float")
add_test(NAME cglc_check_optimizer_intrinsic_swizzle_boundary_hir_dynamic_length_intrinsic
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTRINSIC_SWIZZLE_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_intrinsic_swizzle_boundary_hir_dynamic_length_intrinsic
  PROPERTIES PASS_REGULAR_EXPRESSION "decl float dynamicLength = length\\(dynamicVector\\) : float")
add_test(NAME cglc_check_optimizer_intrinsic_swizzle_boundary_hir_constant_intrinsic_fold
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTRINSIC_SWIZZLE_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_intrinsic_swizzle_boundary_hir_constant_intrinsic_fold
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[1\\] : float = 5 : float")
add_test(NAME cglc_check_optimizer_intrinsic_swizzle_boundary_hir_swizzle_storage_write
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTRINSIC_SWIZZLE_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_intrinsic_swizzle_boundary_hir_swizzle_storage_write
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[2\\] : float = dynamicVector\\.rgb\\.z : float")
add_test(NAME cglc_check_optimizer_intrinsic_swizzle_boundary_hir_dead_local_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTRINSIC_SWIZZLE_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_intrinsic_swizzle_boundary_hir_dead_local_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[0\\] : float = dynamicAbs \\+ dynamicLength : float"
    FAIL_REGULAR_EXPRESSION "unusedFolded|unusedSwizzle")
set(CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/OptimizerBranchReadModifyBoundaryHIRShader.cgl)
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir
  COMMAND cglc check ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_then_write
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_then_write
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[1\\] : float = thenLive : float")
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_else_write
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_else_write
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[2\\] : float = elseLive : float")
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_branch_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_branch_dead_cleanup
  PROPERTIES FAIL_REGULAR_EXPRESSION "thenDead|elseDead")
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_nested_then_write
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_nested_then_write
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[8\\] : float = nestedThenLive : float")
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_nested_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_nested_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[8\\] : float = nestedElseLive : float"
    FAIL_REGULAR_EXPRESSION "nestedThenDead|nestedElseDead")
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_read_modify_add
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_read_modify_add
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[0\\] : float = values\\[0\\] \\+ values\\[3\\] : float")
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_read_modify_sub
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_read_modify_sub
  PROPERTIES PASS_REGULAR_EXPRESSION "assign values\\[0\\] : float = values\\[0\\] - values\\[3\\] : float")
add_test(NAME cglc_check_optimizer_branch_read_modify_boundary_hir_return_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BRANCH_READ_MODIFY_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_branch_read_modify_boundary_hir_return_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[4\\] : float = -values\\[0\\] : float"
    FAIL_REGULAR_EXPRESSION "99\\.0|100\\.0|101\\.0")
set(CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/OptimizerScalarVectorBoundaryHIRShader.cgl)
add_test(NAME cglc_check_optimizer_scalar_vector_boundary_hir
  COMMAND cglc check ${CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_optimizer_scalar_constructor_boundary_hir_folded_operand
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_scalar_constructor_boundary_hir_folded_operand
  PROPERTIES PASS_REGULAR_EXPRESSION "decl float foldedScalar = float\\(3\\) : float")
add_test(NAME cglc_check_optimizer_scalar_constructor_boundary_hir_dynamic_cast
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_scalar_constructor_boundary_hir_dynamic_cast
  PROPERTIES PASS_REGULAR_EXPRESSION "decl int signedValue = int\\(source\\) : int")
add_test(NAME cglc_check_optimizer_vector_local_dead_local_cleanup_hir
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_vector_local_dead_local_cleanup_hir
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl vec4 lifted = base \\+ vec4\\(foldedScalar, 0\\.5, 0\\.25, 0\\.0\\) : vec4"
    FAIL_REGULAR_EXPRESSION "unusedVector")
add_test(NAME cglc_check_optimizer_vector_storage_write_hir_vec4
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_vector_storage_write_hir_vec4
  PROPERTIES PASS_REGULAR_EXPRESSION "assign vectors\\[1\\] : vec4 = lifted : vec4")
add_test(NAME cglc_check_optimizer_vector_storage_write_hir_vec3
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_vector_storage_write_hir_vec3
  PROPERTIES PASS_REGULAR_EXPRESSION "assign vectors3\\[1\\] : vec3 = lifted3 \\+ vec3\\(0\\.25, 0\\.25, 0\\.0\\) : vec3")
add_test(NAME cglc_check_optimizer_arithmetic_comparison_boundary_hir
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_SCALAR_VECTOR_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_optimizer_arithmetic_comparison_boundary_hir
  PROPERTIES PASS_REGULAR_EXPRESSION "decl bool useLifted = signedBack > foldedScalar : bool")
set(CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ArrayOptimizerBoundaryHIRShader.cgl)
add_test(NAME cglc_check_array_optimizer_boundary_hir
  COMMAND cglc check ${CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_array_optimizer_boundary_hir_folded_dimensions
  COMMAND cglc dump-ir ${CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_array_optimizer_boundary_hir_folded_dimensions
  PROPERTIES
    PASS_REGULAR_EXPRESSION "const int COUNT = 3 folded 3.*const int ROWS = 2 folded 2")
add_test(NAME cglc_check_array_optimizer_boundary_hir_helper_parameter_write
  COMMAND cglc dump-ir ${CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_array_optimizer_boundary_hir_helper_parameter_write
  PROPERTIES
    PASS_REGULAR_EXPRESSION "fn rewriteWeight\\(float\\[COUNT\\] samples, int slot, float incoming\\) -> float.*assign samples\\[slot\\] : float = samples\\[0\\] \\+ incoming : float")
add_test(NAME cglc_check_array_optimizer_boundary_hir_local_array_writes
  COMMAND cglc dump-ir ${CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_array_optimizer_boundary_hir_local_array_writes
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float\\[COUNT\\] weights.*assign weights\\[0\\] : float = values\\[0\\] : float.*assign weights\\[2\\] : float = values\\[2\\] : float")
add_test(NAME cglc_check_array_optimizer_boundary_hir_dynamic_nested_read
  COMMAND cglc dump-ir ${CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_array_optimizer_boundary_hir_dynamic_nested_read
  PROPERTIES
    PASS_REGULAR_EXPRESSION "fn readGrid\\(float\\[ROWS\\]\\[COUNT\\] grid, int row, int col\\) -> float.*return grid\\[row\\]\\[col\\] : float.*decl float selected = readGrid\\(grid, row, col\\)")
add_test(NAME cglc_check_array_optimizer_boundary_hir_storage_side_effects
  COMMAND cglc dump-ir ${CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_array_optimizer_boundary_hir_storage_side_effects
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[slot\\] : float = updated : float.*assign values\\[8\\] : float = selected : float.*assign values\\[9\\] : float = weights\\[slot\\] : float")
add_test(NAME cglc_check_array_optimizer_boundary_hir_dead_local_cleanup
  COMMAND cglc dump-ir ${CROSSGL_ARRAY_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_array_optimizer_boundary_hir_dead_local_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[9\\] : float = weights\\[slot\\] : float"
    FAIL_REGULAR_EXPRESSION "deadParameterLocal|deadMainLocal")
set(CROSSGL_STRUCT_OPTIMIZER_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/StructOptimizerBoundaryHIRShader.cgl)
add_test(NAME cglc_check_struct_optimizer_boundary_hir
  COMMAND cglc check ${CROSSGL_STRUCT_OPTIMIZER_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_struct_optimizer_boundary_hir_folded_array_field_index
  COMMAND cglc dump-ir ${CROSSGL_STRUCT_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_struct_optimizer_boundary_hir_folded_array_field_index
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float foldedWeight = particles\\[0\\]\\.transform\\.weights\\[2\\] : float"
    FAIL_REGULAR_EXPRESSION "weights\\[1 \\+ 1\\]")
add_test(NAME cglc_check_struct_optimizer_boundary_hir_dynamic_nested_field
  COMMAND cglc dump-ir ${CROSSGL_STRUCT_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_struct_optimizer_boundary_hir_dynamic_nested_field
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float selectedWeight = particles\\[dynamicSlot\\]\\.transform\\.weights\\[dynamicWeight\\] : float.*decl vec3 nestedPosition = particles\\[0\\]\\.transform\\.position : vec3")
add_test(NAME cglc_check_struct_optimizer_boundary_hir_runtime_struct_array
  COMMAND cglc dump-ir ${CROSSGL_STRUCT_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_struct_optimizer_boundary_hir_runtime_struct_array
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl vec3 runtimePosition = payloads\\.particles\\[0\\]\\.position : vec3.*decl float runtimeMass = payloads\\.particles\\[dynamicRuntime\\]\\.mass : float")
add_test(NAME cglc_check_struct_optimizer_boundary_hir_storage_side_effects
  COMMAND cglc dump-ir ${CROSSGL_STRUCT_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_struct_optimizer_boundary_hir_storage_side_effects
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign particles\\[1\\]\\.transform\\.weights\\[0\\] : float = foldedWeight \\+ selectedWeight : float.*assign particles\\[1\\]\\.transform\\.position : vec3 = nestedPosition \\+ runtimePosition : vec3.*assign payloads\\.particles\\[dynamicSlot\\]\\.position : vec3 = particles\\[1\\]\\.transform\\.position : vec3.*assign payloads\\.particles\\[dynamicSlot\\]\\.mass : float = payloads\\.count \\+ particles\\[1\\]\\.transform\\.weights\\[0\\] : float"
    FAIL_REGULAR_EXPRESSION "deadFieldRead")
set(CROSSGL_WORKGROUP_SHARED_OPTIMIZER_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/WorkgroupSharedOptimizerBoundaryHIRShader.cgl)
add_test(NAME cglc_check_workgroup_shared_optimizer_boundary_hir
  COMMAND cglc check ${CROSSGL_WORKGROUP_SHARED_OPTIMIZER_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_workgroup_shared_optimizer_boundary_hir_metadata
  COMMAND cglc dump-ir ${CROSSGL_WORKGROUP_SHARED_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_workgroup_shared_optimizer_boundary_hir_metadata
  PROPERTIES
    PASS_REGULAR_EXPRESSION "const int TILE_WIDTH = 4 folded 4.*const int WORKGROUP_X = 8 folded 8.*workgroup_size 8, 2, 1 source WORKGROUP_X, 2, 1")
add_test(NAME cglc_check_workgroup_shared_optimizer_boundary_hir_resource
  COMMAND cglc dump-ir ${CROSSGL_WORKGROUP_SHARED_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_workgroup_shared_optimizer_boundary_hir_resource
  PROPERTIES
    PASS_REGULAR_EXPRESSION "resource buffer float\\* values set 0 binding 0.*resource buffer int\\* indices set 0 binding 1.*resource shared float\\[TILE_WIDTH\\] tile local")
add_test(NAME cglc_check_workgroup_shared_optimizer_boundary_hir_side_effects
  COMMAND cglc dump-ir ${CROSSGL_WORKGROUP_SHARED_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_workgroup_shared_optimizer_boundary_hir_side_effects
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign tile\\[slot\\] : float = base \\+ 1\\.0 : float.*decl float sharedValue = tile\\[slot\\] : float.*assign values\\[slot\\] : float = sharedValue : float.*assign values\\[1\\] : float = tile\\[1\\] : float"
    FAIL_REGULAR_EXPRESSION "deadLocal")
set(CROSSGL_COMPUTE_BUILTIN_OPTIMIZER_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ComputeBuiltinOptimizerBoundaryHIRShader.cgl)
add_test(NAME cglc_check_compute_builtin_optimizer_boundary_hir
  COMMAND cglc check ${CROSSGL_COMPUTE_BUILTIN_OPTIMIZER_BOUNDARY_HIR_SHADER})
add_test(NAME cglc_check_compute_builtin_optimizer_boundary_hir_live_locals
  COMMAND cglc dump-ir ${CROSSGL_COMPUTE_BUILTIN_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_compute_builtin_optimizer_boundary_hir_live_locals
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl uint globalX = gl_GlobalInvocationID\\.x.*decl uint localY = gl_LocalInvocationID\\.y.*decl uint groupZ = gl_WorkGroupID\\.z")
add_test(NAME cglc_check_compute_builtin_optimizer_boundary_hir_live_writes
  COMMAND cglc dump-ir ${CROSSGL_COMPUTE_BUILTIN_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_compute_builtin_optimizer_boundary_hir_live_writes
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign ids\\[0\\] : uint = globalX \\+ localY : uint.*assign ids\\[1\\] : uint = gl_WorkGroupID\\.x \\+ gl_LocalInvocationID\\.x.*assign values\\[2\\] : float = float\\(groupZ \\+ gl_GlobalInvocationID\\.z\\) : float.*assign values\\[3\\] : float = values\\[1\\] \\+ float\\(gl_WorkGroupID\\.y\\) : float")
add_test(NAME cglc_check_compute_builtin_optimizer_boundary_hir_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_COMPUTE_BUILTIN_OPTIMIZER_BOUNDARY_HIR_SHADER} --stage hir)
set_tests_properties(cglc_check_compute_builtin_optimizer_boundary_hir_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "assign values\\[3\\] : float = values\\[1\\] \\+ float\\(gl_WorkGroupID\\.y\\) : float"
    FAIL_REGULAR_EXPRESSION "deadGlobalLocal|deadFloatLocal")
add_test(NAME cglc_check_scalar_constructor_compute
  COMMAND cglc check ${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER})
add_test(NAME cglc_check_scalar_constructor_compute_hir_casts
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl int signedValue = int\\(source\\) : int[^\n]*\n      decl uint unsignedValue = uint\\(source\\) : uint[^\n]*\n      decl float signedBack = float\\(signedValue\\) : float[^\n]*\n      decl float unsignedBack = float\\(unsignedValue\\) : float[^\n]*\n      assign values\\[1\\] : float = signedBack \\+ unsignedBack : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector_local_compute
  COMMAND cglc check ${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER})
add_test(NAME cglc_check_vector_local_compute_hir_construct_vector_arithmetic
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl vec4 color = vec4\\(values\\[0\\], values\\[1\\], values\\[2\\], 1\\.0\\) : vec4[^\n]*\n      decl vec4 lifted = color \\+ vec4\\(0\\.5, 0\\.5, 0\\.5, 0\\.0\\) : vec4[^\n]*\n      assign values\\[0\\] : float = lifted\\.x : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector_swizzle_compute
  COMMAND cglc check ${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER})
add_test(NAME cglc_check_vector_swizzle_compute_hir_member_types
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign values\\[2\\] : float = rgba\\.b : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector_scalar_compute
  COMMAND cglc check ${CROSSGL_VECTOR_SCALAR_COMPUTE_SHADER})
add_test(NAME cglc_check_vector_scalar_cast_compute
  COMMAND cglc check ${CROSSGL_VECTOR_SCALAR_CAST_COMPUTE_SHADER})
add_test(NAME cglc_check_matrix_scalar_arithmetic_compute
  COMMAND cglc check ${CROSSGL_MATRIX_SCALAR_ARITHMETIC_COMPUTE_SHADER})
add_test(NAME cglc_check_matrix_scalar_arithmetic_hir_types
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MATRIX_SCALAR_ARITHMETIC_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl mat3 scaled = transform \\* 2\\.0 : mat3[^\n]*\n      decl mat3 rescaled = 0\\.5 \\* transform : mat3[^\n]*\n      decl mat3 inferred = transform \\* 0\\.25 : mat3[^\n]*\n      assign inferred : mat3 = inferred \\* 4\\.0 : mat3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector_buffer_compute
  COMMAND cglc check ${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER})
add_test(NAME cglc_check_vector_buffer_compute_hir_vec4_load_store
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl vec4 lifted = color \\+ vec4\\(0\\.5, 0\\.5, 0\\.5, 0\\.0\\) : vec4[^\n]*\n      assign values\\[1\\] : vec4 = lifted : vec4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_buffer_pointer_helper_param
  COMMAND cglc check ${CROSSGL_STORAGE_BUFFER_POINTER_HELPER_PARAM_SHADER})
add_test(NAME cglc_check_storage_buffer_pointer_helper_param_hir
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_POINTER_HELPER_PARAM_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=resource buffer float\\* values set 0 binding 0[^\n]*\n    resource buffer vec4\\* vectors set 0 binding 1[^\n]*\n    fn writeScalar\\(float\\* dst, float value\\) -> void[^\n]*\n      assign dst\\[0\\] : float = value : float[^\n]*\n      return[^\n]*\n    fn writeVector\\(vec4\\* dst, vec4 value\\) -> void[^\n]*\n      assign dst\\[1\\] : vec4 = value : vec4[^\n]*\n      return[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl float scalar = values\\[1\\] \\+ 2\\.0 : float[^\n]*\n      decl vec4 vector = vectors\\[0\\] \\+ vec4\\(0\\.25, 0\\.5, 0\\.75, 1\\.0\\) : vec4[^\n]*\n      expr writeScalar\\(values, scalar\\)[^\n]*\n      expr writeVector\\(vectors, vector\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector3_buffer_compute
  COMMAND cglc check ${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER})
add_test(NAME cglc_check_vector3_buffer_compute_hir_vec3_load_store
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl vec3 lifted = color \\+ vec3\\(0\\.5, 0\\.5, 0\\.0\\) : vec3[^\n]*\n      assign values\\[1\\] : vec3 = lifted : vec3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_struct_buffer_compute
  COMMAND cglc check ${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER})
add_test(NAME cglc_check_struct_buffer_compute_hir_struct_field_access
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct Particle[^\n]*\n    vec3 position[^\n]*\n    float mass[^\n]*\n    vec4 velocity[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer Particle\\* particles set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl float mass = particles\\[0\\]\\.mass : float[^\n]*\n      assign particles\\[1\\]\\.mass : float = mass \\+ 1\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_struct_vector_buffer_compute
  COMMAND cglc check ${CROSSGL_STRUCT_VECTOR_BUFFER_COMPUTE_SHADER})
add_test(NAME cglc_check_struct_array_field_compute
  COMMAND cglc check ${CROSSGL_STRUCT_ARRAY_FIELD_COMPUTE_SHADER})
add_test(NAME cglc_check_struct_array_field_compute_hir_fixed_array_field
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_ARRAY_FIELD_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct Particle[^\n]*\n    float\\[4\\] weights[^\n]*\n    float mass[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer Particle\\* particles set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl float firstWeight = particles\\[0\\]\\.weights\\[0\\] : float[^\n]*\n      assign particles\\[1\\]\\.mass : float = firstWeight : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_struct_constant_array_field_compute
  COMMAND cglc check ${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER})
add_test(NAME cglc_check_struct_constant_array_field_compute_hir_symbolic_array_field
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct Particle[^\n]*\n    float\\[WEIGHT_COUNT\\] weights[^\n]*\n    float mass[^\n]*\n  const int WEIGHT_COUNT = 4 folded 4[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer Particle\\* particles set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl float firstWeight = particles\\[0\\]\\.weights\\[0\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_struct_vector_array_field_compute
  COMMAND cglc check ${CROSSGL_STRUCT_VECTOR_ARRAY_FIELD_COMPUTE_SHADER})
add_test(NAME cglc_check_struct_vector_array_field_compute_hir_vector_array_field
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_VECTOR_ARRAY_FIELD_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct Particle[^\n]*\n    vec3\\[2\\] positions[^\n]*\n    float mass[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer Particle\\* particles set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl vec3 lifted = particles\\[0\\]\\.positions\\[1\\] : vec3[^\n]*\n      assign particles\\[1\\]\\.positions\\[0\\] : vec3 = lifted : vec3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_struct_nested_field_compute
  COMMAND cglc check ${CROSSGL_STRUCT_NESTED_FIELD_COMPUTE_SHADER})
add_test(NAME cglc_check_struct_nested_field_compute_hir_nested_field_access
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_NESTED_FIELD_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct Transform[^\n]*\n    vec3 position[^\n]*\n  struct Particle[^\n]*\n    Transform transform[^\n]*\n    float mass[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer Particle\\* particles set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl vec3 position = particles\\[0\\]\\.transform\\.position : vec3[^\n]*\n      decl vec3 lifted = position \\+ vec3\\(1\\.0, 0\\.0, 0\\.0\\) : vec3[^\n]*\n      assign particles\\[1\\]\\.transform\\.position : vec3 = lifted : vec3[^\n]*\n      assign particles\\[1\\]\\.mass : float = lifted\\.x : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_struct_nested_array_field_compute
  COMMAND cglc check ${CROSSGL_STRUCT_NESTED_ARRAY_FIELD_COMPUTE_SHADER})
add_test(NAME cglc_check_struct_nested_array_field_compute_hir_nested_array_field
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_NESTED_ARRAY_FIELD_COMPUTE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct Transform[^\n]*\n    vec3 position[^\n]*\n    float weight[^\n]*\n  struct Particle[^\n]*\n    Transform\\[2\\] history[^\n]*\n    float mass[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer Particle\\* particles set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl vec3 previous = particles\\[0\\]\\.history\\[1\\]\\.position : vec3[^\n]*\n      assign particles\\[1\\]\\.history\\[0\\]\\.position : vec3 = previous : vec3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_function_parameter_array
  COMMAND cglc check ${CROSSGL_FUNCTION_PARAMETER_ARRAY_SHADER})
add_test(NAME cglc_check_function_parameter_array_hir_parameters
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn main\\(float scale, vec3 direction, mat4 transform, float\\[4\\] taps, float\\[COLS\\] weights, vec4\\[ROWS\\]\\[COLS\\] grid\\) -> void"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_function_parameter_array_hir_call_arguments
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=expr consumeTaps\\(taps\\)[^\n]*\n      expr consumeWeights\\(weights\\)[^\n]*\n      expr consumeGrid\\(grid\\)[^\n]*\n      expr consumeWeights\\(particles\\[0\\]\\.weights\\)[^\n]*\n      expr consumeRows\\(particles\\[0\\]\\.payload\\.lanes\\)[^\n]*\n      expr consumeGrid\\(particles\\[0\\]\\.grid\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_function_parameter_array
  COMMAND cglc check ${CROSSGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER})
add_test(NAME cglc_check_local_function_parameter_array_hir_parameter
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn readWeight\\(float\\[COUNT\\] values, int index\\) -> float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_function_parameter_array_hir_decl
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float\\[COUNT\\] weights"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_function_parameter_array_hir_call_argument
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float first = readWeight\\(weights, 0\\) \\* scale : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_void_parameter_list
  COMMAND cglc check ${CROSSGL_VOID_PARAMETER_LIST_SHADER})
add_test(NAME cglc_check_void_parameter_list_hir_zero_parameters
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VOID_PARAMETER_LIST_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn helper\\(\\) -> float[^\n\r]*[\n\r]+      return 1\\.0 : float[^\n\r]*[\n\r]+    fn main\\(\\) -> void[^\n\r]*[\n\r]+      decl float value = helper\\(\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_array_mutation_hir
  COMMAND cglc check ${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER})
add_test(NAME cglc_check_local_array_mutation_hir_helper_parameter
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn rewriteWeight\\(float\\[COUNT\\] samples\\) -> float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_array_mutation_hir_local_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign weights\\[0\\] : float = values\\[0\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_array_mutation_hir_second_local_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign weights\\[1\\] : float = values\\[1\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_array_mutation_hir_helper_parameter_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign samples\\[0\\] : float = samples\\[1\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_array_mutation_hir_helper_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float first = rewriteWeight\\(weights\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_folded_nested_array_hir
  COMMAND cglc check ${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER})
add_test(NAME cglc_check_folded_nested_array_hir_constants
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=const int BASE_COLS = 2 folded 2[^\n]*\n  const int COLS = 3 folded 3[^\n]*\n  const int ROWS = 2 folded 2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_folded_nested_array_hir_helper_parameter
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn readGrid\\(float\\[ROWS\\]\\[COLS\\] grid, int row, int col\\) -> float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_folded_nested_array_hir_local_decl
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float\\[ROWS\\]\\[COLS\\] grid"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_folded_nested_array_hir_helper_nested_read
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=return grid\\[row\\]\\[col\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_folded_nested_array_hir_first_nested_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign grid\\[0\\]\\[0\\] : float = values\\[0\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_folded_nested_array_hir_second_nested_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign grid\\[1\\]\\[2\\] : float = values\\[1\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_folded_nested_array_hir_helper_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float selected = readGrid\\(grid, 1, 2\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/BlocksAndFoldedArrayDimensionsShader.cgl)
add_test(NAME cglc_check_blocks_and_folded_array_dimensions
  COMMAND cglc check ${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER})
add_test(NAME cglc_check_blocks_and_folded_array_dimensions_field
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=float\\[BASE\\*2\\] weights"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_blocks_and_folded_array_dimensions_resource
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=resource texture sampler2D\\[BASE\\*2\\] maps"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_blocks_and_folded_array_dimensions_parameter
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn readSample\\(float\\[BASE\\*2\\] samples, int index\\) -> float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_blocks_and_folded_array_dimensions_block
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=block"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_blocks_and_folded_array_dimensions_local
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float\\[BASE\\*2\\] blockValues"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_blocks_and_folded_array_dimensions_inner_shadow
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float sample = values\\[0\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_blocks_and_folded_array_dimensions_outer_shadow
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BLOCKS_AND_FOLDED_ARRAY_DIMENSIONS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=assign sample : int = 2 : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_dynamic_nested_array_hir
  COMMAND cglc check ${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER})
add_test(NAME cglc_check_dynamic_nested_array_hir_helper_parameter
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=fn readGrid\\(float\\[ROWS\\]\\[COLS\\] grid, int row, int col\\) -> float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_dynamic_nested_array_hir_helper_dynamic_read
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=return grid\\[row\\]\\[col\\] : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_dynamic_nested_array_hir_dynamic_row_source
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl int row = int\\(values\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_dynamic_nested_array_hir_dynamic_col_source
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl int col = int\\(values\\[1\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_dynamic_nested_array_hir_helper_dynamic_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl float selected = readGrid\\(grid, row, col\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_buffer_struct_array_field_descriptor_array
  COMMAND cglc check ${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_FIELD_DESCRIPTOR_ARRAY_SHADER})
add_test(NAME cglc_check_storage_buffer_struct_array_field_descriptor_array_hir_field_paths
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_FIELD_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct Transform[^\n]*\n    vec3 position[^\n]*\n    float weight[^\n]*\n  struct Particle[^\n]*\n    float\\[4\\] weights[^\n]*\n    Transform\\[2\\] history[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer Particle\\*\\[2\\] particles set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl float previousWeight = particles\\[1\\]\\[0\\]\\.weights\\[2\\] : float[^\n]*\n      decl vec3 previousPosition = particles\\[1\\]\\[0\\]\\.history\\[1\\]\\.position : vec3[^\n]*\n      assign particles\\[0\\]\\[1\\]\\.weights\\[3\\] : float = previousWeight \\+ particles\\[0\\]\\[1\\]\\.history\\[0\\]\\.weight : float[^\n]*\n      assign particles\\[0\\]\\[1\\]\\.history\\[0\\]\\.position : vec3 = previousPosition : vec3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_runtime_array
  COMMAND cglc check ${CROSSGL_RUNTIME_ARRAY_SHADER})
add_test(NAME cglc_check_runtime_vector_array
  COMMAND cglc check ${CROSSGL_RUNTIME_VECTOR_ARRAY_SHADER})
add_test(NAME cglc_check_runtime_struct_array
  COMMAND cglc check ${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER})
add_test(NAME cglc_check_runtime_struct_array_hir_runtime_struct_array_refs
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=struct TailParticle[^\n]*\n    vec3 position[^\n]*\n    float mass[^\n]*\n  struct RuntimeStructPayload[^\n]*\n    float count[^\n]*\n    TailParticle\\[\\] particles[^\n]*\n  stage compute entry main[^\n]*\n    workgroup_size 1, 1, 1[^\n]*\n    resource buffer RuntimeStructPayload\\* payloads set 0 binding 0[^\n]*\n    fn main\\(\\) -> void[^\n]*\n      decl vec3 firstPosition = payloads\\.particles\\[0\\]\\.position : vec3[^\n]*\n      decl float firstMass = payloads\\.particles\\[0\\]\\.mass : float[^\n]*\n      assign payloads\\.count : float = firstMass : float[^\n]*\n      assign payloads\\.particles\\[1\\]\\.position : vec3 = firstPosition \\+ vec3\\(1\\.0, 0\\.0, 0\\.0\\) : vec3[^\n]*\n      assign payloads\\.particles\\[1\\]\\.mass : float = payloads\\.count \\+ 1\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_runtime_array_non_final_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NON_FINAL_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_runtime_array_nested_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NESTED_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.tail.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_runtime_array_dynamic_outer_index
  COMMAND cglc check ${CROSSGL_RUNTIME_ARRAY_DYNAMIC_OUTER_INDEX_SHADER})
add_test(NAME cglc_check_runtime_resource_array_unsupported
  COMMAND cglc check ${CROSSGL_RUNTIME_RESOURCE_ARRAY_UNSUPPORTED_SHADER})
add_test(NAME cglc_check_duplicate_resource_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_RESOURCE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-resource
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=19"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate resource 'params'|message=stage 'compute'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_binding_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_BINDING_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-resource-binding
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate resource binding 3|message=set 0|message=stage 'compute'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_field_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_FIELD_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=9"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate field 'value'|message=struct 'Params'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_constant_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_CONSTANT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-constant
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=3"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate constant 'COUNT'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_top_level_function_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_TOP_LEVEL_FUNCTION_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-function
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=8"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate top-level function 'helper'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_stage_function_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_STAGE_FUNCTION_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-stage-function
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=10"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate function 'main'|message=stage 'compute'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_shared_resource_binding_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_SHARED_RESOURCE_BINDING_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.shared-resource-binding
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=shared resource 'tile'|message=cannot use descriptor set or binding layout"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_empty_stage_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_EMPTY_STAGE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.empty-stage
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=2|location.column=3"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=stage 'compute' has no functions"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_no_stages_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NO_STAGES_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.no-stages
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=1|location.column=8"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=shader has no compileable stages"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
function(crossgl_add_native_v0_unsupported_failure test_name input line column message_contains)
  add_test(NAME ${test_name}
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${input}
      -DMODE=check-failure
      -DEXPECTED_DIAGNOSTIC=spec.unsupported-for-native-v0
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
      "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=${line}|location.column=${column}"
      "-DEXPECTED_DIAGNOSTIC_FIELDS_GREATER_THAN=location.length=0"
      "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=${message_contains}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
endfunction()
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_extended_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_EXTENDED_STAGE_SHADER}
  2
  3
  "message=stage 'geometry'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_enum_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_ENUM_SHADER}
  2
  3
  "message=enum declarations|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_stage_enum_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_STAGE_ENUM_SHADER}
  3
  5
  "message=enum declarations|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_struct_enum_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_STRUCT_ENUM_SHADER}
  3
  5
  "message=enum declarations|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_generic_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_GENERIC_SHADER}
  2
  3
  "message=generic declarations|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_impl_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_IMPL_SHADER}
  2
  3
  "message=impl declarations|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_import_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_IMPORT_SHADER}
  1
  1
  "message=source import declarations|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_colon_var_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_COLON_VAR_SHADER}
  3
  5
  "message=colon-style variable declarations|message=native v0|message=decl.colon-var")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_match_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_MATCH_SHADER}
  5
  7
  "message=match/pattern control statements|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_switch_failure
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadUnsupportedSwitchShader.cgl
  7
  7
  "message=restricted switch/case/default statements|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_switch_duplicate_case_label_failure
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadUnsupportedSwitchDuplicateCaseLabelShader.cgl
  7
  7
  "message=restricted switch/case/default statements|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_switch_grouped_labels_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_SWITCH_GROUPED_LABELS_COMPAT_SHADER}
  7
  7
  "message=restricted switch/case/default statements|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_switch_incompatible_case_label_type_failure
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadUnsupportedSwitchIncompatibleCaseLabelTypeShader.cgl
  7
  7
  "message=restricted switch/case/default statements|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_switch_non_terminal_break_failure
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadUnsupportedSwitchNonTerminalBreakShader.cgl
  7
  7
  "message=restricted switch/case/default statements|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_for_in_failure
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadUnsupportedForInShader.cgl
  5
  7
  "message=for-in loop statements|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_malformed_for_header_failure
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadMalformedForHeaderShader.cgl
  5
  7
  "message=malformed control headers|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_preprocessor_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_PREPROCESSOR_SHADER}
  1
  1
  "message=preprocessor directives|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_line_splicing_preprocessor_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_LINE_SPLICING_PREPROCESSOR_SHADER}
  1
  21
  "message=line-splicing/preprocessor continuation syntax|message=native v0|message=decl.line-splicing-preprocessor")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_ray_any_hit_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_RAY_ANY_HIT_STAGE_SHADER}
  2
  3
  "message=stage 'ray_any_hit'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_ray_callable_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_RAY_CALLABLE_STAGE_SHADER}
  2
  3
  "message=stage 'ray_callable'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_ray_closest_hit_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_RAY_CLOSEST_HIT_STAGE_SHADER}
  2
  3
  "message=stage 'ray_closest_hit'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_ray_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_RAY_STAGE_SHADER}
  2
  3
  "message=stage 'ray_generation'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_ray_intersection_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_RAY_INTERSECTION_STAGE_SHADER}
  2
  3
  "message=stage 'ray_intersection'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_ray_miss_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_RAY_MISS_STAGE_SHADER}
  2
  3
  "message=stage 'ray_miss'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_tessellation_stage_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_TESSELLATION_STAGE_SHADER}
  2
  3
  "message=stage 'tessellation_control'|message=native v0")
crossgl_add_native_v0_unsupported_failure(
  cglc_check_unsupported_native_v0_trait_failure
  ${CROSSGL_CHECK_FAILURE_UNSUPPORTED_TRAIT_SHADER}
  2
  3
  "message=trait declarations|message=native v0")
add_test(NAME cglc_check_malformed_scientific_float_literal_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadMalformedScientificFloatLiteralShader.cgl
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=lex.malformed-float-literal
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=27"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=malformed scientific float literal|message=exponent requires"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_malformed_hex_float_literal_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadMalformedHexFloatLiteralShader.cgl
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=lex.malformed-float-literal
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=27"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=malformed hexadecimal float literal|message=binary exponent"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_named_void_parameter_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NAMED_VOID_PARAMETER_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=parse.invalid-void-parameter
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=void parameter list must be exactly 'void'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_mixed_void_parameter_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MIXED_VOID_PARAMETER_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=parse.invalid-void-parameter
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=void parameter list must be exactly 'void'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_location_alias_resource_binding_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_LOCATION_ALIAS_RESOURCE_BINDING_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-resource-binding
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=sema.duplicate-resource-binding|diagnostics.0.location.line=7|diagnostics.0.location.column=21"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=duplicate resource binding 0|diagnostics.0.message=set 0|diagnostics.0.message=stage 'compute'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_conflicting_register_binding_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_CONFLICTING_REGISTER_BINDING_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=parse.conflicting-resource-binding
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=34"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=register|message=binding"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_conflicting_register_binding_reverse_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_CONFLICTING_REGISTER_BINDING_REVERSE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=parse.conflicting-resource-binding
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=35"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=binding|message=register"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_unsupported_native_v0_var_address_space_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_UNSUPPORTED_VAR_ADDRESS_SPACE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=parse.unsupported-var-address-space
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=5"
    "-DEXPECTED_DIAGNOSTIC_FIELDS_GREATER_THAN=location.length=0"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=var<storage>|message=native v0|message=resource.var-address-space|message=var<workgroup>"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_break_outside_loop_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_BREAK_OUTSIDE_LOOP_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.break-placement
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=break statement|message=inside a loop"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_continue_outside_loop_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_CONTINUE_OUTSIDE_LOOP_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.continue-placement
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=9"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=continue statement|message=inside a loop"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_compute_discard_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_COMPUTE_DISCARD_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.discard-stage
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=discard statement|message=fragment stage|message=stage 'compute'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_top_level_discard_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TOP_LEVEL_DISCARD_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.discard-stage
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=5"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=discard statement|message=top-level functions|message=no fragment stage context"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_cbuffer_field_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_CBUFFER_FIELD_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-cbuffer-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=9"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate cbuffer field 'value'|message=ambiguous"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_recursive_storage_buffer_struct_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_RECURSIVE_STORAGE_BUFFER_STRUCT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-recursive-struct
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.next|message=finite storage-buffer layout"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=20"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample expects either texture and coordinates|message=got 1 operand"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_method_texture_sample_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_METHOD_TEXTURE_SAMPLE_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=29"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample expects either texture and coordinates|message=got 1 operand"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_load_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_LOAD_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.image-load-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=20"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=imageLoad expects storage image and coordinates|message=got 1 operand"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_store_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_STORE_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.image-store-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=8|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=imageStore expects storage image, coordinates, and value|message=got 2 operand"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_load_coordinate_shape_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_LOAD_COORDINATE_SHAPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.image-load-coordinates
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=imageLoad coordinates for 'image2D'|diagnostics.0.message=must be 'ivec2'|diagnostics.1.message=imageLoad coordinates for 'uimage2DArray'|diagnostics.1.message=must be 'ivec3'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_store_coordinate_shape_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_STORE_COORDINATE_SHAPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.image-store-coordinates
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=imageStore coordinates for 'image2D'|diagnostics.0.message=must be 'ivec2'|diagnostics.1.message=imageStore coordinates for 'uimage2DArray'|diagnostics.1.message=must be 'ivec3'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_sampled_texture_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_SAMPLED_TEXTURE_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.image-load-image
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=imageLoad first operand must be a storage image|diagnostics.0.message=got 'sampler2D'|diagnostics.1.message=imageStore first operand must be a storage image|diagnostics.1.message=got 'sampler2D'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_store_payload_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_STORE_PAYLOAD_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.image-store-value
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=3"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=must be 'vec4'|diagnostics.0.message=got 'ivec4'|diagnostics.1.message=must be 'ivec4'|diagnostics.1.message=got 'uvec4'|diagnostics.2.message=must be 'uvec4'|diagnostics.2.message=got 'vec4'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_value_use_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_VALUE_USE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.declaration-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=8|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=declaration initializer for 'stored' must be type 'vec4', got 'void'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_read_write_access_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_READ_WRITE_ACCESS_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.storage-image-read-only-store
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=sema.storage-image-read-only-store|diagnostics.0.location.line=10|diagnostics.0.location.column=18|diagnostics.1.severity=error|diagnostics.1.code=sema.storage-image-write-only-load|diagnostics.1.location.line=11|diagnostics.1.location.column=30"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=imageStore cannot write to read-only storage image 'readImages'|diagnostics.1.message=imageLoad cannot read from write-only storage image 'writeImages'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_format_layout_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_FORMAT_LAYOUT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.storage-image-format-layout
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=sema.storage-image-format-layout|diagnostics.1.severity=error|diagnostics.1.code=sema.storage-image-format-layout"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=storage-image layout format 'rgba32i' is incompatible|diagnostics.0.message=expected 'rgba32f'|diagnostics.1.message=storage-image layout format 'rgba32f' can only be used with storage-image resources"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_atomic_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_ATOMIC_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.storage-image-atomic-image-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=5"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=sema.storage-image-atomic-image-type|diagnostics.0.location.line=12|diagnostics.1.code=sema.storage-image-atomic-format|diagnostics.1.location.line=13|diagnostics.2.code=sema.storage-image-atomic-access|diagnostics.2.location.line=14|diagnostics.3.code=sema.storage-image-atomic-coordinates|diagnostics.3.location.line=15|diagnostics.4.code=sema.storage-image-atomic-value|diagnostics.4.location.line=16"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=signed or unsigned integer storage image|diagnostics.1.message=requires format 'r32i'|diagnostics.2.message=requires read-write storage image|diagnostics.3.message=must be 'ivec2'|diagnostics.4.message=must be 'uint'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_runtime_storage_image_descriptor_array_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_RUNTIME_STORAGE_IMAGE_ARRAY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.storage-image-runtime-descriptor-array
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=3"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=runtime/unsized storage-image descriptor arrays|diagnostics.0.message=colorImages|diagnostics.1.message=labelImages|diagnostics.2.message=maskAtlases"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=34"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_nonuniform_runtime_storage_image_descriptor_array_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NONUNIFORM_STORAGE_IMAGE_ARRAY_INDEX_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.storage-image-runtime-descriptor-array
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=runtime/unsized storage-image descriptor arrays|diagnostics.0.message=colorImages"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=34"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-texture
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=28"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample first operand must be a texture|message=got 'float'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_sampler_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_SAMPLER_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-sampler
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=38"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample second operand must be a raw sampler|message=explicit sampler form|message=got 'vec2'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_comparison_sampler_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COMPARISON_SAMPLER_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-sampler
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=32"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample second operand must be a raw sampler|message=got 'comparison_sampler'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_coordinates_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COORDINATES_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-coordinates
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=53"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample coordinates for 'sampler2D'|message=must be vec2|message=got 'vec3'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_ternary_texture_coordinates_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TERNARY_TEXTURE_COORDINATES_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-coordinates
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=43"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample coordinates for 'sampler2D'|message=must be vec2|message=got 'vec3'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_array_coordinates_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_ARRAY_COORDINATES_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-coordinates
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=53"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=texture sample coordinates for 'sampler2DArray'|message=must be vec3|message=got 'vec2'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_shadow_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_SHADOW_SAMPLE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-shadow
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=34"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=comparison texture 'sampler2DShadow'|message=must be sampled with textureCompare"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_lod_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_LOD_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-sample-lod
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=72"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureLod lod operand must be a scalar numeric value|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_mixed_swizzle_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MIXED_SWIZZLE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.invalid-swizzle
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=24"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=invalid vector swizzle 'xg'|message=type 'vec4'|message=xyzw, rgba, or stpq"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_width_swizzle_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_WIDTH_SWIZZLE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.invalid-swizzle
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=22"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=invalid vector swizzle 'z'|message=type 'vec2'|message=within the vector width"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_swizzle_assignment_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_SWIZZLE_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-swizzle-duplicate
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=13"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target swizzle 'xx' cannot write the same vector component more than once"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector_scalar_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_VECTOR_SCALAR_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.vector-scalar-arithmetic
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=26"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=float vector-scalar arithmetic requires the scalar operand to be float|message=vec4 + int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_compound_assignment_vector_scalar_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_COMPOUND_ASSIGNMENT_VECTOR_SCALAR_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.vector-scalar-arithmetic
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=16"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=float vector-scalar arithmetic requires the scalar operand to be float|message=vec4 + int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_matrix_scalar_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MATRIX_SCALAR_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.matrix-arithmetic
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=float matrix-scalar arithmetic requires the scalar operand to be float|message=mat3 * int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_scalar_matrix_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_SCALAR_MATRIX_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.matrix-arithmetic
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=float matrix-scalar arithmetic requires the scalar operand to be float|message=int * mat3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_matrix_modulo_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MATRIX_MODULO_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.matrix-arithmetic
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=matrix arithmetic does not support operator '%'|message=mat3 % float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_scalar_constructor_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_SCALAR_CONSTRUCTOR_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.scalar-constructor
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=25"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=scalar numeric constructor 'float'|message=requires a scalar numeric operand|message=got 'vec4'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector_constructor_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_VECTOR_CONSTRUCTOR_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.vector-constructor
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=18"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=vector constructor 'vec3'|message=expects 3 scalar components|message=got 2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_vector_constructor_operand_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_VECTOR_CONSTRUCTOR_OPERAND_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.vector-constructor
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=39"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=vector constructor 'vec3'|message=convertible to component type 'float'|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_matrix_constructor_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MATRIX_CONSTRUCTOR_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.matrix-constructor
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=18"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=matrix constructor 'mat2'|message=expects 4 scalar components|message=got 3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_matrix_constructor_operand_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MATRIX_CONSTRUCTOR_OPERAND_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.matrix-constructor
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=38"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=matrix constructor 'mat2'|message=convertible to component type 'float'|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_logical_not_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_LOGICAL_NOT_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.logical-operand-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=19"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=logical not operator requires a scalar bool operand|message=got 'int'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_logical_binary_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_LOGICAL_BINARY_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.logical-operand-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=20"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=logical operator '&&' requires scalar bool operands|message=int && bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_scalar_bool_arithmetic_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_SCALAR_BOOL_ARITHMETIC_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.binary-operand-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=19"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=arithmetic operator '+' requires numeric scalar, vector, or matrix operands|message=int + bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_relational_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_RELATIONAL_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.comparison-operand-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=23"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=comparison operator '<' requires scalar numeric operands|message=vec2 < vec2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_equality_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_EQUALITY_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.equality-operand-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=27"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=equality operator '==' requires scalar bool operands or scalar numeric operands|message=sampler2D == sampler2D"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_select_condition_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_SELECT_CONDITION_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.select-condition-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=select condition must be scalar bool|message=got 'int'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_select_branch_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_SELECT_BRANCH_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.select-branch-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=30"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=select branches must have compatible scalar, vector, or matrix value types|message=vec2 and vec3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_intrinsic_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_INTRINSIC_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.intrinsic-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=19"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=intrinsic call 'dot' expects exactly 2 arguments, got 1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_intrinsic_argument_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_INTRINSIC_ARGUMENT_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.intrinsic-argument-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=23"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=intrinsic call 'sin' argument 0 expects a floating-point scalar or vector type|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_intrinsic_compatibility_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_INTRINSIC_COMPATIBILITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.intrinsic-argument-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=39"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=intrinsic call 'dot' argument 1 expects a floating-point vector with width 2|message=got 'vec3'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_function_call_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_FUNCTION_CALL_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.function-call-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=22"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=function call 'identity' expects exactly 1 argument, got 0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_function_call_argument_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_FUNCTION_CALL_ARGUMENT_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.function-call-argument-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=30"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=function call 'identity' argument 0 expects 'vec2', got 'float'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_unresolved_function_call_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_UNRESOLVED_FUNCTION_CALL_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.unresolved-function-call
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=function call 'missingHelper' does not resolve to a declared function or supported intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_function_signature_return_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_FUNCTION_SIGNATURE_RETURN_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.function-signature-mismatch
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=9"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=stage 'compute' function list function 'helper' signature mismatch|message=previous signature 'float(float)'|message=current signature 'int(float)'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_top_level_function_signature_parameter_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TOP_LEVEL_FUNCTION_SIGNATURE_PARAMETER_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.function-signature-mismatch
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=9"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=top-level function list function 'utility' signature mismatch|message=previous signature 'float(float)'|message=current signature 'float(vec2)'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_duplicate_function_parameter_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DUPLICATE_FUNCTION_PARAMETER_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-function-parameter
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=35"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=stage 'compute' function list function 'helper' contains duplicate parameter 'value'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_declaration_initializer_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DECLARATION_INITIALIZER_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.declaration-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=19"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=declaration initializer for 'value' must be type 'int', got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_assignment_value_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_ASSIGNMENT_VALUE_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment RHS must be type 'int', got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_assignment_target_lvalue_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_ASSIGNMENT_TARGET_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-lvalue
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target must be an assignable storage location, got 'literal' expression"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_index_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_INDEX_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.index-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=27"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=index operator requires a scalar int or uint index|message=got 'float'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_index_base_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_INDEX_BASE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.index-base-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=24"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=index operator requires an array, storage-buffer pointer, descriptor array, or vector base|message=got 'float'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_constant_assignment_readonly_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_CONSTANT_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-readonly
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'COUNT' is read-only"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_compute_builtin_assignment_readonly_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_COMPUTE_BUILTIN_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-readonly
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'gl_GlobalInvocationID' is read-only"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_cbuffer_assignment_readonly_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_CBUFFER_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-readonly
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'exposure' is read-only"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_buffer_resource_assignment_readonly_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_BUFFER_RESOURCE_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-readonly
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'values' is a resource handle"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_resource_assignment_readonly_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_RESOURCE_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-readonly
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'colorMap' is a resource handle"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_storage_image_resource_assignment_readonly_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STORAGE_IMAGE_RESOURCE_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-readonly
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'colorImage' is a resource handle"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_array_assignment_lvalue_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_LOCAL_ARRAY_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-lvalue
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'weights' has array type 'float[4]'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_shared_array_assignment_lvalue_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_SHARED_ARRAY_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-lvalue
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target 'tile' has array type 'float[4]'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_struct_array_field_assignment_lvalue_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_STRUCT_ARRAY_FIELD_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-lvalue
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=8|location.column=20"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target member 'weights' has array type 'float[4]'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_nested_subarray_assignment_lvalue_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NESTED_SUBARRAY_ASSIGNMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.assignment-target-lvalue
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=11"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=assignment target indexed expression has array type 'float[3]'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_void_return_value_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_VOID_RETURN_VALUE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.return-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=14"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=return statement in void function must not return a value"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_missing_return_value_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MISSING_RETURN_VALUE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.return-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=return statement must return type 'float'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_return_value_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_RETURN_VALUE_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.return-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=14"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=return statement must return type 'float', got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_CHECK_FAILURE_INCREMENT_DECREMENT_OPERAND_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadIncrementDecrementOperandShader.cgl)
add_test(NAME cglc_check_increment_decrement_operand_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_INCREMENT_DECREMENT_OPERAND_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.increment-decrement-operand
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=increment/decrement updates require a scalar numeric local variable operand|message=got 'vec2'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_CHECK_FAILURE_INCREMENT_DECREMENT_EXPRESSION_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadIncrementDecrementExpressionShader.cgl)
add_test(NAME cglc_check_increment_decrement_expression_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_INCREMENT_DECREMENT_EXPRESSION_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.increment-decrement-update-form
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=23"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=increment/decrement is only defined as a standalone update|message=expression-valued uses are not defined"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_CHECK_FAILURE_WHILE_CONDITION_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadWhileConditionShader.cgl)
add_test(NAME cglc_check_while_condition_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_WHILE_CONDITION_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-condition-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=14"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=condition must be scalar bool|message=got 'int'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_do_while_condition_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_DO_WHILE_CONDITION_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.logical-operand-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=logical not operator requires a scalar bool operand|message=got 'int'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_unresolved_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_UNRESOLVED_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=11"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=array size for field 'weights'|message=struct 'Particle'|message=got 'WEIGHT_COUNT'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_zero_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_ZERO_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=52"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=array size for resource 'maps'|message=stage 'compute'|message=got '0'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_overflow_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_OVERFLOW_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=52"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=array size for resource 'maps'|message=positive integer literals|message=999999999999999999999999999999999999999999"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_expression_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_EXPRESSION_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=52"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=array size for resource 'maps'|message=pure folded top-level int/uint constant expressions|message=MAP_COUNT+runtimeCount"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_bool_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_BOOL_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=52"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=array size for resource 'maps'|message=pure folded top-level int/uint constant expressions|message=got 'MAP_COUNT'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_CHECK_FAILURE_NEGATIVE_ARRAY_SIZE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadNegativeArraySizeShader.cgl)
add_test(NAME cglc_check_negative_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NEGATIVE_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=array size for resource 'maps'|message=pure folded top-level int/uint constant expressions|message=got '-COUNT'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_local_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_LOCAL_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=local declaration 'runtimeWeights'|diagnostics.0.message=got '[]'|diagnostics.1.message=local declaration 'unresolvedWeights'|diagnostics.1.message=got 'COUNT'"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=7"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_CHECK_FAILURE_MUTABLE_ARRAY_SIZE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/check-failures/BadMutableArraySizeShader.cgl)
add_test(NAME cglc_check_mutable_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MUTABLE_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=local declaration 'weights'|message=pure folded top-level int/uint constant expressions|message=got 'count'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_parameter_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_PARAMETER_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=parameter 'weights'|message=stage 'compute' function 'main'|message=got 'COUNT'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_zero_parameter_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_ZERO_PARAMETER_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=3|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=parameter 'weights'|message=stage 'compute' function 'main'|message=got '0'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_bool_parameter_array_size_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_BOOL_PARAMETER_ARRAY_SIZE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.array-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=4|location.column=21"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=parameter 'weights'|message=stage 'compute' function 'main'|message=pure folded top-level int/uint constant expressions|message=got 'COUNT'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_nonuniform_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NONUNIFORM_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.nonuniform-index-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=5|location.column=28"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=nonuniform expects exactly one descriptor index operand"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_nonuniform_placement_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NONUNIFORM_PLACEMENT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.nonuniform-index-placement
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=19"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=nonuniform can only annotate the index operand|message=descriptor resource array access"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_nonuniform_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_NONUNIFORM_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.nonuniform-index-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=6|location.column=39"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=nonuniform descriptor indices must be scalar int or uint values|message=got 'float'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_arity_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COMPARE_ARITY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-arity
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=11"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompare expects texture, sampler, coordinates, and depth|message=got 3 operand"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_texture_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COMPARE_TEXTURE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-texture
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=26"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompare first operand must be a comparison texture|message=got 'sampler2D'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_coordinates_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COMPARE_COORDINATES_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-coordinates
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=52"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompare coordinates for 'sampler2DShadow'|message=must be vec2|message=got 'vec3'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_depth_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COMPARE_DEPTH_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-depth
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=68"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompare depth operand must be a scalar numeric value|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_lod_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COMPARE_LOD_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-lod
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=8|location.column=35"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLod lod operand must be a scalar numeric value|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_texture_compare_compare_op_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_TEXTURE_COMPARE_COMPARE_OP_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-compare-op
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=8|location.column=62"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManual compareOp operand must be a symbolic identifier|message=less_equal|message=got 'true'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_compare_comparison_sampler_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_COMPARISON_SAMPLER_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-sampler
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=48"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManual second operand must be a raw sampler|message=got 'comparison_sampler'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_compare_offset_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_OFFSET_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-offset
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=9|location.column=41"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualOffset offset operand must be ivec2|message=got 'vec2'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_compare_offset_shape_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_OFFSET_SHAPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-offset-texture
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=41"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualOffset supports offset sampling only|message=sampler2DArrayShadow|message=got 'samplerCubeShadow'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_compare_dynamic_offset_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_DYNAMIC_OFFSET_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-offset-static
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=10|location.column=41"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualOffset offset operand must be a static ivec2 integer literal constructor"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_compare_gather_shape_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_GATHER_SHAPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-gather-texture
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=44"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualGather2x2 supports 2x2 gather sampling only|message=sampler2DArrayShadow|message=got 'samplerCubeShadow'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_shape_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_KERNEL_SHAPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-texture
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=7|location.column=42"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel4 supports kernel sampling only|message=sampler2DArrayShadow|message=got 'samplerCubeShadow'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_offset_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_KERNEL_OFFSET_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-offset
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=9|location.column=42"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel4 offset operand 0|message=must be ivec2|message=got 'vec2'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_dynamic_offset_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_KERNEL_DYNAMIC_OFFSET_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-offset-static
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=10|location.column=42"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel4 offset operand 0|message=static ivec2 integer literal constructor"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_weight_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_COMPARE_KERNEL_WEIGHT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-weight
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=9|location.column=56"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel4 weight operand 0|message=scalar numeric value|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_list_empty_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_KERNEL_LIST_EMPTY_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-list-empty
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=9|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel tap list must contain at least one ivec2/weight pair"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_list_offset_type_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_KERNEL_LIST_OFFSET_TYPE_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-offset
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=10|location.column=36"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel offset operand 1|message=must be ivec2|message=got 'vec2'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_list_dynamic_offset_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_KERNEL_LIST_DYNAMIC_OFFSET_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-offset-static
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=11|location.column=36"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel offset operand 1|message=static ivec2 integer literal constructor"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_list_weight_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_KERNEL_LIST_WEIGHT_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-weight
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=10|location.column=49"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel weight operand 1|message=scalar numeric value|message=got 'bool'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_list_pairs_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_KERNEL_LIST_PAIRS_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-list-pairs
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=9|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel tap list must contain complete ivec2/weight pairs"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_list_non_builder_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_KERNEL_LIST_NON_BUILDER_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-list-builder
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=9|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel tap list must be a textureCompareKernel"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_manual_kernel_list_too_many_taps_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_FAILURE_MANUAL_KERNEL_LIST_TOO_MANY_TAPS_SHADER}
    -DMODE=check-failure
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-list-size
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=9|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=textureCompareLodManualKernel tap list supports at most 16 taps"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_duplicate_struct_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_DUPLICATE_STRUCT_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.duplicate-struct
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=6|location.column=3"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=duplicate struct declaration 'Params'|message=using the first declaration"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_unknown_struct_field_type_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_UNKNOWN_STRUCT_FIELD_TYPE_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.unknown-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=3|location.column=5"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=unknown type 'Nope'|message=struct 'Params'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_unknown_constant_type_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_UNKNOWN_CONSTANT_TYPE_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.unknown-constant-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=2|location.column=9"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=unknown type 'Nope'|message=constant 'VALUE'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_unknown_resource_type_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_UNKNOWN_RESOURCE_TYPE_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.unknown-resource-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=3|location.column=34"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=unknown resource type 'Nope'|message=resource 'thing'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_unknown_return_type_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_UNKNOWN_RETURN_TYPE_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.unknown-return-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=3|location.column=5"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=unknown return type 'Nope'|message=stage function 'main'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_unknown_parameter_type_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_UNKNOWN_PARAMETER_TYPE_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.unknown-parameter-type
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=3|location.column=15"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=unknown parameter type 'Nope'|message=stage function 'main'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_inferred_entry_point_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_INFERRED_ENTRY_POINT_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.inferred-entry-point
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=2|location.column=3"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=stage 'compute' has no main function|message=using 'helper'"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_manual_kernel_non_normalized_weight_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_MANUAL_KERNEL_NON_NORMALIZED_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-weight-not-normalized
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=7|location.column=11"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=literal weights sum to 0.8|message=preserves exact user weights|message=does not normalize manual shadow kernels"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_check_json_manual_kernel_zero_sum_weight_warning
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_MANUAL_KERNEL_ZERO_SUM_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-weight-zero-sum
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.line=7|location.column=11"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=literal weights sum to zero|message=preserves exact user weights|message=does not normalize manual shadow kernels"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
