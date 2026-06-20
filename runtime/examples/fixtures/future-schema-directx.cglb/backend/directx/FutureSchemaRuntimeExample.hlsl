// Generated HLSL artifact that must not override schema admission failure.
RWStructuredBuffer<float4> OutputBuffer : register(u0, space0);

[numthreads(1, 1, 1)]
void future_schema_main(uint3 dispatchThreadId : SV_DispatchThreadID) {
  OutputBuffer[dispatchThreadId.x] = float4(0.0, 0.0, 0.0, 1.0);
}
