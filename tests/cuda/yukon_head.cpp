#include "strata/kernels/native_mmvq.hpp"
#include "strata/kernels/sampler.hpp"
#include "strata/kernels/verify_kernels.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cuda_runtime.h>
#include <random>
#include <vector>
static void ck(cudaError_t e) {
  if (e != cudaSuccess) {
    fprintf(stderr, "%s\n", cudaGetErrorString(e));
    exit(1);
  }
}
struct Buf {
  void *p;
  size_t n;
  Buf(size_t n) : n(n) { ck(cudaMalloc(&p, n)); }
  ~Buf() { cudaFree(p); }
  template <class T> T *as() { return static_cast<T *>(p); }
};
template <class F> double timed(cudaStream_t s, F f) {
  cudaGraph_t g;
  cudaGraphExec_t e;
  cudaEvent_t a, b;
  ck(cudaStreamBeginCapture(s, cudaStreamCaptureModeGlobal));
  f();
  ck(cudaStreamEndCapture(s, &g));
  ck(cudaGraphInstantiate(&e, g, nullptr, nullptr, 0));
  for (int i = 0; i < 3; ++i)
    ck(cudaGraphLaunch(e, s));
  ck(cudaEventCreate(&a));
  ck(cudaEventCreate(&b));
  ck(cudaEventRecord(a, s));
  for (int i = 0; i < 100; ++i)
    ck(cudaGraphLaunch(e, s));
  ck(cudaEventRecord(b, s));
  ck(cudaEventSynchronize(b));
  float ms;
  ck(cudaEventElapsedTime(&ms, a, b));
  cudaEventDestroy(a);
  cudaEventDestroy(b);
  cudaGraphExecDestroy(e);
  cudaGraphDestroy(g);
  return ms * 1000 / 100;
}
int main() {
  using namespace strata::kernels;
  constexpr int NI = 2560, NO = 248320, MAXT = 5;
  cudaStream_t s;
  ck(cudaStreamCreate(&s));
  std::mt19937 rng(777);
  std::vector<unsigned char> host(native_mmvq_weight_bytes(23, NI, NO));
  for (auto &x : host)
    x = rng();
  for (size_t i = 0; i < host.size(); i += 136) {
    host[i] = 0;
    host[i + 1] = 0x20;
  }
  Buf w(host.size()), x(NI * MAXT * 4), xq(native_q8_1_bytes(NI, MAXT)),
      xil(native_q8_1_il_bytes(NI, MAXT)), yr(NO * MAXT * 4), yc(NO * MAXT * 4),
      tmp(((NO + 1) / 2) * MAXT * 16), ir(MAXT * 4), ic(MAXT * 4),
      fr(MAXT * 16 * 4), fc(MAXT * 4);
  ck(cudaMemcpy(w.p, host.data(), host.size(), cudaMemcpyHostToDevice));
  std::vector<float> hx(NI * MAXT);
  for (auto &v : hx)
    v = (int(rng() % 2001) - 1000) * .001f;
  ck(cudaMemcpy(x.p, hx.data(), hx.size() * 4, cudaMemcpyHostToDevice));
  native_quantize_q8_1(x.as<float>(), xq.p, NI, MAXT, s);
  SamplerParams sp;
  sp.greedy = true;
  sp.temperature = 0;
  for (int t = 1; t <= 5; ++t) {
    auto base = [&] {
      if (native_mmvq_il_supported(23, t, NO)) {
        if (t >= 2)
          native_q8_1_interleave(xq.p, xil.p, NI, t, s);
        native_mmvq_il(23, w.p, xq.p, xil.p, yr.as<float>(), NI, NO, t, s);
      } else
        native_mmvq(23, w.p, xq.p, yr.as<float>(), NI, NO, t, s);
      sample_tokens(yr.as<float>(), t, NO, nullptr, 0, sp, ir.as<int>(), s);
      logits_nonfinite_rows(yr.as<float>(), t, NO, fr.as<unsigned>(), s);
    };
    for (int warm = 0; warm < 500; ++warm)
      base();
    ck(cudaStreamSynchronize(s));
    std::vector<float> ref(NO * t);
    std::vector<int> ids(t);
    ck(cudaMemcpy(ref.data(), yr.p, ref.size() * 4, cudaMemcpyDeviceToHost));
    ck(cudaMemcpy(ids.data(), ir.p, t * 4, cudaMemcpyDeviceToHost));
    for (int rows : {-1, -2, -4, 2, 4, 8}) {
      if (rows < 0) {
        if (t >= 2)
          native_q8_1_interleave(xq.p, xil.p, NI, t, s);
        if (!native_iq4_xs_head_il(w.p, xq.p, xil.p, tmp.p, ic.as<int>(),
                                   fc.as<unsigned>(), NI, NO, t, -rows, s,
                                   yc.as<float>()))
          return 4;
      } else
        native_iq4_xs_head(w.p, xq.p, tmp.p, ic.as<int>(), fc.as<unsigned>(),
                           NI, NO, t, rows, s, yc.as<float>());
      ck(cudaStreamSynchronize(s));
      std::vector<float> got(NO * t);
      std::vector<int> pick(t);
      std::vector<unsigned> flag(t);
      ck(cudaMemcpy(got.data(), yc.p, got.size() * 4, cudaMemcpyDeviceToHost));
      ck(cudaMemcpy(pick.data(), ic.p, t * 4, cudaMemcpyDeviceToHost));
      ck(cudaMemcpy(flag.data(), fc.p, t * 4, cudaMemcpyDeviceToHost));
      size_t diff = 0;
      for (size_t i = 0; i < ref.size(); ++i)
        diff += memcmp(&ref[i], &got[i], 4) != 0;
      if (diff || pick != ids) {
        fprintf(stderr, "FAIL T=%d rows=%d logit_diff=%zu picks_equal=%d\n", t,
                rows, diff, pick == ids);
        return 1;
      }
      for (auto f : flag)
        if (f) {
          fprintf(stderr, "unexpected nonfinite\n");
          return 1;
        }
      auto fused = [&] {
        if (rows < 0) {
          if (t >= 2)
            native_q8_1_interleave(xq.p, xil.p, NI, t, s);
          native_iq4_xs_head_il(w.p, xq.p, xil.p, tmp.p, ic.as<int>(),
                                fc.as<unsigned>(), NI, NO, t, -rows, s);
        } else
          native_iq4_xs_head(w.p, xq.p, tmp.p, ic.as<int>(), fc.as<unsigned>(),
                             NI, NO, t, rows, s);
      };
      double a = timed(s, base), b = timed(s, fused);
      if (rows < 0) {
        auto plain = [&] {
          if (t >= 2)
            native_q8_1_interleave(xq.p, xil.p, NI, t, s);
          native_iq4_xs_head_layout(w.p, xq.p, xil.p, yc.as<float>(), NI, NO, t,
                                    -rows, s);
          sample_tokens(yc.as<float>(), t, NO, nullptr, 0, sp, ic.as<int>(), s);
          logits_nonfinite_rows(yc.as<float>(), t, NO, fr.as<unsigned>(), s);
        };
        plain();
        ck(cudaStreamSynchronize(s));
        ck(cudaMemcpy(got.data(), yc.p, got.size() * 4,
                      cudaMemcpyDeviceToHost));
        if (memcmp(got.data(), ref.data(), got.size() * 4))
          return 5;
        double plain_us = timed(s, plain);
        printf("T=%d rows=%d layout_only_us=%.3f fusion_vs_layout_pct=%.2f\n",
               t, rows, plain_us, (plain_us / b - 1) * 100);
      }
      printf("T=%d rows=%d logits=bitwise top1=PASS reference_us=%.3f "
             "fused_us=%.3f gain_pct=%.2f\n",
             t, rows, a, b, (a / b - 1) * 100);
    }
  }
  // All equal finite logits: lowest vocabulary ID must win in every
  // tile/window.
  ck(cudaMemset(x.p, 0, x.n));
  native_quantize_q8_1(x.as<float>(), xq.p, NI, MAXT, s);
  native_iq4_xs_head(w.p, xq.p, tmp.p, ic.as<int>(), fc.as<unsigned>(), NI, NO,
                     MAXT, 8, s);
  ck(cudaStreamSynchronize(s));
  int ids[MAXT];
  ck(cudaMemcpy(ids, ic.p, sizeof ids, cudaMemcpyDeviceToHost));
  for (int id : ids)
    if (id != 0)
      return 2;
  // Nonfinite weights must still be reported by the fused guard.
  for (size_t i = 0; i < host.size(); i += 136) {
    host[i] = 0;
    host[i + 1] = 0x7c;
  }
  ck(cudaMemcpy(w.p, host.data(), host.size(), cudaMemcpyHostToDevice));
  native_iq4_xs_head(w.p, xq.p, tmp.p, ic.as<int>(), fc.as<unsigned>(), NI, NO,
                     MAXT, 8, s);
  ck(cudaStreamSynchronize(s));
  unsigned flags[MAXT];
  ck(cudaMemcpy(flags, fc.p, sizeof flags, cudaMemcpyDeviceToHost));
  for (auto f : flags)
    if (!f)
      return 3;
  native_q8_1_interleave(xq.p, xil.p, NI, MAXT, s);
  for (int rows : {1, 2, 4}) {
    native_iq4_xs_head_il(w.p, xq.p, xil.p, tmp.p, ic.as<int>(),
                          fc.as<unsigned>(), NI, NO, MAXT, rows, s);
    ck(cudaStreamSynchronize(s));
    ck(cudaMemcpy(flags, fc.p, sizeof flags, cudaMemcpyDeviceToHost));
    for (auto f : flags)
      if (!f)
        return 6;
  }
  for (size_t i = 0; i < host.size(); i += 136) {
    host[i] = 0;
    host[i + 1] = 0x20;
  }
  ck(cudaMemcpy(w.p, host.data(), host.size(), cudaMemcpyHostToDevice));
  for (int rows : {1, 2, 4}) {
    native_iq4_xs_head_il(w.p, xq.p, xil.p, tmp.p, ic.as<int>(),
                          fc.as<unsigned>(), NI, NO, MAXT, rows, s);
    ck(cudaStreamSynchronize(s));
    ck(cudaMemcpy(ids, ic.p, sizeof ids, cudaMemcpyDeviceToHost));
    for (int id : ids)
      if (id != 0)
        return 7;
  }
  puts("PASS full-size logits, top1, ties and nonfinite guard");
  cudaStreamDestroy(s);
}
