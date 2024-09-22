#ifndef CrossGL_OPS
#define CrossGL_OPS

include "CrossglDialect.td"
include "mlir/Interfaces/SideEffectInterfaces.td"

def ConstantOp : Crossgl_Op<"constant", [Pure]> {
  let summary = "constant";
  let description = [{
    Constant operation turns a literal into an SSA value. The data is attached
    to the operation as an attribute. For example:

    ```mlir
      %0 = "crossgl.constant"()
      { value = dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf64> }
      : () -> tensor<2x3xf64>
    ```
  }];

  let builders = [
    OpBuilder<(ins "mlir::DenseElementsAttr":$value), [{
      build($_builder, $_state, value.getType(), value);
    }]>,
    OpBuilder<(ins "double":$value)>
  ];

//  let parser = [{ return ::parseConstantOp(parser, result); }];
  let arguments = (ins F64ElementsAttr:$value);
  let results = (outs F64Tensor);
}

def PrintOp : Crossgl_Op<"print", [Pure]> {
    let summary = "print operation";
    let description = [{
        The "print" builtin operation prints a given input tensor, and produces
        no results.
    }];

    // The print operation takes an input tensor to print.
    let arguments = (ins AnyTypeOf<[F64Tensor, F64MemRef]>:$input);

    let assemblyFormat = "$input attr-dict `:` type($input)";
}

def WorldOp : Crossgl_Op<"world", [Pure]> {
    let summary = "print Hello, World";
    let description = [{
        The "world" operation prints 
        no results.
    }];
}

def AddOp : Crossgl_Op<"add", [Pure]> {
    let summary = "element-wise addition operation";
    let description = [{
        The "add" operation performs element-wise addition between two tensors.
        The shapes of the tensor operands are expected to match.
    }];

    let arguments = (ins F64Tensor:$lhs, F64Tensor:$rhs);
    let results = (outs F64Tensor);

    let hasCustomAssemblyFormat = 1;

    let builders = [
        OpBuilder<(ins "Value": $lhs, "Value": $rhs)>
    ];
}

def SubtractOp : Crossgl_Op<"subtract",[Pure]>{
    let summary = "element-wise subtraction operation";
    let description = [{
        The "subtract" operation performs element-wise subtraction between two tensors.
        The shapes of the tensor operands are expected to match.
    }];

    let arguments = (ins F64Tensor:$lhs, F64Tensor:$rhs);
    let results = (outs F64Tensor);

    let hasCustomAssemblyFormat = 1;

    let builders = [
        OpBuilder<(ins "Value": $lhs, "Value": $rhs)>
    ];

}

def MultiplyOp : Crossgl_Op<"multiply",
        [ Pure]> {
    let summary = "element-wise multiplication operation";
    let description = [{
         The "multiplication" operation performs element-wise multiplication between two tensors.
         The shapes of the tensor operands are expected to match.
    }];

    let arguments = (ins F64Tensor:$lhs , F64Tensor:$rhs);
    let results = (outs F64Tensor);

    let hasCustomAssemblyFormat = 1;

    let builders = [
        OpBuilder<(ins "Value": $lhs, "Value": $rhs)>
    ];

}

def DivideOp : Crossgl_Op<"divide",
        [ Pure]> {
    let summary = "element-wise division operation";
    let description = [{
        The "division" operation performs element-wise division between teo tensors.
        The shapes of the tensor operands are expected to match.

    }];

    let arguments = (ins F64Tensor:$lhs , F64Tensor:$rhs);
    let results = (outs F64Tensor);

    let hasCustomAssemblyFormat = 1;

    let builders = [
        OpBuilder<(ins "Value": $lhs, "Value": $rhs)>
    ];

}

















#endif 
