#ifndef CrossGL_DIALECT
#define CrossGL_DIALECT

include "mlir/IR/OpBase.td"

def Crossgl_Dialect : Dialect {
    let name = "crossgl";
    let summary = "crossgl compiler MLIR dialect.";
    let description = [{

        by the crossgl team!

    }];
    let cppNamespace = "::crossgl";
    let hasConstantMaterializer = 1;
}

class Crossgl_Op<string mnemonic, list<Trait> traits = []> :
        Op<Crossgl_Dialect, mnemonic, traits>;

#endif // CrossGL_DIALECT
