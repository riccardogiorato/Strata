// Q4_K selector storage checked against GGML's independent CPU dequantizer.
#include "strata/kernels/dflash2.hpp"
#include "ggml.h"
#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>
#include <random>
#include <stdexcept>
#include <vector>
static void ck(cudaError_t e) { if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e)); }
template<class T> struct Device {
 T* p=nullptr;explicit Device(size_t n){ck(cudaMalloc(&p,n*sizeof(T)));}
 explicit Device(const std::vector<T>& v):Device(v.size()){ck(cudaMemcpy(p,v.data(),v.size()*sizeof(T),cudaMemcpyHostToDevice));}
 ~Device(){cudaFree(p);} std::vector<T> read(size_t n){std::vector<T> v(n);ck(cudaMemcpy(v.data(),p,n*sizeof(T),cudaMemcpyDeviceToHost));return v;}
};
int main(){
 int n=0;if(cudaGetDeviceCount(&n)!=cudaSuccess||n<1)return 77;
 try {
  auto* ctx=ggml_init({16<<20,nullptr,true});if(!ctx)throw std::runtime_error("ggml init");
  int tests=0;std::mt19937 rng(7320);std::uniform_real_distribution<float> dist(-1.5f,1.5f);
  for(int rank:{256,512,1024})for(int seed=0;seed<5;++seed){
   const int vocab=128;size_t count=size_t(vocab)*rank;
   std::vector<float> prev(count),next(count),pflat(count),nflat(count);
   for(auto& x:prev)x=dist(rng);for(auto& x:next)x=dist(rng);
   std::vector<unsigned char> pq(count/256*144),nq(pq.size());
   if(ggml_quantize_chunk(GGML_TYPE_Q4_K,prev.data(),pq.data(),0,vocab,rank,nullptr)!=pq.size())throw std::runtime_error("quantize size");
   ggml_quantize_chunk(GGML_TYPE_Q4_K,next.data(),nq.data(),0,vocab,rank,nullptr);
   ggml_get_type_traits(GGML_TYPE_Q4_K)->to_float(pq.data(),pflat.data(),count);
   ggml_get_type_traits(GGML_TYPE_Q4_K)->to_float(nq.data(),nflat.data(),count);
   Device<float> dp(pflat),dn(nflat);Device<unsigned char> dqp(pq),dqn(nq);
   for(int rows:{2,4,8})for(int top:{1,16,64}){
    std::vector<int32_t> ids(rows*top);std::vector<float> unary(rows*top),hidden(rows*rank);
    for(int row=0;row<rows;++row)for(int k=0;k<top;++k){ids[row*top+k]=(k*17+row*11)%vocab;unary[row*top+k]=seed==0?0:dist(rng);}
    for(auto& x:hidden)x=seed==0?0:dist(rng);
    Device<int32_t> di(ids),anchor(std::vector<int32_t>{seed==0?0:127}),a(rows),b(rows),c(rows);
    Device<float> du(unary),dh(hidden),ac(rows),bc(rows),cc(rows);
    strata::kernels::dflash2_select(di.p,du.p,dh.p,dp.p,dn.p,anchor.p,a.p,ac.p,rows,top,rank,nullptr);
    strata::kernels::dflash2_select_q4_k(di.p,du.p,dh.p,dqp.p,dqn.p,anchor.p,b.p,bc.p,rows,top,rank,nullptr);
    strata::kernels::dflash2_select_q4_k(di.p,du.p,dh.p,dqp.p,dqn.p,anchor.p,c.p,cc.p,rows,top,rank,nullptr,true);
    ck(cudaDeviceSynchronize());auto av=a.read(rows-1),bv=b.read(rows-1),cv=c.read(rows-1);
    auto af=ac.read(rows-1),bf=bc.read(rows-1),cf=cc.read(rows-1);
    if(av!=bv||av!=cv)throw std::runtime_error("candidate IDs differ from GGML-dequantized oracle");
    for(int i=0;i<rows-1;++i)if(!std::isfinite(bf[i])||std::abs(af[i]-bf[i])>3e-5f||std::abs(af[i]-cf[i])>3e-5f)throw std::runtime_error("selector confidence mismatch");
    ++tests;
   }
  }
  ggml_free(ctx);std::printf("PASS: %d GGML Q4_K selector oracle cases (ties, rows 2/4/8, top-k 1/16/64, rank 256/512/1024)\n",tests);
  return 0;
 }catch(const std::exception& e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}
}
