set(CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/WorkgroupBarrierOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_ATOMIC_STORAGE_BUFFER_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/AtomicStorageBufferOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_ATOMIC_COMPAT_COUNTER_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/AtomicCompatCounterOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_ATOMIC_WORKGROUP_BARRIER_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/AtomicWorkgroupBarrierOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_ATOMIC_ADD_RETURN_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/AtomicAddReturnOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_ATOMIC_MINMAX_RETURN_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/AtomicMinMaxReturnOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_ATOMIC_EXCHANGE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/AtomicExchangeOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_ATOMIC_BITWISE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/AtomicBitwiseOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/StorageImageOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/StorageImageArrayOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/StorageImageNonuniformArrayOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/StorageImageAtomicOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_CONSTANTS_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/StorageImageConstantsOptimizerBoundaryShader.cgl)
set(CROSSGL_OPTIMIZER_BOOLEAN_ALGEBRA_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/BooleanAlgebraOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_ZERO_ALGEBRA_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/ZeroAlgebraOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_INTEGER_IDENTITY_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/IntegerIdentityOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_MINMAX_IDENTITY_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/MinMaxIdentityOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_MODULO_IDENTITY_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/ModuloIdentityOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_INTEGER_RELATIONAL_IDENTITY_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/IntegerRelationalIdentityOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_FLOAT_UNARY_IDENTITY_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/FloatUnaryIdentityOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_PROPAGATED_ALGEBRA_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/PropagatedAlgebraOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_PURE_INTRINSIC_CONSTANT_FOLDING_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/PureIntrinsicConstantFoldingShader.cgl)
set(CROSSGL_OPTIMIZER_VECTOR_TRIG_INTRINSIC_FOLD_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/VectorTrigIntrinsicFoldOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_O2_TEMPORARY_INLINING_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/O2TemporaryInliningOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_O2_PURE_EXPRESSION_CSE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/O2PureExpressionCSEOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_O2_DOMINATED_SCOPE_CSE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/O2DominatedScopeCSEOptimizerShader.cgl)
set(CROSSGL_OPTIMIZER_FOR_BOUNDARY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ForOptimizerBoundaryHIRShader.cgl)

add_test(NAME cglc_optimizer_opt_level_check_o2_accepts
  COMMAND cglc check ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --opt-level O2)

add_test(NAME cglc_optimizer_opt_level_check_requires_known_level
  COMMAND cglc check ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --opt-level O3)
set_tests_properties(cglc_optimizer_opt_level_check_requires_known_level
  PROPERTIES
    WILL_FAIL TRUE)

crossgl_add_required_python_test(
  NAME cglc_v0_optimizer_evidence_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_v0_optimizer_evidence.py")
crossgl_add_python_script_test(
  NAME cglc_v0_optimizer_evidence_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_v0_optimizer_evidence.py
  ARGS
    --self-test)
crossgl_add_python_script_test(
  NAME cglc_v0_optimizer_evidence
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_v0_optimizer_evidence.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)

add_test(NAME cglc_optimizer_opt_level_default_trace_policy
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_opt_level_default_trace_policy
  PROPERTIES
    PASS_REGULAR_EXPRESSION "\"optimizationLevel\": \"O1\".*\"passSchedule\": \\{.*\"fingerprint\": \"fnv1a64:[0-9a-f].*\"fingerprintPolicy\": \"scheduled-pass-ids-v1\".*\"stability\": \"stable-opt-level-policy\".*\"scheduledPassCount\": 10.*\"passCount\": 10.*\"completed\": true.*\"stopReason\": \"none\""
    FAIL_REGULAR_EXPRESSION "hir[.]optimize[.]o2[.](pure-expression-cse|inline-scalar-temporaries|inline-literal-vector-temporaries)|hir[.]validate[.]backend-input")

add_test(NAME cglc_optimizer_hir_pass_trace_reports_change_status
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_pass_trace_reports_change_status
  PROPERTIES
    PASS_REGULAR_EXPRESSION "\"kind\": \"hir-pass-trace\".*\"changedPassCount\": [1-9][0-9]*.*\"diagnosticPassCount\": 0.*\"errorPassCount\": 0.*\"name\": \"hir.validate.module-shape\".*\"changed\": false.*\"name\": \"hir.optimize.cleanup-dead-local-declarations\".*\"changed\": true.*\"name\": \"hir.validate.storage-buffer-shapes\".*\"changed\": false")

add_test(NAME cglc_optimizer_hir_pass_trace_reports_completed_status_counts
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_pass_trace_reports_completed_status_counts
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["index": 0.*"name": "hir[.]validate[.]module-shape".*"changed": false.*"status": "completed".*"diagnosticCount": 0.*"errorCount": 0.*"index": 7.*"name": "hir[.]optimize[.]cleanup-dead-local-declarations".*"changed": true.*"status": "completed".*"diagnosticCount": 0.*"errorCount": 0.*"index": 9.*"name": "hir[.]validate[.]storage-buffer-shapes".*"changed": false.*"status": "completed".*"diagnosticCount": 0.*"errorCount": 0]=])

add_test(NAME cglc_optimizer_hir_pass_trace_reports_metrics
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER}
    -DSTAGE=hir-pass-trace
    -DMODE=dump-stage
    -DEXPECT_HIR_PASS_TRACE_METRICS=ON
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=hir-pass-trace"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_opt_level_o2_trace_has_distinct_pass
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --stage hir-pass-trace --opt-level O2)
set_tests_properties(cglc_optimizer_opt_level_o2_trace_has_distinct_pass
  PROPERTIES
    PASS_REGULAR_EXPRESSION "\"optimizationLevel\": \"O2\".*\"scheduledPassCount\": 13.*\"passCount\": 13.*\"completed\": true.*\"stopReason\": \"none\".*hir[.]optimize[.]o2[.]pure-expression-cse.*hir[.]optimize[.]o2[.]inline-scalar-temporaries.*hir[.]optimize[.]o2[.]inline-literal-vector-temporaries"
    FAIL_REGULAR_EXPRESSION "hir[.]validate[.]backend-input")

add_test(NAME cglc_optimizer_opt_level_o0_trace_is_validation_only
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --stage hir-pass-trace --opt-level O0)
set_tests_properties(cglc_optimizer_opt_level_o0_trace_is_validation_only
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O0".*"scheduledPassCount": 3.*"passCount": 3.*"changedPassCount": 0.*"diagnosticPassCount": 0.*"errorPassCount": 0.*"changed": false.*"completed": true.*"stopReason": "none".*"index": 0.*"name": "hir[.]validate[.]module-shape".*"changed": false.*"status": "completed".*"diagnosticCount": 0.*"errorCount": 0.*"index": 1.*"name": "hir[.]validate[.]typed-symbols".*"changed": false.*"status": "completed".*"diagnosticCount": 0.*"errorCount": 0.*"index": 2.*"name": "hir[.]validate[.]storage-buffer-shapes".*"changed": false.*"status": "completed".*"diagnosticCount": 0.*"errorCount": 0]=]
    FAIL_REGULAR_EXPRESSION "hir[.]optimize[.]|hir[.]validate[.]backend-input")

add_test(NAME cglc_optimizer_opt_level_o0_preserves_readable_hir
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --stage hir --opt-level O0)
set_tests_properties(cglc_optimizer_opt_level_o0_preserves_readable_hir
  PROPERTIES
    PASS_REGULAR_EXPRESSION "deadBefore|deadMiddle|deadAfter")

add_test(NAME cglc_optimizer_hir_o1_preserves_temp_inlining_candidates
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_TEMPORARY_INLINING_SHADER} --stage hir --opt-level O1)
set_tests_properties(cglc_optimizer_hir_o1_preserves_temp_inlining_candidates
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl float scalarInline = left \+ right : float.*return scalarInline : float.*decl vec4 vectorInline = vec4\(0[.]25, 0[.]5, 0[.]75, 1[.]0\) : vec4.*assign values\[1\] : float = consumeVector\(vectorInline\)]=])

add_test(NAME cglc_optimizer_hir_o2_temp_inlining
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_TEMPORARY_INLINING_SHADER} --stage hir --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_temp_inlining
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[return left \+ right : float.*decl float scalarReadTwice = left \+ right : float.*return scalarReadTwice \+ scalarReadTwice : float.*assign values\[1\] : float = consumeVector\(vec4\(0[.]25, 0[.]5, 0[.]75, 1[.]0\)\).*decl float scalarResourceRead = values\[4\] : float.*assign values\[4\] : float = scalarResourceRead : float.*decl vec4 vectorReadTwice = vec4\(1[.]0, 2[.]0, 3[.]0, 4[.]0\) : vec4.*assign values\[5\] : float = consumeVector\(vectorReadTwice\) \+ consumeVector\(vectorReadTwice\)]=]
    FAIL_REGULAR_EXPRESSION [=[decl float scalarInline|return scalarInline|decl vec4 vectorInline|consumeVector\(vectorInline\)]=])

add_test(NAME cglc_optimizer_hir_o2_temp_inlining_trace_changed
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_TEMPORARY_INLINING_SHADER} --stage hir-pass-trace --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_temp_inlining_trace_changed
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O2".*"name": "hir[.]optimize[.]o2[.]inline-scalar-temporaries".*"changed": true.*"name": "hir[.]optimize[.]o2[.]inline-literal-vector-temporaries".*"changed": true]=])

add_test(NAME cglc_optimizer_hir_o1_preserves_pure_expression_cse_candidates
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_PURE_EXPRESSION_CSE_SHADER} --stage hir --opt-level O1)
set_tests_properties(cglc_optimizer_hir_o1_preserves_pure_expression_cse_candidates
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl float first = \(left \+ right\) \* bias : float.*decl float second = \(left \+ right\) \* bias : float.*decl float third = max\(left \+ right, bias\) : float.*decl float fourth = max\(left \+ right, bias\) : float.*decl float before = left \+ right : float.*assign values\[index\] : float = before : float.*decl float after = left \+ right : float]=])

add_test(NAME cglc_optimizer_hir_o2_pure_expression_cse
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_PURE_EXPRESSION_CSE_SHADER} --stage hir --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_pure_expression_cse
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl float first = \(left \+ right\) \* bias : float.*decl float third = max\(left \+ right, bias\) : float.*return first \+ first \+ third \+ third : float.*decl float before = left \+ right : float.*assign values\[index\] : float = before : float.*decl float after = left \+ right : float.*return before \+ after \+ after : float]=]
    FAIL_REGULAR_EXPRESSION [=[decl float second|decl float fourth|decl float after = before]=])

add_test(NAME cglc_optimizer_hir_o2_pure_expression_cse_trace_changed
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_PURE_EXPRESSION_CSE_SHADER} --stage hir-pass-trace --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_pure_expression_cse_trace_changed
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O2".*"name": "hir[.]optimize[.]o2[.]pure-expression-cse".*"changed": true]=])

add_test(NAME cglc_optimizer_hir_o1_preserves_dominated_scope_cse_candidates
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_DOMINATED_SCOPE_CSE_SHADER} --stage hir --opt-level O1)
set_tests_properties(cglc_optimizer_hir_o1_preserves_dominated_scope_cse_candidates
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl float parent = \(left \+ right\) \* 2[.]0 : float.*decl float child = \(left \+ right\) \* 2[.]0 : float.*decl float childLocalFirst = \(left - right\) \* 4[.]0 : float.*decl float childLocalSecond = \(left - right\) \* 4[.]0 : float.*decl float before = max\(left \+ right, 1[.]0\) : float.*decl float thenReuse = max\(left \+ right, 1[.]0\) : float.*decl float elseReuse = max\(left \+ right, 1[.]0\) : float]=])

add_test(NAME cglc_optimizer_hir_o2_dominated_scope_pure_expression_cse
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_DOMINATED_SCOPE_CSE_SHADER} --stage hir --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_dominated_scope_pure_expression_cse
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl float parent = \(left \+ right\) \* 2[.]0 : float.*assign total : float = total \+ parent \+ childLocalFirst \+ childLocalFirst : float.*decl float before = max\(left \+ right, 1[.]0\) : float.*assign selected : float = selected \+ before \+ thenLocalFirst \+ thenLocalFirst : float.*assign selected : float = selected \+ before \+ elseLocalFirst \+ elseLocalFirst : float.*decl float after = \(left \+ right\) \* 7[.]0 : float]=]
    FAIL_REGULAR_EXPRESSION [=[decl float child =|decl float childLocalSecond|decl float thenReuse|decl float thenLocalSecond|decl float elseReuse|decl float elseLocalSecond|decl float after = thenScoped|decl float after = elseScoped]=])

add_test(NAME cglc_optimizer_hir_o2_dominated_scope_cse_trace_changed
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_O2_DOMINATED_SCOPE_CSE_SHADER} --stage hir-pass-trace --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_dominated_scope_cse_trace_changed
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O2".*"name": "hir[.]optimize[.]o2[.]pure-expression-cse".*"changed": true]=])

add_test(NAME cglc_optimizer_workgroup_barrier_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER})

set(CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_ORDER_REGEX [=[assign tile\[local\] : int = values\[local\] \+ 1 : int.*expr workgroupBarrier\(\) : void.*decl int sharedAfter = tile\[0\] \+ tile\[local\] : int.*assign values\[local\] : int = sharedAfter : int.*expr barrier\(\) : void.*assign values\[local \+ 1\] : int = values\[local\] \+ tile\[0\] : int]=])
add_test(NAME cglc_optimizer_hir_workgroup_barrier_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_workgroup_barrier_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_WORKGROUP_BARRIER_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_workgroup_barrier_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr workgroupBarrier\\(\\) : void.*expr barrier\\(\\) : void"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadMiddle|deadAfter")

add_test(NAME cglc_optimizer_atomic_storage_buffer_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ATOMIC_STORAGE_BUFFER_SHADER})

set(CROSSGL_OPTIMIZER_ATOMIC_STORAGE_BUFFER_ORDER_REGEX [=[assign values\[0\] : int = 1 : int.*expr atomicAdd\(counters\[index\], 1\) : int.*assign values\[1\] : int = values\[0\] \+ 2 : int.*expr atomicAdd\(unsignedCounters\[index\], index\) : uint.*decl int liveAfter = values\[1\] \+ 3 : int.*assign values\[2\] : int = liveAfter : int]=])
add_test(NAME cglc_optimizer_hir_atomic_storage_buffer_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_ATOMIC_STORAGE_BUFFER_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_ATOMIC_STORAGE_BUFFER_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_atomic_storage_buffer_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_STORAGE_BUFFER_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_atomic_storage_buffer_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr atomicAdd\\(counters\\[index\\], 1\\) : int.*expr atomicAdd\\(unsignedCounters\\[index\\], index\\) : uint"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadAfter")

add_test(NAME cglc_optimizer_hir_atomic_storage_buffer_trace_cleanup_evidence
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_STORAGE_BUFFER_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_atomic_storage_buffer_trace_cleanup_evidence
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O1".*"scheduledPassCount": 10.*"passCount": 10.*"changedPassCount": 3.*"diagnosticPassCount": 0.*"errorPassCount": 0.*"completed": true.*"name": "hir[.]optimize[.]fold-constant-intrinsics".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]propagate-local-scalars".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]cleanup-dead-local-declarations".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]cleanup-dead-local-stores".*"changed": false.*"status": "completed".*"name": "hir[.]validate[.]storage-buffer-shapes".*"changed": false.*"status": "completed"]=])

add_test(NAME cglc_optimizer_atomic_compat_counter_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ATOMIC_COMPAT_COUNTER_SHADER})

set(CROSSGL_OPTIMIZER_ATOMIC_COMPAT_COUNTER_ORDER_REGEX [=[assign values\[0\] : int = counters[.]active_count : int.*expr atomicAdd\(counters[.]active_count, 1\) : int.*assign values\[1\] : int = values\[0\] \+ counters[.]active_count : int.*expr atomicAdd\(counters[.]spawn_count, index\) : uint.*decl int liveAfter = values\[1\] \+ counters[.]active_count : int.*assign values\[2\] : int = liveAfter : int]=])
add_test(NAME cglc_optimizer_hir_atomic_compat_counter_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_ATOMIC_COMPAT_COUNTER_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_ATOMIC_COMPAT_COUNTER_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_atomic_compat_counter_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_COMPAT_COUNTER_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_atomic_compat_counter_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr atomicAdd\\(counters[.]active_count, 1\\) : int.*expr atomicAdd\\(counters[.]spawn_count, index\\) : uint"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadAfter")

add_test(NAME cglc_optimizer_atomic_add_return_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ATOMIC_ADD_RETURN_SHADER})

set(CROSSGL_OPTIMIZER_ATOMIC_ADD_RETURN_ORDER_REGEX [=[assign values\[0\] : int = 1 : int.*decl int old = atomicAdd\(counters\[index\], 1\) : int.*assign values\[1\] : int = old \+ values\[0\] : int.*assign old : int = atomicAdd\(counters\[index\], 1\) : int.*decl uint oldU = atomicAdd\(unsignedCounters\[index\], unsignedDelta\) : uint.*decl int unusedReturned = atomicAdd\(counters\[index\], 1\) : int.*expr atomicAdd\(counters\[index\], 1\) : int.*decl int oldCompat = atomicAdd\(compatCounters[.]active_count, 1\) : int.*assign values\[2\] : int = values\[1\] \+ old \+ oldCompat : int]=])
add_test(NAME cglc_optimizer_hir_atomic_add_return_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_ATOMIC_ADD_RETURN_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_ATOMIC_ADD_RETURN_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_atomic_add_return_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_ADD_RETURN_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_atomic_add_return_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl int old = atomicAdd\\(counters\\[index\\], 1\\) : int.*assign old : int = atomicAdd\\(counters\\[index\\], 1\\) : int.*decl uint oldU = atomicAdd\\(unsignedCounters\\[index\\], unsignedDelta\\) : uint.*decl int unusedReturned = atomicAdd\\(counters\\[index\\], 1\\) : int.*expr atomicAdd\\(counters\\[index\\], 1\\) : int.*decl int oldCompat = atomicAdd\\(compatCounters[.]active_count, 1\\) : int"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadAfter")

add_test(NAME cglc_optimizer_atomic_minmax_return_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ATOMIC_MINMAX_RETURN_SHADER})

set(CROSSGL_OPTIMIZER_ATOMIC_MINMAX_RETURN_ORDER_REGEX [=[assign values\[0\] : int = 1 : int.*decl int oldMin = atomicMin\(counters\[index\], value\) : int.*expr barrier\(\) : void.*assign values\[1\] : int = oldMin \+ values\[0\] : int.*assign oldMax : int = atomicMax\(counters\[index\], value\) : int.*expr atomicMin\(counters\[index\], 0\) : int.*decl uint oldMaxU = atomicMax\(unsignedCounters\[index\], unsignedValue\) : uint.*decl int unusedReturnedMin = atomicMin\(counters\[index\], value\) : int.*expr workgroupBarrier\(\) : void.*expr atomicMax\(counters\[index\], value\) : int.*decl int oldCompat = atomicMax\(compatCounters[.]active_count, 1\) : int.*assign values\[2\] : int = values\[1\] \+ oldMin \+ oldMax \+ oldCompat : int]=])
add_test(NAME cglc_optimizer_hir_atomic_minmax_return_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_ATOMIC_MINMAX_RETURN_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_ATOMIC_MINMAX_RETURN_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_atomic_minmax_return_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_MINMAX_RETURN_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_atomic_minmax_return_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl int oldMin = atomicMin\\(counters\\[index\\], value\\) : int.*assign oldMax : int = atomicMax\\(counters\\[index\\], value\\) : int.*expr atomicMin\\(counters\\[index\\], 0\\) : int.*decl uint oldMaxU = atomicMax\\(unsignedCounters\\[index\\], unsignedValue\\) : uint.*decl int unusedReturnedMin = atomicMin\\(counters\\[index\\], value\\) : int.*expr workgroupBarrier\\(\\) : void.*expr atomicMax\\(counters\\[index\\], value\\) : int.*decl int oldCompat = atomicMax\\(compatCounters[.]active_count, 1\\) : int"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadAfter")

add_test(NAME cglc_optimizer_atomic_exchange_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ATOMIC_EXCHANGE_SHADER})

set(CROSSGL_OPTIMIZER_ATOMIC_EXCHANGE_ORDER_REGEX [=[assign values\[0\] : int = 1 : int.*decl int oldExchange = atomicExchange\(counters\[index\], value\).*expr barrier\(\) : void.*assign values\[1\] : int = oldExchange \+ values\[0\] : int.*assign oldShared : int = atomicExchange\(sharedCounters\[local\], value\).*expr atomicExchange\(counters\[index\], value\).*decl uint oldUnsigned = atomicExchange\(unsignedCounters\[index\], unsignedValue\).*decl int unusedReturnedExchange = atomicExchange\(counters\[index\], value\).*expr workgroupBarrier\(\) : void.*decl int oldCompat = atomicExchange\(compatCounters[.]active_count, 1\).*assign values\[2\] : int = values\[1\] \+ oldExchange \+ oldShared \+ oldCompat : int]=])
add_test(NAME cglc_optimizer_hir_atomic_exchange_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_ATOMIC_EXCHANGE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_ATOMIC_EXCHANGE_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_atomic_exchange_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_EXCHANGE_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_atomic_exchange_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl int oldExchange = atomicExchange\\(counters\\[index\\], value\\).*assign oldShared : int = atomicExchange\\(sharedCounters\\[local\\], value\\).*expr atomicExchange\\(counters\\[index\\], value\\).*decl uint oldUnsigned = atomicExchange\\(unsignedCounters\\[index\\], unsignedValue\\).*decl int unusedReturnedExchange = atomicExchange\\(counters\\[index\\], value\\).*expr workgroupBarrier\\(\\) : void.*decl int oldCompat = atomicExchange\\(compatCounters[.]active_count, 1\\)"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadAfter")

add_test(NAME cglc_optimizer_atomic_bitwise_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ATOMIC_BITWISE_SHADER})

set(CROSSGL_OPTIMIZER_ATOMIC_BITWISE_ORDER_REGEX [=[assign values\[0\] : int = 1 : int.*decl int oldAnd = atomicAnd\(masks\[index\], mask\).*expr barrier\(\) : void.*assign values\[1\] : int = oldAnd \+ values\[0\] : int.*assign oldOr : int = atomicOr\(masks\[index\], mask\).*expr atomicXor\(masks\[index\], mask\).*decl uint oldAndU = atomicAnd\(unsignedMasks\[index\], unsignedMask\).*decl int unusedReturnedOr = atomicOr\(masks\[index\], mask\).*expr workgroupBarrier\(\) : void.*decl int oldShared = atomicXor\(sharedMasks\[local\], mask\).*expr atomicAnd\(sharedMasks\[local\], mask\).*decl uint oldSharedU = atomicOr\(unsignedSharedMasks\[local\], unsignedMask\).*decl int oldCompat = atomicXor\(compatCounters[.]active_count, 1\).*assign values\[2\] : int = values\[1\] \+ oldAnd \+ oldOr \+ oldShared \+ oldCompat : int]=])
add_test(NAME cglc_optimizer_hir_atomic_bitwise_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_ATOMIC_BITWISE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_ATOMIC_BITWISE_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_atomic_bitwise_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_BITWISE_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_atomic_bitwise_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl int oldAnd = atomicAnd\\(masks\\[index\\], mask\\).*assign oldOr : int = atomicOr\\(masks\\[index\\], mask\\).*expr atomicXor\\(masks\\[index\\], mask\\).*decl uint oldAndU = atomicAnd\\(unsignedMasks\\[index\\], unsignedMask\\).*decl int unusedReturnedOr = atomicOr\\(masks\\[index\\], mask\\).*expr workgroupBarrier\\(\\) : void.*decl int oldShared = atomicXor\\(sharedMasks\\[local\\], mask\\).*expr atomicAnd\\(sharedMasks\\[local\\], mask\\).*decl uint oldSharedU = atomicOr\\(unsignedSharedMasks\\[local\\], unsignedMask\\).*decl int oldCompat = atomicXor\\(compatCounters[.]active_count, 1\\)"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadAfter")

add_test(NAME cglc_optimizer_storage_image_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_SHADER})

set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_ORDER_REGEX [=[expr imageStore\(colorImage, pixel, seed\) : void.*decl vec4 color = imageLoad\(colorImage, pixel\) : vec4.*expr imageLoad\(colorImage, pixel\) : vec4.*expr imageStore\(colorImage, pixel \+ ivec2\(1, 0\), color\) : void.*decl ivec4 label = imageLoad\(labelImage, pixel\) : ivec4.*expr imageStore\(labelImage, pixel \+ ivec2\(0, 1\), label\) : void.*decl uvec4 mask = imageLoad\(maskAtlas, ivec3\(pixel, layer\)\) : uvec4.*expr imageStore\(maskAtlas, ivec3\(pixel, layer \+ 1\), mask\) : void]=])
add_test(NAME cglc_optimizer_hir_storage_image_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_storage_image_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_storage_image_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr imageStore\\(colorImage, pixel, seed\\) : void.*decl vec4 color = imageLoad\\(colorImage, pixel\\) : vec4.*expr imageLoad\\(colorImage, pixel\\) : vec4.*expr imageStore\\(maskAtlas, ivec3\\(pixel, layer \\+ 1\\), mask\\) : void"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadColor|deadAfter|deadTail")

add_test(NAME cglc_optimizer_hir_storage_image_trace_cleanup_evidence
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_storage_image_trace_cleanup_evidence
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O1".*"scheduledPassCount": 10.*"passCount": 10.*"changedPassCount": 1.*"diagnosticPassCount": 0.*"errorPassCount": 0.*"completed": true.*"name": "hir[.]optimize[.]cleanup-dead-local-declarations".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]cleanup-dead-local-stores".*"changed": false.*"status": "completed".*"name": "hir[.]validate[.]storage-buffer-shapes".*"changed": false.*"status": "completed"]=])

add_test(NAME cglc_optimizer_storage_image_descriptor_array_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER})

set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_DESCRIPTOR_ARRAY_ORDER_REGEX [=[expr imageStore\(colorImages\[1\], pixel, seed\) : void.*decl vec4 dynamicColor = imageLoad\(colorImages\[dynamicSlot\], pixel\) : vec4.*expr imageLoad\(colorImages\[0\], pixel\) : vec4.*expr imageStore\(colorImages\[dynamicSlot\], pixel \+ ivec2\(1, 0\), dynamicColor\) : void.*decl ivec4 label = imageLoad\(labelImages\[1\], pixel\) : ivec4.*expr imageStore\(labelImages\[dynamicSlot\], pixel \+ ivec2\(0, 1\), label\) : void.*decl uvec4 mask = imageLoad\(maskAtlases\[dynamicSlot\], ivec3\(pixel, layer\)\) : uvec4.*expr imageStore\(maskAtlases\[1\], ivec3\(pixel, layer \+ 1\), mask\) : void]=])
add_test(NAME cglc_optimizer_hir_storage_image_descriptor_array_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_DESCRIPTOR_ARRAY_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_storage_image_descriptor_array_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_storage_image_descriptor_array_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr imageStore\\(colorImages\\[1\\], pixel, seed\\) : void.*decl vec4 dynamicColor = imageLoad\\(colorImages\\[dynamicSlot\\], pixel\\) : vec4.*expr imageLoad\\(colorImages\\[0\\], pixel\\) : vec4.*expr imageStore\\(maskAtlases\\[1\\], ivec3\\(pixel, layer \\+ 1\\), mask\\) : void"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadColor|deadAfter|deadTail")

add_test(NAME cglc_optimizer_storage_image_nonuniform_descriptor_array_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER})

set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_ORDER_REGEX [=[expr imageStore\(colorImages\[nonuniform\(slot\)\], pixel, seed\) : void.*decl vec4 color = imageLoad\(colorImages\[nonuniform\(slot\)\], pixel \+ ivec2\(1, 0\)\) : vec4.*expr imageLoad\(colorImages\[nonuniform\(slot\)\], pixel \+ ivec2\(2, 0\)\) : vec4.*expr imageStore\(colorImages\[nonuniform\(slot\)\], pixel \+ ivec2\(3, 0\), color\) : void.*decl uvec4 mask = imageLoad\(maskAtlases\[nonuniform\(slot\)\], ivec3\(pixel, layer\)\) : uvec4.*expr imageStore\(maskAtlases\[nonuniform\(slot\)\], ivec3\(pixel, layer \+ 1\), mask\) : void]=])
add_test(NAME cglc_optimizer_hir_storage_image_nonuniform_descriptor_array_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_storage_image_nonuniform_descriptor_array_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_storage_image_nonuniform_descriptor_array_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr imageStore\\(colorImages\\[nonuniform\\(slot\\)\\], pixel, seed\\) : void.*decl vec4 color = imageLoad\\(colorImages\\[nonuniform\\(slot\\)\\], pixel \\+ ivec2\\(1, 0\\)\\) : vec4.*expr imageLoad\\(colorImages\\[nonuniform\\(slot\\)\\], pixel \\+ ivec2\\(2, 0\\)\\) : vec4.*expr imageStore\\(maskAtlases\\[nonuniform\\(slot\\)\\], ivec3\\(pixel, layer \\+ 1\\), mask\\) : void"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadColor|deadAfter|deadTail")

add_test(NAME cglc_optimizer_hir_o2_storage_image_nonuniform_literal_vector_temp
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER} --stage hir --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_storage_image_nonuniform_literal_vector_temp
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr imageStore\\(colorImages\\[nonuniform\\(slot\\)\\], pixel, vec4\\([^)]*\\)\\) : void.*decl vec4 color = imageLoad\\(colorImages\\[nonuniform\\(slot\\)\\], pixel \\+ ivec2\\(1, 0\\)\\) : vec4.*expr imageLoad\\(colorImages\\[nonuniform\\(slot\\)\\], pixel \\+ ivec2\\(2, 0\\)\\) : vec4.*expr imageStore\\(maskAtlases\\[nonuniform\\(slot\\)\\], ivec3\\(pixel, layer \\+ 1\\), mask\\) : void"
    FAIL_REGULAR_EXPRESSION "decl vec4 seed|imageStore\\(colorImages\\[nonuniform\\(slot\\)\\], pixel, seed\\)|deadBefore|deadColor|deadAfter|deadTail")

add_test(NAME cglc_optimizer_storage_image_atomic_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_SHADER})

set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_ORDER_REGEX [=[assign signedResults\[0\] : int = 1 : int.*decl int signedOld = imageAtomicAdd\(signedCounters, pixel, 1\) : int.*assign signedResults\[1\] : int = signedResults\[0\] \+ signedOld : int.*decl int minOld = imageAtomicMin\(signedCounters, pixel, signedOld\) : int.*decl int maxOld = imageAtomicMax\(signedCounters, pixel \+ ivec2\(1, 0\), minOld \+ 1\) : int.*decl int andOld = imageAtomicAnd\(signedCounters, pixel, maxOld\) : int.*decl int orOld = imageAtomicOr\(signedCounters, pixel \+ ivec2\(1, 0\), andOld\) : int.*decl int exchanged = imageAtomicExchange\(signedCounters, pixel \+ ivec2\(1, 0\), orOld \+ 2\) : int.*decl uint unsignedOld = imageAtomicAdd\(unsignedAtlas, atlasPixel, uint\(1\.0\)\) : uint.*decl uint unsignedMin = imageAtomicMin\(unsignedAtlas, atlasPixel, unsignedOld\) : uint.*decl uint unsignedMax = imageAtomicMax\(unsignedAtlas, atlasPixel, unsignedMin\) : uint.*expr imageAtomicExchange\(unsignedAtlas, ivec3\(pixel, 1\), unsignedMax\) : uint.*expr imageAtomicXor\(signedCounters, pixel, exchanged\) : int.*expr imageAtomicXor\(unsignedAtlas, atlasPixel, unsignedMax\) : uint.*assign signedResults\[2\] : int = exchanged \+ 9 : int.*assign unsignedResults\[0\] : uint = unsignedOld : uint]=])
add_test(NAME cglc_optimizer_hir_storage_image_atomic_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_storage_image_atomic_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_storage_image_atomic_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl int signedOld = imageAtomicAdd\\(signedCounters, pixel, 1\\) : int.*decl int minOld = imageAtomicMin\\(signedCounters, pixel, signedOld\\) : int.*decl int maxOld = imageAtomicMax\\(signedCounters, pixel \\+ ivec2\\(1, 0\\), minOld \\+ 1\\) : int.*decl int andOld = imageAtomicAnd\\(signedCounters, pixel, maxOld\\) : int.*decl int orOld = imageAtomicOr\\(signedCounters, pixel \\+ ivec2\\(1, 0\\), andOld\\) : int.*decl int exchanged = imageAtomicExchange\\(signedCounters, pixel \\+ ivec2\\(1, 0\\), orOld \\+ 2\\) : int.*decl uint unsignedOld = imageAtomicAdd\\(unsignedAtlas, atlasPixel, uint\\(1\\.0\\)\\) : uint.*decl uint unsignedMin = imageAtomicMin\\(unsignedAtlas, atlasPixel, unsignedOld\\) : uint.*decl uint unsignedMax = imageAtomicMax\\(unsignedAtlas, atlasPixel, unsignedMin\\) : uint.*expr imageAtomicExchange\\(unsignedAtlas, ivec3\\(pixel, 1\\), unsignedMax\\) : uint.*expr imageAtomicXor\\(signedCounters, pixel, exchanged\\) : int.*expr imageAtomicXor\\(unsignedAtlas, atlasPixel, unsignedMax\\) : uint"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadTail")

add_test(NAME cglc_optimizer_hir_o2_storage_image_atomic_trace_unchanged
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_SHADER} --stage hir-pass-trace --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_storage_image_atomic_trace_unchanged
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O2".*"name": "hir[.]optimize[.]o2[.]pure-expression-cse".*"changed": false.*"name": "hir[.]optimize[.]o2[.]inline-scalar-temporaries".*"changed": false.*"name": "hir[.]optimize[.]o2[.]inline-literal-vector-temporaries".*"changed": false]=])

add_test(NAME cglc_optimizer_hir_o2_storage_image_atomic_trace_cleanup_evidence
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_ATOMIC_SHADER} --stage hir-pass-trace --opt-level O2)
set_tests_properties(cglc_optimizer_hir_o2_storage_image_atomic_trace_cleanup_evidence
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O2".*"scheduledPassCount": 13.*"passCount": 13.*"changedPassCount": 3.*"diagnosticPassCount": 0.*"errorPassCount": 0.*"completed": true.*"name": "hir[.]optimize[.]fold-constant-intrinsics".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]propagate-local-scalars".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]cleanup-dead-local-declarations".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]cleanup-dead-local-stores".*"changed": false.*"status": "completed".*"name": "hir[.]optimize[.]o2[.]pure-expression-cse".*"changed": false.*"status": "completed".*"name": "hir[.]optimize[.]o2[.]inline-scalar-temporaries".*"changed": false.*"status": "completed".*"name": "hir[.]optimize[.]o2[.]inline-literal-vector-temporaries".*"changed": false.*"status": "completed".*"name": "hir[.]validate[.]storage-buffer-shapes".*"changed": false.*"status": "completed"]=])

add_test(NAME cglc_optimizer_storage_image_constants_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_CONSTANTS_SHADER})

set(CROSSGL_OPTIMIZER_STORAGE_IMAGE_CONSTANTS_ORDER_REGEX [=[expr imageStore\(colorImage, foldedPixel, seed\) : void.*decl vec4 scalarColor = imageLoad\(colorImage, pixel \+ ivec2\(1, 0\)\) : vec4.*expr imageLoad\(colorImage, pixel \+ ivec2\(1, 0\)\) : vec4.*expr imageStore\(colorImages\[1\], foldedPixel, scalarColor\) : void.*decl uvec4 atlas = imageLoad\(maskAtlases\[dynamicSlot\], ivec3\(pixel, layer \+ \(1\)\)\) : uvec4.*expr imageStore\(maskAtlases\[1\], ivec3\(pixel, layer \+ \(1\)\), atlas\) : void.*decl int old = imageAtomicAdd\(signedCounters, foldedPixel, 1\) : int.*decl int exchanged = imageAtomicExchange\(signedCounters, pixel \+ ivec2\(1, 0\), old \+ \(1\)\) : int.*expr imageAtomicXor\(signedCounters, foldedPixel, exchanged\) : int.*decl uint unsignedOld = imageAtomicAdd\(unsignedAtlases\[1\], ivec3\(pixel, layer \+ \(1\)\), uint\(1\)\) : uint.*expr imageAtomicExchange\(unsignedAtlases\[dynamicSlot\], ivec3\(pixel, layer \+ \(1\)\), unsignedOld \+ uint\(0\)\) : uint.*assign signedResults\[0\] : int = \(old \+ exchanged\) : int.*assign unsignedResults\[0\] : uint = unsignedOld : uint]=])
add_test(NAME cglc_optimizer_hir_storage_image_constants_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_CONSTANTS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_STORAGE_IMAGE_CONSTANTS_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_storage_image_constants_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_STORAGE_IMAGE_CONSTANTS_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_storage_image_constants_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr imageStore\\(colorImage, foldedPixel, seed\\) : void.*decl vec4 scalarColor = imageLoad\\(colorImage, pixel \\+ ivec2\\(1, 0\\)\\) : vec4.*expr imageLoad\\(colorImage, pixel \\+ ivec2\\(1, 0\\)\\) : vec4.*expr imageStore\\(colorImages\\[1\\], foldedPixel, scalarColor\\) : void.*decl uvec4 atlas = imageLoad\\(maskAtlases\\[dynamicSlot\\], ivec3\\(pixel, layer \\+ \\(1\\)\\)\\) : uvec4.*expr imageStore\\(maskAtlases\\[1\\], ivec3\\(pixel, layer \\+ \\(1\\)\\), atlas\\) : void.*decl int old = imageAtomicAdd\\(signedCounters, foldedPixel, 1\\) : int.*decl int exchanged = imageAtomicExchange\\(signedCounters, pixel \\+ ivec2\\(1, 0\\), old \\+ \\(1\\)\\) : int.*expr imageAtomicXor\\(signedCounters, foldedPixel, exchanged\\) : int.*decl uint unsignedOld = imageAtomicAdd\\(unsignedAtlases\\[1\\], ivec3\\(pixel, layer \\+ \\(1\\)\\), uint\\(1\\)\\) : uint.*expr imageAtomicExchange\\(unsignedAtlases\\[dynamicSlot\\], ivec3\\(pixel, layer \\+ \\(1\\)\\), unsignedOld \\+ uint\\(0\\)\\) : uint"
    FAIL_REGULAR_EXPRESSION "deadCoordinate|deadPayload|deadTail")

add_test(NAME cglc_optimizer_atomic_workgroup_barrier_boundary_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ATOMIC_WORKGROUP_BARRIER_SHADER})

set(CROSSGL_OPTIMIZER_ATOMIC_WORKGROUP_BARRIER_ORDER_REGEX [=[expr workgroupBarrier\(\) : void.*expr atomicAdd\(sharedCounters\[local\], 1\) : int.*assign values\[1\] : int = values\[0\] \+ 1 : int.*expr barrier\(\) : void.*expr atomicAdd\(unsignedSharedCounters\[local\], local\) : uint.*assign values\[2\] : int = values\[1\] : int]=])
add_test(NAME cglc_optimizer_hir_atomic_workgroup_barrier_order
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPTIMIZER_ATOMIC_WORKGROUP_BARRIER_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPTIMIZER_ATOMIC_WORKGROUP_BARRIER_ORDER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_optimizer_hir_atomic_workgroup_barrier_dead_cleanup
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ATOMIC_WORKGROUP_BARRIER_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_atomic_workgroup_barrier_dead_cleanup
  PROPERTIES
    PASS_REGULAR_EXPRESSION "expr workgroupBarrier\\(\\) : void.*expr atomicAdd\\(sharedCounters\\[local\\], 1\\) : int.*expr barrier\\(\\) : void.*expr atomicAdd\\(unsignedSharedCounters\\[local\\], local\\) : uint"
    FAIL_REGULAR_EXPRESSION "deadBefore|deadUnsigned|deadAfter")

add_test(NAME cglc_optimizer_hir_for_loop_update_cleanup_trace
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_FOR_BOUNDARY_HIR_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_for_loop_update_cleanup_trace
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O1".*"scheduledPassCount": 10.*"passCount": 10.*"changedPassCount": 2.*"diagnosticPassCount": 0.*"errorPassCount": 0.*"completed": true.*"name": "hir[.]optimize[.]fold-constant-intrinsics".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]cleanup-dead-local-declarations".*"changed": true.*"status": "completed".*"name": "hir[.]optimize[.]cleanup-dead-local-stores".*"changed": false.*"status": "completed".*"name": "hir[.]validate[.]storage-buffer-shapes".*"changed": false.*"status": "completed"]=])

add_test(NAME cglc_optimizer_boolean_algebra_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_BOOLEAN_ALGEBRA_SHADER})

add_test(NAME cglc_optimizer_hir_boolean_algebra_simplify
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_BOOLEAN_ALGEBRA_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_boolean_algebra_simplify
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl bool andRightTrue = base : bool.*decl bool andLeftTrue = base : bool.*decl bool orRightFalse = base : bool.*decl bool orLeftFalse = base : bool.*decl bool andRightFalsePure = false : bool.*decl bool orRightTruePure = true : bool.*decl bool andRightFalseUnknown = unknownFlag\\(dynamicIndex\\) && false : bool.*decl bool orRightTrueUnknown = unknownFlag\\(dynamicIndex\\) \\|\\| true : bool.*decl bool duplicateAndPure = base : bool.*decl bool duplicateOrPure = base : bool.*decl bool duplicateAndUnknown = unknownFlag\\(dynamicIndex\\) && unknownFlag\\(dynamicIndex\\) : bool.*decl bool duplicateOrUnknown = unknownFlag\\(dynamicIndex\\) \\|\\| unknownFlag\\(dynamicIndex\\) : bool.*decl bool complementAndPure = false : bool.*decl bool complementAndPureReversed = false : bool.*decl bool complementOrPure = true : bool.*decl bool complementOrPureReversed = true : bool.*decl bool complementAndUnknown = unknownFlag\\(dynamicIndex\\) && !unknownFlag\\(dynamicIndex\\) : bool.*decl bool complementOrUnknown = unknownFlag\\(dynamicIndex\\) \\|\\| !unknownFlag\\(dynamicIndex\\) : bool.*decl bool selectIdentity = base : bool.*decl bool selectNegation = !base : bool.*decl bool selectCompareNegation = dynamicIndex <= 5 : bool.*decl bool selfEqualInt = true : bool.*decl bool selfNotEqualInt = false : bool.*decl bool selfEqualBool = true : bool.*decl bool selfEqualUnknown = unknownFlag\\(dynamicIndex\\) == unknownFlag\\(dynamicIndex\\) : bool.*decl bool equalRightTrue = base : bool.*decl bool equalLeftTrue = base : bool.*decl bool notEqualRightFalse = base : bool.*decl bool notEqualLeftFalse = base : bool.*decl bool equalRightFalseCompare = dynamicIndex <= 7 : bool.*decl bool notEqualRightTrueCompare = dynamicIndex <= 8 : bool.*decl bool equalRightFalseUnknown = !unknownFlag\\(dynamicIndex\\) : bool.*assign values\\[7\\] : int = 0 : int.*assign values\\[8\\] : int = 1 : int"
    FAIL_REGULAR_EXPRESSION "andRightTrue = base && true|andLeftTrue = true && base|orRightFalse = base \\|\\| false|orLeftFalse = false \\|\\| base|andRightFalsePure = \\(dynamicIndex > 1\\) && false|orRightTruePure = \\(dynamicIndex > 2\\) \\|\\| true|andLeftFalsePure = false && \\(dynamicIndex > 3\\)|orLeftTruePure = true \\|\\| \\(dynamicIndex > 4\\)|duplicateAndPure = base && base|duplicateOrPure = base \\|\\| base|duplicateAndUnknown = unknownFlag\\(dynamicIndex\\) : bool|duplicateOrUnknown = unknownFlag\\(dynamicIndex\\) : bool|complementAndPure = base && !base|complementAndPureReversed = !base && base|complementOrPure = base \\|\\| !base|complementOrPureReversed = !base \\|\\| base|complementAndUnknown = false : bool|complementOrUnknown = true : bool|selectIdentity = base \\? true : false|selectNegation = base \\? false : true|selectCompareNegation = \\(dynamicIndex > 5\\) \\? false : true|selectCompareNegation = !\\(dynamicIndex > 5\\)|selfEqualInt = dynamicIndex == dynamicIndex|selfNotEqualInt = dynamicIndex != dynamicIndex|selfEqualBool = base == base|equalRightTrue = base == true|equalLeftTrue = true == base|notEqualRightFalse = base != false|notEqualLeftFalse = false != base|equalRightFalseCompare = \\(dynamicIndex > 7\\) == false|equalRightFalseCompare = !\\(dynamicIndex > 7\\)|notEqualRightTrueCompare = \\(dynamicIndex > 8\\) != true|notEqualRightTrueCompare = !\\(dynamicIndex > 8\\)|equalRightFalseUnknown = unknownFlag\\(dynamicIndex\\) == false")

crossgl_add_python_script_test(
  NAME cglc_optimizer_select_identity_evidence
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/check_select_identity_optimizer.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_optimizer_boolean_absorption_evidence
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/check_boolean_absorption_optimizer.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_optimizer_boolean_de_morgan_evidence
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/check_boolean_de_morgan_optimizer.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_optimizer_boolean_comparison_negation_evidence
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/check_boolean_comparison_negation_optimizer.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_optimizer_preserved_grouping_evidence
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/check_preserved_grouping_optimizer.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)

add_test(NAME cglc_optimizer_zero_algebra_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_ZERO_ALGEBRA_SHADER})

add_test(NAME cglc_optimizer_hir_zero_algebra_simplify
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_ZERO_ALGEBRA_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_zero_algebra_simplify
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl int mulRightZeroUnknown = unknownInt\\(dynamicIndex\\) \\* 0 : int.*decl int mulLeftZeroUnknown = 0 \\* unknownInt\\(dynamicIndex\\) : int.*decl int subtractSelfUnknown = unknownInt\\(dynamicIndex\\) - unknownInt\\(dynamicIndex\\).*assign values\\[1\\] : int = 0 : int.*assign unsignedValues\\[1\\] : uint = 0 : uint"
    FAIL_REGULAR_EXPRESSION "mulRightZero = dynamicIndex \\* 0|mulLeftZero = 0 \\* \\(dynamicIndex \\+ 1\\)|subtractSelf = dynamicIndex - dynamicIndex|unsignedMulRightZero = unsignedIndex \\* 0|unsignedMulLeftZero = 0 \\* \\(unsignedIndex \\+ 1\\)|unsignedSubtractSelf = unsignedIndex - unsignedIndex")

add_test(NAME cglc_optimizer_integer_identity_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_INTEGER_IDENTITY_SHADER})

add_test(NAME cglc_optimizer_hir_integer_identity_simplify
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTEGER_IDENTITY_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_integer_identity_simplify
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl int unaryInt = dynamicIndex : int.*decl uint unaryUint = unsignedIndex : uint.*decl float floatUnaryPlus = floatBase : float.*decl int addRightZero = dynamicIndex : int.*decl int addLeftZero = dynamicIndex : int.*decl int addUnaryNegativeZero = dynamicIndex : int.*decl int subtractRightZero = dynamicIndex : int.*decl int multiplyRightOne = dynamicIndex : int.*decl int multiplyLeftOne = dynamicIndex : int.*decl int divideRightOne = dynamicIndex : int.*decl uint unsignedAddRightZero = unsignedIndex : uint.*decl uint unsignedAddLeftZero = unsignedIndex : uint.*decl uint unsignedAddUnaryNegativeZero = unsignedIndex : uint.*decl uint unsignedSubtractRightZero = unsignedIndex : uint.*decl uint unsignedMultiplyRightOne = unsignedIndex : uint.*decl uint unsignedMultiplyLeftOne = unsignedIndex : uint.*decl uint unsignedDivideRightOne = unsignedIndex : uint]=]
    FAIL_REGULAR_EXPRESSION [=[unaryInt = \+dynamicIndex|unaryUint = \+unsignedIndex|floatUnaryPlus = \+floatBase|addRightZero = dynamicIndex \+ 0|addLeftZero = 0 \+ dynamicIndex|addUnaryNegativeZero = dynamicIndex \+ -0|subtractRightZero = dynamicIndex - 0|multiplyRightOne = dynamicIndex \* 1|multiplyLeftOne = 1 \* dynamicIndex|divideRightOne = dynamicIndex / 1|unsignedAddRightZero = unsignedIndex \+ 0|unsignedAddLeftZero = 0 \+ unsignedIndex|unsignedAddUnaryNegativeZero = unsignedIndex \+ -0|unsignedSubtractRightZero = unsignedIndex - 0|unsignedMultiplyRightOne = unsignedIndex \* 1|unsignedMultiplyLeftOne = 1 \* unsignedIndex|unsignedDivideRightOne = unsignedIndex / 1]=])

add_test(NAME cglc_optimizer_hir_integer_identity_pass_trace_changed
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTEGER_IDENTITY_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_integer_identity_pass_trace_changed
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["name": "hir[.]optimize[.]simplify-algebraic".*"changed": true]=])

add_test(NAME cglc_optimizer_minmax_identity_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_SHADER})

set(CROSSGL_OPTIMIZER_MINMAX_IDENTITY_HIR_REGEX [=[decl int minSameInt = dynamicIndex : int.*decl int maxSameInt = \(dynamicIndex \+ 1\) : int.*decl uint minSameUint = unsignedIndex : uint.*decl uint maxSameUint = \(unsignedIndex \+ 1\) : uint.*decl int minSameUnknown = min\(unknownInt\(dynamicIndex\), unknownInt\(dynamicIndex\)\) : int.*decl float minSameFloat = min\(floatBase, floatBase\) : float.*decl float maxSameFloat = max\(floatBase, floatBase\) : float]=])
set(CROSSGL_OPTIMIZER_MINMAX_IDENTITY_O2_HIR_REGEX [=[decl int minSameUnknown = min\(unknownInt\(dynamicIndex\), unknownInt\(dynamicIndex\)\) : int.*decl float minSameFloat = min\(floatBase, floatBase\) : float.*decl float maxSameFloat = max\(floatBase, floatBase\) : float.*assign values\[1\] : int = dynamicIndex \+ \(dynamicIndex \+ 1\) : int.*assign unsignedValues\[1\] : uint = unsignedIndex \+ \(unsignedIndex \+ 1\) : uint]=])
set(CROSSGL_OPTIMIZER_MINMAX_IDENTITY_FAIL_REGEX [=[minSameInt = min\(dynamicIndex, dynamicIndex\)|maxSameInt = max\(dynamicIndex \+ 1, dynamicIndex \+ 1\)|minSameUint = min\(unsignedIndex, unsignedIndex\)|maxSameUint = max\(unsignedIndex \+ 1, unsignedIndex \+ 1\)|minSameUnknown = unknownInt\(dynamicIndex\) : int|minSameFloat = floatBase : float|maxSameFloat = floatBase : float]=])

add_test(NAME cglc_optimizer_hir_minmax_identity_simplify_o1
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_SHADER} --stage hir --opt-level O1)
set_tests_properties(cglc_optimizer_hir_minmax_identity_simplify_o1
  PROPERTIES
    PASS_REGULAR_EXPRESSION ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_HIR_REGEX}
    FAIL_REGULAR_EXPRESSION ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_FAIL_REGEX})

add_test(NAME cglc_optimizer_hir_minmax_identity_simplify_o2
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_SHADER} --stage hir --opt-level O2)
set_tests_properties(cglc_optimizer_hir_minmax_identity_simplify_o2
  PROPERTIES
    PASS_REGULAR_EXPRESSION ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_O2_HIR_REGEX}
    FAIL_REGULAR_EXPRESSION ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_FAIL_REGEX})

add_test(NAME cglc_optimizer_hir_minmax_identity_pass_trace_changed_o1
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_SHADER} --stage hir-pass-trace --opt-level O1)
set_tests_properties(cglc_optimizer_hir_minmax_identity_pass_trace_changed_o1
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O1".*"name": "hir[.]optimize[.]simplify-algebraic".*"changed": true.*"status": "completed"]=])

add_test(NAME cglc_optimizer_hir_minmax_identity_pass_trace_changed_o2
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_MINMAX_IDENTITY_SHADER} --stage hir-pass-trace --opt-level O2)
set_tests_properties(cglc_optimizer_hir_minmax_identity_pass_trace_changed_o2
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["optimizationLevel": "O2".*"name": "hir[.]optimize[.]simplify-algebraic".*"changed": true.*"status": "completed"]=])

add_test(NAME cglc_optimizer_modulo_identity_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_MODULO_IDENTITY_SHADER})

add_test(NAME cglc_optimizer_hir_modulo_identity_simplify
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_MODULO_IDENTITY_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_modulo_identity_simplify
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl int moduloRightOneUnknown = unknownInt\(dynamicIndex\) % 1 : int.*assign values\[1\] : int = 0 : int.*assign unsignedValues\[1\] : uint = 0 : uint.*assign values\[2\] : int = moduloRightOneUnknown : int]=]
    FAIL_REGULAR_EXPRESSION [=[moduloRightOne = dynamicIndex % 1|unsignedModuloRightOne = unsignedIndex % 1]=])

add_test(NAME cglc_optimizer_integer_relational_identity_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_INTEGER_RELATIONAL_IDENTITY_SHADER})

add_test(NAME cglc_optimizer_hir_integer_relational_identity_simplify
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_INTEGER_RELATIONAL_IDENTITY_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_integer_relational_identity_simplify
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl bool selfLessInt = false : bool.*decl bool selfLessEqualInt = true : bool.*decl bool selfGreaterInt = false : bool.*decl bool selfGreaterEqualInt = true : bool.*decl bool unsignedSelfLess = false : bool.*decl bool unsignedSelfGreaterEqual = true : bool.*decl bool selfLessUnknown = unknownInt\(dynamicIndex\) < unknownInt\(dynamicIndex\) : bool.*decl bool floatSelfLessEqual = floatBase <= floatBase : bool.*decl bool negLessInt = dynamicIndex >= 1 : bool.*decl bool negLessEqualInt = dynamicIndex > 2 : bool.*decl bool negGreaterInt = dynamicIndex <= 3 : bool.*decl bool negGreaterEqualInt = dynamicIndex < 4 : bool.*decl bool negUnsignedLess = unsignedIndex >= 5 : bool.*decl bool negUnknownLess = !\(unknownInt\(dynamicIndex\) < dynamicIndex\) : bool.*decl bool negFloatLessEqual = !\(floatBase <= floatBase\) : bool]=]
    FAIL_REGULAR_EXPRESSION [=[selfLessInt = dynamicIndex < dynamicIndex|selfLessEqualInt = dynamicIndex <= dynamicIndex|selfGreaterInt = dynamicIndex > dynamicIndex|selfGreaterEqualInt = dynamicIndex >= dynamicIndex|unsignedSelfLess = unsignedIndex < unsignedIndex|unsignedSelfGreaterEqual = unsignedIndex >= unsignedIndex|selfLessUnknown = false|floatSelfLessEqual = true|negLessInt = !\(dynamicIndex < 1\)|negLessEqualInt = !\(dynamicIndex <= 2\)|negGreaterInt = !\(dynamicIndex > 3\)|negGreaterEqualInt = !\(dynamicIndex >= 4\)|negUnsignedLess = !\(unsignedIndex < 5\)|negUnknownLess = unknownInt\(dynamicIndex\) >= dynamicIndex|negFloatLessEqual = floatBase > floatBase]=])

add_test(NAME cglc_optimizer_float_unary_identity_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_FLOAT_UNARY_IDENTITY_SHADER})

add_test(NAME cglc_optimizer_hir_float_unary_identity_simplify
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_FLOAT_UNARY_IDENTITY_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_float_unary_identity_simplify
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl float floatUnaryPlus = floatBase : float.*decl float floatAddRightZero = floatBase \+ 0[.]0 : float.*decl float floatAddLeftZero = 0[.]0 \+ floatBase : float.*decl float floatSubtractRightZero = floatBase : float.*decl float floatMultiplyRightOne = floatBase : float.*decl float floatMultiplyLeftOne = floatBase : float.*decl float floatDivideRightOne = floatBase : float.*decl float floatMultiplyRightZero = floatBase \* 0[.]0 : float.*decl float floatMultiplyLeftZero = 0[.]0 \* floatBase : float.*decl float floatResourceMultiplyRightOne = values\[0\] : float.*decl float floatResourceMultiplyLeftOne = values\[0\] : float.*decl float floatResourceDivideRightOne = values\[0\] : float.*decl float floatResourceSubtractRightZero = values\[0\] : float.*decl float floatResourceMultiplyRightZero = values\[0\] \* 0[.]0 : float.*decl float floatResourceMultiplyLeftZero = 0[.]0 \* values\[0\] : float]=]
    FAIL_REGULAR_EXPRESSION [=[decl float floatUnaryPlus = \+floatBase : float|decl float floatAddRightZero = floatBase : float|decl float floatAddLeftZero = floatBase : float|decl float floatSubtractRightZero = floatBase - 0[.]0 : float|decl float floatMultiplyRightOne = floatBase \* 1[.]0 : float|decl float floatMultiplyLeftOne = 1[.]0 \* floatBase : float|decl float floatDivideRightOne = floatBase / 1[.]0 : float|decl float floatMultiplyRightZero = floatBase : float|decl float floatMultiplyLeftZero = floatBase : float|decl float floatResourceMultiplyRightOne = values\[0\] \* 1[.]0 : float|decl float floatResourceMultiplyLeftOne = 1[.]0 \* values\[0\] : float|decl float floatResourceDivideRightOne = values\[0\] / 1[.]0 : float|decl float floatResourceSubtractRightZero = values\[0\] - 0[.]0 : float|decl float floatResourceMultiplyRightZero = values\[0\] : float|decl float floatResourceMultiplyLeftZero = values\[0\] : float|decl float floatResourceMultiplyRightZero = 0([.]0)? : float|decl float floatResourceMultiplyLeftZero = 0([.]0)? : float]=])

add_test(NAME cglc_optimizer_hir_float_unary_identity_pass_trace_changed
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_FLOAT_UNARY_IDENTITY_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_float_unary_identity_pass_trace_changed
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["name": "hir[.]optimize[.]simplify-algebraic".*"changed": true]=])

add_test(NAME cglc_optimizer_propagated_algebra_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_PROPAGATED_ALGEBRA_SHADER})

add_test(NAME cglc_optimizer_hir_propagated_algebra_simplify
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_PROPAGATED_ALGEBRA_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_propagated_algebra_simplify
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=[decl int addRightZero = dynamicIndex : int.*decl int addLeftZero = dynamicIndex : int.*decl int multiplyRightOne = dynamicIndex : int.*decl int multiplyLeftOne = dynamicIndex : int.*decl int divideRightOne = dynamicIndex : int.*decl int unknownMulRightZero = unknownInt\(dynamicIndex\) \* 0 : int.*decl int unknownModuloRightOne = unknownInt\(dynamicIndex\) % 1 : int.*assign values\[4\] : int = 0 : int.*assign values\[5\] : int = 0 : int.*assign values\[6\] : int = 0 : int]=]
    FAIL_REGULAR_EXPRESSION [=[addRightZero = dynamicIndex \+ 0|addLeftZero = 0 \+ dynamicIndex|multiplyRightOne = dynamicIndex \* 1|multiplyLeftOne = 1 \* dynamicIndex|divideRightOne = dynamicIndex / 1|multiplyRightZero = dynamicIndex \* 0|multiplyLeftZero = 0 \* \(dynamicIndex \+ 1\)|moduloRightOne = dynamicIndex % 1|unknownMulRightZero = 0 : int|unknownModuloRightOne = 0 : int]=])

add_test(NAME cglc_optimizer_hir_propagated_algebra_pass_trace_changed
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_PROPAGATED_ALGEBRA_SHADER} --stage hir-pass-trace)
set_tests_properties(cglc_optimizer_hir_propagated_algebra_pass_trace_changed
  PROPERTIES
    PASS_REGULAR_EXPRESSION [=["name": "hir[.]optimize[.]fold-constant-intrinsics".*"changed": false.*"name": "hir[.]optimize[.]simplify-algebraic".*"changed": false.*"name": "hir[.]optimize[.]propagate-local-scalars".*"changed": true.*"expressionCount": 92.*"expressionCount": 59.*"expressionCount": 33]=])

add_test(NAME cglc_optimizer_pure_intrinsic_constant_folding_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_PURE_INTRINSIC_CONSTANT_FOLDING_SHADER})

add_test(NAME cglc_optimizer_hir_pure_intrinsic_constant_folding
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_PURE_INTRINSIC_CONSTANT_FOLDING_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_pure_intrinsic_constant_folding
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl float foldedDistance = 5 : float.*decl float foldedScalarNormalize = -1 : float.*decl float foldedScalarReflect = -2 : float.*decl float foldedSmoothStep = 0\\.5 : float.*decl float unfurledReversedSmoothStep = smoothstep\\(1\\.0, 0\\.0, 0\\.25\\) : float.*assign results\\[0\\] : float = -1 : float.*assign results\\[1\\] : float = 0\\.5 : float.*assign results\\[2\\] : float = 3 : float.*assign results\\[3\\] : float = -1 : float.*assign results\\[4\\] : float = 0\\.5 : float.*assign results\\[5\\] : float = 1 : float.*assign results\\[6\\] : float = 1 : float.*assign results\\[7\\] : float = -2 : float.*assign results\\[8\\] : float = 3 : float.*assign results\\[9\\] : float = 2 : float.*assign results\\[10\\] : float = -1 : float.*assign results\\[11\\] : float = 3 : float.*assign results\\[12\\] : float = -3 : float.*assign results\\[13\\] : float = 6 : float.*assign results\\[14\\] : float = -3 : float.*assign results\\[15\\] : float = foldedDistance : float.*assign results\\[16\\] : float = foldedScalarNormalize : float.*assign results\\[17\\] : float = 0 : float.*assign results\\[18\\] : float = -1 : float.*assign results\\[19\\] : float = 0 : float.*assign results\\[20\\] : float = foldedScalarReflect : float.*assign results\\[21\\] : float = 1 : float.*assign results\\[22\\] : float = 1 : float.*assign results\\[23\\] : float = 0 : float.*assign results\\[24\\] : float = foldedSmoothStep : float.*assign results\\[25\\] : float = 0 : float.*assign results\\[26\\] : float = 0\\.5 : float.*assign results\\[27\\] : float = 1 : float.*assign results\\[28\\] : float = unfurledReversedSmoothStep : float"
    FAIL_REGULAR_EXPRESSION "clamp\\(|floor\\(|ceil\\(|cross\\(|distance\\(|normalize\\(|reflect\\(|foldedSmoothStep = smoothstep|foldedVectorSmoothStep = smoothstep")

add_test(NAME cglc_optimizer_vector_trig_intrinsic_fold_check
  COMMAND cglc check ${CROSSGL_OPTIMIZER_VECTOR_TRIG_INTRINSIC_FOLD_SHADER})

add_test(NAME cglc_optimizer_hir_vector_trig_intrinsic_fold
  COMMAND cglc dump-ir ${CROSSGL_OPTIMIZER_VECTOR_TRIG_INTRINSIC_FOLD_SHADER} --stage hir)
set_tests_properties(cglc_optimizer_hir_vector_trig_intrinsic_fold
  PROPERTIES
    PASS_REGULAR_EXPRESSION "decl vec4 foldedCos = vec4\\(1, 1, 1, 1\\) : vec4.*decl vec4 foldedTan = vec4\\(0, 0, 0, 0\\) : vec4"
    FAIL_REGULAR_EXPRESSION "cos\\(|tan\\(")
