#include "mlir/IR/Builders.h"
#include "mlir/IR/OpImplementation.h"

#include "Crossgl/CrossglDialect.h"
#include "Crossgl/CrossglOps.h"

using namespace mlir;
using namespace crossgl;


#include "Crossgl/CrossglOpsDialect.cpp.inc"

void CrossglDialect::initialize() {
  addOperations<
#define GET_OP_LIST
#include "Crossgl/CrossglOps.cpp.inc"
      >();
}

void crossgl::ConstantOp::build(mlir::OpBuilder &builder,
                              mlir::OperationState &state, double value) {
  auto dataType = RankedTensorType::get({}, builder.getF64Type());
  auto dataAttribute = DenseElementsAttr::get(dataType, value);
  crossgl::ConstantOp::build(builder, state, dataType, dataAttribute);
}

mlir::Operation *CrossglDialect::materializeConstant(mlir::OpBuilder &builder,
                                                   mlir::Attribute value,
                                                   mlir::Type type,
                                                   mlir::Location loc) {
  return builder.create<crossgl::ConstantOp>(
      loc, type, value.cast<mlir::DenseElementsAttr>());
}
