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
  float *p;
  size_t n;
  Buf(size_t n) : n(n) { ck(cudaMalloc(&p, n * 4)); }
  ~Buf() { cudaFree(p); }
  void set(const std::vector<float> &v) {
    ck(cudaMemcpy(p, v.data(), n * 4, cudaMemcpyHostToDevice));
  }
  std::vector<float> get() {
    std::vector<float> v(n);
    ck(cudaMemcpy(v.data(), p, n * 4, cudaMemcpyDeviceToHost));
    return v;
  }
};
template <class F> double timed(cudaStream_t s, F f) {
  cudaGraph_t g;
  cudaGraphExec_t e;
  cudaEvent_t a, b;
  ck(cudaStreamBeginCapture(s, cudaStreamCaptureModeGlobal));
  f();
  ck(cudaStreamEndCapture(s, &g));
  ck(cudaGraphInstantiate(&e, g, nullptr, nullptr, 0));
  for (int i = 0; i < 10; ++i)
    ck(cudaGraphLaunch(e, s));
  ck(cudaEventCreate(&a));
  ck(cudaEventCreate(&b));
  ck(cudaEventRecord(a, s));
  for (int i = 0; i < 200; ++i)
    ck(cudaGraphLaunch(e, s));
  ck(cudaEventRecord(b, s));
  ck(cudaEventSynchronize(b));
  float ms;
  ck(cudaEventElapsedTime(&ms, a, b));
  cudaEventDestroy(a);
  cudaEventDestroy(b);
  cudaGraphExecDestroy(e);
  cudaGraphDestroy(g);
  return ms * 5;
}
int main() {
  using namespace strata::kernels;
  constexpr int HK = 16, HV = 48, C = 10240, V = 6144, MT = 8,
                SN = 128 * 128 * HV;
  cudaStream_t stream;
  ck(cudaStreamCreate(&stream));
  std::mt19937 rng(531);
  std::uniform_real_distribution<float> d(-.05f, .05f);
  auto random = [&](size_t n) {
    std::vector<float> v(n);
    for (auto &x : v)
      x = d(rng);
    return v;
  };
  Buf saved(MT * (C + 2 * HV)), ref(SN), cand(SN), prev(C * MT), h(C * MT),
      pg(HV * MT), pb(HV * MT), gate(HV * MT), beta(HV * MT), z(V * MT),
      gamma(128), yr(V * MT), yc(V * MT);
  auto initial = random(SN);
  prev.set(random(prev.n));
  h.set(random(h.n));
  z.set(random(z.n));
  pg.set(std::vector<float>(pg.n, -.1f));
  gate.set(std::vector<float>(gate.n, -.1f));
  pb.set(std::vector<float>(pb.n, .5f));
  beta.set(std::vector<float>(beta.n, .5f));
  gamma.set(std::vector<float>(128, 1));
  int *keep;
  ck(cudaMalloc(&keep, 4));
  for (int T = 1; T <= MT; ++T)
    for (int K = 0; K <= MT; ++K) {
      ref.set(initial);
      cand.set(initial);
      ck(cudaMemset(yr.p, 0, yr.n * 4));
      ck(cudaMemset(yc.p, 0, yc.n * 4));
      ck(cudaMemcpy(keep, &K, 4, cudaMemcpyHostToDevice));
      auto base = [&] {
        gdn_step_norm_multi(ref.p, prev.p, C, pg.p, pb.p, z.p, gamma.p, 1e-6f,
                            yr.p, HK, HV, MT, keep, stream, MT);
        gdn_step_norm_multi(ref.p, h.p, C, gate.p, beta.p, z.p, gamma.p, 1e-6f,
                            yr.p, HK, HV, T, nullptr, stream);
      };
      auto fused = [&] {
        gdn_save_pending(prev.p, pg.p, pb.p, saved.p, C, HV, MT, keep, stream);
        gdn_step_norm_deferred(cand.p, saved.p, saved.p + MT * C,
                               saved.p + MT * (C + HV), 0, h.p, C, gate.p,
                               beta.p, z.p, gamma.p, 1e-6f, yc.p, HK, HV, T,
                               stream, keep);
      };
      base();
      fused();
      ck(cudaStreamSynchronize(stream));
      auto sr = ref.get(), sc = cand.get(), ar = yr.get(), ac = yc.get();
      if (memcmp(sr.data(), sc.data(), SN * 4) ||
          memcmp(ar.data(), ac.data(), T * V * 4)) {
        size_t ds = 0, dy = 0;
        for (int i = 0; i < SN; ++i)
          ds += memcmp(&sr[i], &sc[i], 4) != 0;
        for (int i = 0; i < T * V; ++i)
          dy += memcmp(&ar[i], &ac[i], 4) != 0;
        fprintf(stderr, "FAIL T=%d keep=%d state=%zu output=%zu\n", T, K, ds,
                dy);
        return 1;
      }
      cand.set(initial);
      gdn_flush_pending(cand.p, SN, prev.p, MT * C, pg.p, pb.p, MT * HV, C, HK,
                        HV, 1, keep, stream);
      ck(cudaStreamSynchronize(stream));
      sc = cand.get();
      if (memcmp(sr.data(), sc.data(), SN * 4)) {
        fprintf(stderr, "FAIL boundary flush T=%d K=%d\n", T, K);
        return 2;
      }
      if (K) {
        double a = timed(stream, base), b = timed(stream, fused);
        printf("T=%d keep=%d bitwise=PASS reference_us=%.3f fused_us=%.3f "
               "gain_pct=%.2f\n",
               T, K, a, b, (a / b - 1) * 100);
      }
    }
  // Production self-commits T1 in the output kernel. Compare that path too,
  // not only the separate state-only commit used by wider windows.
  ref.set(initial);
  cand.set(initial);
  const int one = 1;
  ck(cudaMemcpy(keep, &one, 4, cudaMemcpyHostToDevice));
  gdn_step_norm_multi(ref.p, prev.p, C, pg.p, pb.p, z.p, gamma.p, 1e-6f, yr.p,
                      HK, HV, 1, keep, stream);
  gdn_step_norm_deferred(cand.p, nullptr, nullptr, nullptr, 0, prev.p, C, pg.p,
                         pb.p, z.p, gamma.p, 1e-6f, yc.p, HK, HV, 1, stream);
  gdn_flush_pending(cand.p, SN, prev.p, MT * C, pg.p, pb.p, MT * HV, C, HK, HV,
                    1, keep, stream);
  ck(cudaStreamSynchronize(stream));
  auto sr = ref.get(), sc = cand.get(), ar = yr.get(), ac = yc.get();
  if (memcmp(sr.data(), sc.data(), SN * 4) ||
      memcmp(ar.data(), ac.data(), V * 4)) {
    fprintf(stderr, "FAIL single-token self-commit parity\n");
    return 3;
  }
  puts("PASS single-token self-commit parity");
  cudaFree(keep);
  cudaStreamDestroy(stream);
  puts("PASS all 72 accepted-prefix/window combinations");
}
