#include "strata/prefill/gemm.hpp"
#include <cmath>
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
  for (int i = 0; i < 3; ++i)
    f();
  cudaEvent_t a, b;
  ck(cudaEventCreate(&a));
  ck(cudaEventCreate(&b));
  ck(cudaEventRecord(a, s));
  for (int i = 0; i < 50; ++i)
    f();
  ck(cudaEventRecord(b, s));
  ck(cudaEventSynchronize(b));
  float ms;
  ck(cudaEventElapsedTime(&ms, a, b));
  cudaEventDestroy(a);
  cudaEventDestroy(b);
  return ms * 20;
}
int main() {
  constexpr int K = 2560, H = 48;
  cudaStream_t s;
  ck(cudaStreamCreate(&s));
  strata::prefill::Gemm g;
  std::string err;
  if (!g.init(s, 0, err)) {
    fprintf(stderr, "%s\n", err.c_str());
    return 1;
  }
  std::mt19937 rng(815);
  std::normal_distribution<float> nd(0, 1);
  auto bf = [&](size_t n, float scale) {
    std::vector<uint16_t> x(n);
    for (auto &b : x) {
      float v = nd(rng) * scale;
      unsigned u;
      memcpy(&u, &v, 4);
      b = uint16_t((u + 0x7fff + ((u >> 16) & 1)) >> 16);
    }
    return x;
  };
  auto hw = bf(2 * H * K, .02);
  Buf w(hw.size() * 2);
  ck(cudaMemcpy(w.p, hw.data(), w.n, cudaMemcpyHostToDevice));
  for (int T : {1, 7, 128, 512, 4096}) {
    auto hx = bf(T * K, 1), hl = bf(T * K, .001);
    Buf x(hx.size() * 2), lo(hl.size() * 2), a(T * 2 * H * 4), b(T * 2 * H * 4);
    ck(cudaMemcpy(x.p, hx.data(), x.n, cudaMemcpyHostToDevice));
    ck(cudaMemcpy(lo.p, hl.data(), lo.n, cudaMemcpyHostToDevice));
    for (bool low : {false, true}) {
      auto base = [&] {
        for (int half = 0; half < 2; ++half) {
          g.bf16(x.as<uint16_t>(), w.as<uint16_t>() + half * H * K,
                 a.as<float>() + half * H, T, H, K, 2 * H);
          if (low)
            g.bf16(lo.as<uint16_t>(), w.as<uint16_t>() + half * H * K,
                   a.as<float>() + half * H, T, H, K, 2 * H, 1);
        }
      };
      auto pair = [&] {
        g.bf16(x.as<uint16_t>(), w.as<uint16_t>(), b.as<float>(), T, 2 * H, K);
        if (low)
          g.bf16(lo.as<uint16_t>(), w.as<uint16_t>(), b.as<float>(), T, 2 * H,
                 K, 0, 1);
      };
      base();
      pair();
      ck(cudaStreamSynchronize(s));
      std::vector<float> va(T * 2 * H), vb(va.size());
      ck(cudaMemcpy(va.data(), a.p, a.n, cudaMemcpyDeviceToHost));
      ck(cudaMemcpy(vb.data(), b.p, b.n, cudaMemcpyDeviceToHost));
      size_t diff = 0;
      double maxabs = 0;
      for (size_t i = 0; i < va.size(); ++i) {
        diff += memcmp(&va[i], &vb[i], 4) != 0;
        maxabs = fmax(maxabs, fabs(va[i] - vb[i]));
        if (!std::isfinite(vb[i]))
          return 1;
      }
      double ta = timed(s, base), tb = timed(s, pair);
      printf("T=%d low=%d bit_differences=%zu max_abs=%.9g separate_us=%.3f "
             "grouped_us=%.3f gain_pct=%.2f\n",
             T, low, diff, maxabs, ta, tb, (ta / tb - 1) * 100);
      if (maxabs > 1e-4)
        return 2;
    }
  }
  puts("PASS finite projections within 1e-4; bitwise differences reported "
       "separately");
}
