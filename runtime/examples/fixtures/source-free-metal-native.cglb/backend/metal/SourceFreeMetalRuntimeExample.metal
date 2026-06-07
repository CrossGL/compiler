// Generated Metal source artifact for native runtime evidence.
#include <metal_stdlib>
using namespace metal;

kernel void source_free_metal_main(device float4 *OutputBuffer [[buffer(0)]],
                                   uint index [[thread_position_in_grid]]) {
  OutputBuffer[index] = float4(0.0, 1.0, 0.0, 1.0);
}
