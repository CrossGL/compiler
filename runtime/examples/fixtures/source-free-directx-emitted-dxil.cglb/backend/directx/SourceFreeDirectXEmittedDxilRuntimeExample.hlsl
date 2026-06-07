// Generated HLSL source artifact for emitted DirectX DXIL fixture.
RWStructuredBuffer<float4> OutputBuffer : register(u0, space0);

[numthreads(1, 1, 1)]
void source_free_directx_emitted_dxil_main(
    uint3 dispatchThreadId : SV_DispatchThreadID) {
  OutputBuffer[dispatchThreadId.x] = float4(0.25, 0.5, 0.75, 1.0);
}
