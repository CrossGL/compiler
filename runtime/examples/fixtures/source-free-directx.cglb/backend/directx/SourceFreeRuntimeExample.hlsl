// Generated HLSL artifact for the runtime loader boundary example.
RWStructuredBuffer<float4> OutputBuffer : register(u0, space0);

[numthreads(1, 1, 1)]
void source_free_main(uint3 dispatchThreadId : SV_DispatchThreadID) {
  OutputBuffer[dispatchThreadId.x] = float4(1.0, 0.0, 0.0, 1.0);
}
