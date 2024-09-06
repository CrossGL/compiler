#ifndef MLIR_CrossGL_PASSES_H
#define MLIR_CrossGL_PASSES_H

#include <memory>

#include "mlir/Pass/Pass.h"

namespace crossgl {
std::unique_ptr<mlir::Pass> createLowerToAffinePass();
std::unique_ptr<mlir::Pass> createLowerToLLVMPass();
} 

#endif 
