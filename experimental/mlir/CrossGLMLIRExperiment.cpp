#if !defined(CROSSGL_MLIR_EXPERIMENT_COMPILE_GATED)
#error "MLIR experiment sources must compile only through the gated CMake target"
#endif

#include <array>
#include <string_view>

namespace crossgl::experimental::mlir {

struct ExperimentScaffold {
  std::string_view gate;
  std::string_view fixture;
  bool productionLinked;
};

struct ExperimentFixtureSlice {
  std::string_view path;
  std::string_view factScope;
  bool resourceFree;
};

struct ExperimentResourceFixtureSlice {
  std::string_view path;
  std::string_view factScope;
  std::string_view resourceName;
  std::string_view resourceKind;
  int descriptorSet;
  int descriptorBinding;
  bool productionLinked;
};

struct ExperimentControlFlowFixtureSlice {
  std::string_view path;
  std::string_view factScope;
  std::string_view controlOperation;
  bool structuredBranchOnly;
  bool productionLinked;
};

struct ExperimentVerifierHarness {
  std::string_view name;
  std::string_view fixture;
  std::string_view tool;
  std::string_view mode;
  bool optionalToolGated;
  bool productionLinked;
};

struct ExperimentComputeFixture {
  std::string_view path;
  std::string_view shaderName;
  std::string_view entryPoint;
  std::string_view stage;
  std::array<int, 3> localSize;
  std::string_view admittedSlice;
  std::string_view resourceFactMode;
  std::string_view controlFlowSlice;
  bool productionLinked;
};

struct ExperimentNamedFact {
  std::string_view fixture;
  std::string_view fact;
};

struct ExperimentSourceLocationAnchor {
  std::string_view operation;
  std::array<std::string_view, 6> commonSourceLocationFacts;
  bool productionLinked;
};

struct ExperimentVerifierParityScaffold {
  std::string_view fixture;
  bool coversSourceLocations;
  bool coversEntryPoint;
  bool coversResourceFacts;
  bool coversTargetIndependentResourceMetadata;
  bool coversTargetIndependentTypeFacts;
  bool coversSourceMapDebugFacts;
  bool futureVerifierGated;
  bool productionLinked;
};

struct ExperimentResourceInventory {
  std::string_view fixture;
  std::string_view descriptorName;
  std::string_view descriptorKind;
  int descriptorSet;
  int descriptorBinding;
  std::string_view storageBufferType;
  std::string_view storageBufferElementType;
  std::string_view addressSpace;
  std::string_view metadataScope;
  std::string_view access;
  bool writeAccess;
  bool targetIndependent;
  bool hasTargetAbiFacts;
  bool hasTextureFacts;
  bool hasSamplerFacts;
  bool hasStorageImageFacts;
  bool productionLinked;
};

struct ExperimentControlFlowInventory {
  std::string_view fixture;
  std::string_view operation;
  std::string_view branchConditionTypeFact;
  std::array<std::string_view, 4> sourceLocationFacts;
  std::array<std::string_view, 3> typeFacts;
  bool structuredOnly;
  bool loopsAdmitted;
  bool earlyReturnsAdmitted;
  bool productionLinked;
};

struct ExperimentScalarComparisonInventory {
  std::string_view fixture;
  std::string_view operation;
  std::string_view sourceLocationFact;
  std::string_view comparisonTypeFact;
  bool productionLinked;
};

struct ExperimentSourceMapDebugContract {
  std::string_view fixture;
  std::string_view debugMetadataArtifact;
  std::string_view hirSourceMapArtifact;
  int debugMetadataSchemaVersion;
  int hirSourceMapSchemaVersion;
  bool unfilteredSourceMap;
  bool unpagedSourceMap;
  bool combinedRecordsDisabled;
  bool productionLinked;
};

constexpr ExperimentScaffold currentExperimentScaffold() {
  return {
      "CROSSGL_ENABLE_MLIR_EXPERIMENTAL",
      "tests/fixtures/MinimalComputeShader.cgl",
      false,
  };
}

constexpr ExperimentFixtureSlice scalarExpressionFixtureSlice() {
  return {
      "tests/fixtures/ScalarExpressionComputeShader.cgl",
      "source-location/type/resource facts and source-map/debug preservation facts",
      true,
  };
}

constexpr ExperimentResourceFixtureSlice storageBufferResourceFixtureSlice() {
  return {
      "tests/fixtures/StorageBufferComputeShader.cgl",
      "experimental fixture-limited resource facts and "
      "target-independent resource metadata only",
      "values",
      "storageBuffer",
      0,
      0,
      false,
  };
}

constexpr ExperimentControlFlowFixtureSlice structuredIfControlFlowFixtureSlice() {
  return {
      "tests/fixtures/IfComputeShader.cgl",
      "experimental structured control-flow facts only",
      "if-else",
      true,
      false,
  };
}

constexpr std::array<ExperimentComputeFixture, 4> computeFixtureInventory() {
  return {{
      {
          "tests/fixtures/MinimalComputeShader.cgl",
          "MinimalComputeShader",
          "main",
          "compute",
          {1, 1, 1},
          "minimal-compute-entry",
          "empty-resource-facts",
          "none",
          false,
      },
      {
          "tests/fixtures/ScalarExpressionComputeShader.cgl",
          "ScalarExpressionComputeShader",
          "main",
          "compute",
          {1, 1, 1},
          "straight-line-scalar-expressions",
          "empty-resource-facts",
          "none",
          false,
      },
      {
          "tests/fixtures/StorageBufferComputeShader.cgl",
          "StorageBufferComputeShader",
          "main",
          "compute",
          {1, 1, 1},
          "single-storage-buffer-resource",
          "single-storage-buffer-binding",
          "none",
          false,
      },
      {
          "tests/fixtures/IfComputeShader.cgl",
          "IfComputeShader",
          "main",
          "compute",
          {1, 1, 1},
          "single-structured-if-else",
          "single-storage-buffer-binding",
          "structured-if-else",
          false,
      },
  }};
}

constexpr std::array<ExperimentNamedFact, 37>
sourceLocationInventory() {
  return {{
      {"tests/fixtures/MinimalComputeShader.cgl", "source_file"},
      {"tests/fixtures/MinimalComputeShader.cgl", "shader_module"},
      {"tests/fixtures/MinimalComputeShader.cgl", "compute_stage"},
      {"tests/fixtures/MinimalComputeShader.cgl", "entry_point"},
      {"tests/fixtures/MinimalComputeShader.cgl", "layout_local_size"},
      {"tests/fixtures/MinimalComputeShader.cgl", "return_statement"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "source_file"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "shader_module"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "compute_stage"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "entry_point"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "layout_local_size"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl",
       "local_variable_declarations"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl",
       "scalar_expression_statements"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "return_statement"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "source_file"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "shader_module"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "compute_stage"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "entry_point"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "layout_local_size"},
      {"tests/fixtures/StorageBufferComputeShader.cgl",
       "storage_buffer_declaration"},
      {"tests/fixtures/StorageBufferComputeShader.cgl",
       "local_variable_declarations"},
      {"tests/fixtures/StorageBufferComputeShader.cgl",
       "scalar_expression_statements"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "storage_buffer_write"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "return_statement"},
      {"tests/fixtures/IfComputeShader.cgl", "source_file"},
      {"tests/fixtures/IfComputeShader.cgl", "shader_module"},
      {"tests/fixtures/IfComputeShader.cgl", "compute_stage"},
      {"tests/fixtures/IfComputeShader.cgl", "entry_point"},
      {"tests/fixtures/IfComputeShader.cgl", "layout_local_size"},
      {"tests/fixtures/IfComputeShader.cgl", "storage_buffer_declaration"},
      {"tests/fixtures/IfComputeShader.cgl", "local_variable_declarations"},
      {"tests/fixtures/IfComputeShader.cgl", "storage_buffer_read"},
      {"tests/fixtures/IfComputeShader.cgl", "if_statement"},
      {"tests/fixtures/IfComputeShader.cgl", "then_block_assignment"},
      {"tests/fixtures/IfComputeShader.cgl", "else_block_assignment"},
      {"tests/fixtures/IfComputeShader.cgl", "storage_buffer_write"},
      {"tests/fixtures/IfComputeShader.cgl", "return_statement"},
  }};
}

constexpr ExperimentSourceLocationAnchor sourceLocationAnchorInventory() {
  return {
      "hir.source_location_anchor",
      {
          "source_file",
          "shader_module",
          "compute_stage",
          "entry_point",
          "layout_local_size",
          "return_statement",
      },
      false,
  };
}

constexpr std::array<ExperimentVerifierParityScaffold, 4>
verifierParityScaffoldInventory() {
  return {{
      {
          "tests/fixtures/MinimalComputeShader.cgl",
          true,
          true,
          true,
          true,
          true,
          true,
          true,
          false,
      },
      {
          "tests/fixtures/ScalarExpressionComputeShader.cgl",
          true,
          true,
          true,
          true,
          true,
          true,
          true,
          false,
      },
      {
          "tests/fixtures/StorageBufferComputeShader.cgl",
          true,
          true,
          true,
          true,
          true,
          true,
          true,
          false,
      },
      {
          "tests/fixtures/IfComputeShader.cgl",
          true,
          true,
          true,
          true,
          true,
          true,
          true,
          false,
      },
  }};
}

constexpr std::array<ExperimentNamedFact, 22>
targetIndependentTypeInventory() {
  return {{
      {"tests/fixtures/MinimalComputeShader.cgl", "void_entry_point"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "void_entry_point"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "float_scalar"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "int_scalar"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "bool_scalar"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl", "scalar_literals"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl",
       "constructor_cast_expression"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl",
       "binary_expression_result_types"},
      {"tests/fixtures/ScalarExpressionComputeShader.cgl",
       "comparison_expression_result_type"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "void_entry_point"},
      {"tests/fixtures/StorageBufferComputeShader.cgl", "float_scalar"},
      {"tests/fixtures/StorageBufferComputeShader.cgl",
       "float_pointer_storage_buffer"},
      {"tests/fixtures/StorageBufferComputeShader.cgl",
       "storage_buffer_element_type"},
      {"tests/fixtures/StorageBufferComputeShader.cgl",
       "binary_expression_result_types"},
      {"tests/fixtures/IfComputeShader.cgl", "void_entry_point"},
      {"tests/fixtures/IfComputeShader.cgl", "float_scalar"},
      {"tests/fixtures/IfComputeShader.cgl", "float_pointer_storage_buffer"},
      {"tests/fixtures/IfComputeShader.cgl", "storage_buffer_element_type"},
      {"tests/fixtures/IfComputeShader.cgl", "comparison_expression_result_type"},
      {"tests/fixtures/IfComputeShader.cgl", "branch_condition_bool"},
      {"tests/fixtures/IfComputeShader.cgl", "assignment_expression_result_types"},
      {"tests/fixtures/IfComputeShader.cgl", "unary_expression_result_types"},
  }};
}

constexpr std::array<ExperimentResourceInventory, 2> resourceInventory() {
  return {{
      {
          "tests/fixtures/StorageBufferComputeShader.cgl",
          "values",
          "storageBuffer",
          0,
          0,
          "float*",
          "float",
          "storage",
          "target-independent resource metadata",
          "read_write",
          true,
          true,
          false,
          false,
          false,
          false,
          false,
      },
      {
          "tests/fixtures/IfComputeShader.cgl",
          "values",
          "storageBuffer",
          0,
          0,
          "float*",
          "float",
          "storage",
          "target-independent resource metadata",
          "read_write",
          true,
          true,
          false,
          false,
          false,
          false,
          false,
      },
  }};
}

constexpr ExperimentScalarComparisonInventory scalarComparisonInventory() {
  return {
      "tests/fixtures/ScalarExpressionComputeShader.cgl",
      "hir.scalar_compare",
      "scalar_expression_statements",
      "comparison_expression_result_type",
      false,
  };
}

constexpr ExperimentControlFlowInventory structuredControlFlowInventory() {
  return {
      "tests/fixtures/IfComputeShader.cgl",
      "hir.if",
      "branch_condition_bool",
      {
          "if_statement",
          "then_block_assignment",
          "else_block_assignment",
          "return_statement",
      },
      {
          "branch_condition_bool",
          "assignment_expression_result_types",
          "unary_expression_result_types",
      },
      true,
      false,
      false,
      false,
  };
}

constexpr std::array<ExperimentSourceMapDebugContract, 4>
sourceMapDebugContractInventory() {
  return {{
      {
          "tests/fixtures/MinimalComputeShader.cgl",
          "ir/debug-metadata" ".json",
          "ir/hir-source-map" ".json",
          11,
          7,
          true,
          true,
          true,
          false,
      },
      {
          "tests/fixtures/ScalarExpressionComputeShader.cgl",
          "ir/debug-metadata" ".json",
          "ir/hir-source-map" ".json",
          11,
          7,
          true,
          true,
          true,
          false,
      },
      {
          "tests/fixtures/StorageBufferComputeShader.cgl",
          "ir/debug-metadata" ".json",
          "ir/hir-source-map" ".json",
          11,
          7,
          true,
          true,
          true,
          false,
      },
      {
          "tests/fixtures/IfComputeShader.cgl",
          "ir/debug-metadata" ".json",
          "ir/hir-source-map" ".json",
          11,
          7,
          true,
          true,
          true,
          false,
      },
  }};
}

constexpr ExperimentVerifierHarness builtinVerifierSmokeInput() {
  return {
      "tests/fixtures/mlir/minimal_compute_builtin_module" ".mlir",
      "tests/fixtures/MinimalComputeShader.cgl",
      "mlir-opt",
      "--verify-diagnostics",
      true,
      false,
  };
}

constexpr bool experimentScaffoldIsProductionIsolated() {
  if (currentExperimentScaffold().productionLinked) {
    return false;
  }
  for (const ExperimentComputeFixture &Fixture : computeFixtureInventory()) {
    if (Fixture.productionLinked) {
      return false;
    }
  }
  for (const ExperimentResourceInventory &Resource : resourceInventory()) {
    if (Resource.productionLinked) {
      return false;
    }
  }
  for (const ExperimentSourceMapDebugContract &Contract :
       sourceMapDebugContractInventory()) {
    if (Contract.productionLinked) {
      return false;
    }
  }
  return !structuredControlFlowInventory().productionLinked &&
         !scalarComparisonInventory().productionLinked &&
         !sourceLocationAnchorInventory().productionLinked &&
         !verifierParityScaffoldInventory()[0].productionLinked &&
         !verifierParityScaffoldInventory()[1].productionLinked &&
         !verifierParityScaffoldInventory()[2].productionLinked &&
         !verifierParityScaffoldInventory()[3].productionLinked &&
         !builtinVerifierSmokeInput().productionLinked;
}

constexpr ExperimentVerifierHarness minimalComputeVerifierHarness() {
  return {
      "cglc_mlir_experiment_minimal_compute_verifier",
      "tests/fixtures/MinimalComputeShader.cgl",
      "mlir-opt",
      "--verify-diagnostics",
      true,
      false,
  };
}

static_assert(computeFixtureInventory().size() == 4);
static_assert(sourceLocationInventory().size() == 37);
static_assert(sourceLocationAnchorInventory().operation ==
              "hir.source_location_anchor");
static_assert(sourceLocationAnchorInventory().commonSourceLocationFacts.size() == 6);
static_assert(!sourceLocationAnchorInventory().productionLinked);
static_assert(verifierParityScaffoldInventory().size() == 4);
static_assert(verifierParityScaffoldInventory()[0].coversSourceLocations);
static_assert(verifierParityScaffoldInventory()[0].coversEntryPoint);
static_assert(verifierParityScaffoldInventory()[0].coversResourceFacts);
static_assert(verifierParityScaffoldInventory()[0]
                  .coversTargetIndependentResourceMetadata);
static_assert(verifierParityScaffoldInventory()[0].coversTargetIndependentTypeFacts);
static_assert(verifierParityScaffoldInventory()[0].coversSourceMapDebugFacts);
static_assert(verifierParityScaffoldInventory()[0].futureVerifierGated);
static_assert(targetIndependentTypeInventory().size() == 22);
static_assert(resourceInventory().size() == 2);
static_assert(resourceInventory()[0].descriptorSet == 0);
static_assert(resourceInventory()[0].descriptorBinding == 0);
static_assert(resourceInventory()[0].targetIndependent);
static_assert(!resourceInventory()[0].hasTargetAbiFacts);
static_assert(!resourceInventory()[0].hasTextureFacts);
static_assert(!resourceInventory()[0].hasSamplerFacts);
static_assert(!resourceInventory()[0].hasStorageImageFacts);
static_assert(scalarComparisonInventory().operation == "hir.scalar_compare");
static_assert(!scalarComparisonInventory().productionLinked);
static_assert(structuredControlFlowInventory().structuredOnly);
static_assert(!structuredControlFlowInventory().loopsAdmitted);
static_assert(!structuredControlFlowInventory().earlyReturnsAdmitted);
static_assert(sourceMapDebugContractInventory().size() == 4);
static_assert(sourceMapDebugContractInventory()[0].debugMetadataSchemaVersion == 11);
static_assert(sourceMapDebugContractInventory()[0].hirSourceMapSchemaVersion == 7);
static_assert(sourceMapDebugContractInventory()[0].unfilteredSourceMap);
static_assert(sourceMapDebugContractInventory()[0].unpagedSourceMap);
static_assert(sourceMapDebugContractInventory()[0].combinedRecordsDisabled);
static_assert(experimentScaffoldIsProductionIsolated());

} // namespace crossgl::experimental::mlir
