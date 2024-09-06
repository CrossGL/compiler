add_mlir_dialect_library(MLIRCrossgl
		CrossglDialect.cpp
		CrossglOps.cpp
		LowerToAffine.cpp
		LowerToLLVM.cpp

        ADDITIONAL_HEADER_DIRS
        ${PROJECT_SOURCE_DIR}/include/Crossgl

        DEPENDS
        MLIRCrossglOpsIncGen

	LINK_LIBS PUBLIC
	MLIRIR
	)
