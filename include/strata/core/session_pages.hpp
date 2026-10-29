#pragma once
// Linux-only opt-in shared page storage for native session serialization. Page boundaries are reset at each
// tensor, so identical leading KV bytes share objects across branches of different lengths. The serializer still
// verifies the complete native session before any device write. This is trusted-cache integrity, not authentication.
#include "strata/core/conversation_file.hpp"
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <list>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <unordered_map>
#ifndef _WIN32
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#endif
namespace strata::core::session_pages {
constexpr size_t page_bytes = 2u << 20;
constexpr char magic[8] = {'S','T','R','P','A','G','E','1'};
struct Ref { uint64_t bytes = 0, a = 0, b = 0; };
inline std::string name(const Ref& r) {
    char s[40]; std::snprintf(s, sizeof(s), "%016llx%016llx.blk", (unsigned long long)r.a, (unsigned long long)r.b);
    return s;
}
inline Ref identify(const uint8_t* p, size_t n) {
    return {n, session_hash64(p,n,0x5041474531ull), session_hash64(p,n,0x5041474532ull)};
}
class Failure : public std::runtime_error {
public:
    SessionError kind;
    Failure(const std::string& s,SessionError k):std::runtime_error("paged session: "+s),kind(k) {}
};
inline void fail(const std::string& s) { throw Failure(s,SessionError::invalid); }
inline void io_fail(const std::string& s,int code=errno) {
    const bool storage=code==ENOSPC || code==EFBIG
#ifdef EDQUOT
        || code==EDQUOT
#endif
        ;
    const auto kind=code==ENOMEM ? SessionError::memory : storage ? SessionError::storage : SessionError::io;
    throw Failure(s+": "+std::strerror(code),kind);
}
inline void inject(const std::function<int(const char*)>& fault,const char* step) {
    if(fault) {const int e=fault(step);if(e)io_fail(step,e);}
}
#ifndef _WIN32
struct Fd {
    int value = -1;
    explicit Fd(int x = -1): value(x) {}
    ~Fd() { if(value >= 0) ::close(value); }
    Fd(const Fd&) = delete; Fd& operator=(const Fd&) = delete;
};
inline void write_all(int fd, const uint8_t* p, size_t n) {
    while(n) { auto z=::write(fd,p,n); if(z<0 && errno==EINTR)continue;
        if(z<=0)io_fail("write");
        p+=z;n-=z; }
}
inline std::vector<uint8_t> read_file(const std::filesystem::path& p, size_t maximum) {
    Fd fd(::open(p.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC));
    if(fd.value<0)io_fail("open " + p.filename().string());
    struct stat st{};
    if(::fstat(fd.value,&st) || !S_ISREG(st.st_mode) || st.st_nlink!=1 || st.st_size<0 || uint64_t(st.st_size)>maximum)
        fail("invalid file " + p.filename().string());
    std::vector<uint8_t> out(size_t(st.st_size)); size_t at=0;
    while(at<out.size()) { auto z=::read(fd.value,out.data()+at,out.size()-at); if(z<0&&errno==EINTR)continue;
        if(z<=0)io_fail("short read",z<0?errno:EIO);
        at+=z; }
    return out;
}
inline void sync_dir(const std::filesystem::path& p) {
    Fd fd(::open(p.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
    if(fd.value<0 || (::fsync(fd.value) && errno!=EINVAL))io_fail("directory flush");
}
inline void atomic_file(const std::filesystem::path& path, const std::vector<uint8_t>& bytes, bool durable, const std::function<int(const char*)>& fault={}) {
    std::string pattern=(path.parent_path()/".page-tmp-XXXXXX").string();
    std::vector<char> tmp(pattern.begin(),pattern.end());tmp.push_back(0);
    Fd fd(::mkstemp(tmp.data())); if(fd.value<0)io_fail("create temporary file");
    try {
        inject(fault,"write");write_all(fd.value,bytes.data(),bytes.size());
        if(durable) {inject(fault,"file_flush");if(::fsync(fd.value))io_fail("file flush");}
        inject(fault,"rename");if(::rename(tmp.data(),path.c_str()))io_fail("publish");
    } catch(...) { ::unlink(tmp.data());throw; }
}
class Lock {
    Fd fd_;
public:
    Lock(const std::filesystem::path& root, bool write):fd_(::open((root/".pages.lock").c_str(),O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600)) {
        struct stat st{};
        if(fd_.value<0 || ::fstat(fd_.value,&st) || !S_ISREG(st.st_mode) || st.st_nlink!=1 || ::flock(fd_.value,write?LOCK_EX:LOCK_SH))io_fail("cache lock");
    }
};
#else
inline std::vector<uint8_t> read_file(const std::filesystem::path&, size_t) { fail("not enabled on Windows");return {}; }
inline void sync_dir(const std::filesystem::path&) { fail("not enabled on Windows"); }
inline void atomic_file(const std::filesystem::path&,const std::vector<uint8_t>&,bool,const std::function<int(const char*)>& = {}) { fail("not enabled on Windows"); }
class Lock { public: Lock(const std::filesystem::path&,bool) { fail("not enabled on Windows"); } };
#endif
inline uint64_t hot_limit() {
    const char* p=std::getenv("STRATA_SESSION_PAGE_HOT_MIB");
    if(!p)return 256ull<<20;
    char* e=nullptr; auto n=std::strtoull(p,&e,10);
    if(!*p || *e || n>16384)fail("invalid hot-page budget (0..16384 MiB)");
    return n<<20;
}
class HotCache {
    struct Entry {std::shared_ptr<const std::vector<uint8_t>> data; std::list<std::string>::iterator pos;};
    std::unordered_map<std::string,Entry> entries_; std::list<std::string> order_; size_t bytes_=0;
    std::mutex mutex_;
public:
    std::shared_ptr<const std::vector<uint8_t>> get(const std::string& key) {
        std::lock_guard<std::mutex> lock(mutex_);auto i=entries_.find(key);if(i==entries_.end())return {};
        order_.splice(order_.begin(),order_,i->second.pos);return i->second.data;
    }
    void put(const std::string& key,std::shared_ptr<const std::vector<uint8_t>> data) {
        std::lock_guard<std::mutex> lock(mutex_);const auto cap=hot_limit();if(!cap || data->size()>cap)return;
        if(entries_.count(key))return;
        while(bytes_+data->size()>cap && !order_.empty()) {
            auto k=order_.back();bytes_-=entries_.at(k).data->size();entries_.erase(k);order_.pop_back();
        }
        order_.push_front(key);
        const size_t added=data->size();
        try {entries_.emplace(key,Entry{std::move(data),order_.begin()});}
        catch(...) {order_.pop_front();throw;}
        bytes_+=added;
    }
    void clear() {std::lock_guard<std::mutex> lock(mutex_);entries_.clear();order_.clear();bytes_=0;}
};
inline HotCache& hot() {static HotCache c;return c;}
inline std::shared_ptr<const std::vector<uint8_t>> load_page(const std::filesystem::path& root,const Ref& ref,bool& hit) {
    const auto path=root/"pages"/name(ref);const auto key=path.string();
    if(std::filesystem::is_symlink(path))fail("page is a symbolic link");
    if(auto x=hot().get(key)) {if(x->size()!=ref.bytes)fail("page size mismatch");hit=true;return x;}
    auto data=std::make_shared<std::vector<uint8_t>>(read_file(path,page_bytes));
    const auto got=identify(data->data(),data->size());
    if(got.bytes!=ref.bytes || got.a!=ref.a || got.b!=ref.b)fail("page checksum mismatch");
    hit=false;hot().put(key,data);return data;
}
inline void u64(std::vector<uint8_t>& b,uint64_t v) {auto p=reinterpret_cast<const uint8_t*>(&v);b.insert(b.end(),p,p+8);}
class Writer {
    std::filesystem::path path_,root_;Lock lock_;
    std::vector<uint8_t> pending_;std::vector<Ref> refs_;std::vector<int32_t> ids_;std::vector<uint64_t> checkpoints_;
    uint64_t flags_=0,logical_=0,new_=0,reused_=0;bool durable_;SessionStatus* status_=nullptr;
    std::function<int(const char*)> fault_;
    void flush() {
        if(pending_.empty())return;
        const Ref ref=identify(pending_.data(),pending_.size());const auto path=root_/"pages"/name(ref);
        if(std::filesystem::exists(path)) {
            bool hit=false;auto old=load_page(root_,ref,hit);
            if(*old!=pending_)fail("page hash collision");
            reused_+=pending_.size();
        } else {
            atomic_file(path,pending_,durable_,fault_);new_+=pending_.size();
            hot().put(path.string(),std::make_shared<const std::vector<uint8_t>>(pending_));
        }
        refs_.push_back(ref);pending_.clear();
    }
public:
    Writer(const std::string& path,const SavedConversation& meta,const SessionWriteOptions& options,SessionStatus* status=nullptr):path_(std::filesystem::absolute(path)),root_(path_.parent_path()),lock_(root_,true),ids_(meta.live.ids),durable_(options.durable),status_(status),fault_(options.fault) {
        const auto pages=root_/"pages";
        std::filesystem::create_directory(pages);
        if(std::filesystem::is_symlink(pages) || !std::filesystem::is_directory(pages))fail("invalid pages directory");
#ifndef _WIN32
        ::chmod(pages.c_str(),0700);
#endif
        flags_=(meta.cvec?2:0) | (!meta.live.imgs.empty()?1:0);
        for(const auto& c:meta.checkpoints) {
            if(!c.imgs.empty())flags_|=1;
            if(c.ids.size()<=ids_.size() && std::equal(c.ids.begin(),c.ids.end(),ids_.begin()))checkpoints_.push_back(c.ids.size());
        }
        pending_.reserve(page_bytes);
    }
    void append(const void* p,size_t n) {
        const auto* s=static_cast<const uint8_t*>(p);logical_+=n;
        while(n) {size_t k=std::min(n,page_bytes-pending_.size());pending_.insert(pending_.end(),s,s+k);s+=k;n-=k;if(pending_.size()==page_bytes)flush();}
    }
    void boundary() {flush();}
    void finish() {
        flush();std::vector<uint8_t> b(magic,magic+8);
        for(auto n:{logical_,uint64_t(refs_.size()),uint64_t(ids_.size()),uint64_t(checkpoints_.size()),flags_})u64(b,n);
        if(!ids_.empty()) {auto p=reinterpret_cast<const uint8_t*>(ids_.data());b.insert(b.end(),p,p+4*ids_.size());}
        for(auto n:checkpoints_)u64(b,n);
        for(const auto& r:refs_) {u64(b,r.bytes);u64(b,r.a);u64(b,r.b);}
        u64(b,session_hash64(b.data(),b.size(),0x4d414e4946455354ull));
        if(durable_)sync_dir(root_/"pages");
        atomic_file(path_,b,durable_,fault_);if(status_)status_->published=true;
        if(durable_) {inject(fault_,"dir_flush");sync_dir(root_);}
        std::fprintf(stderr,"strata paged cache: saved logical=%llu new=%llu shared=%llu pages=%zu manifest=%zu\n",(unsigned long long)logical_,(unsigned long long)new_,(unsigned long long)reused_,refs_.size(),b.size());
    }
};
class Reader {
    std::filesystem::path root_;Lock lock_;std::vector<Ref> refs_;size_t index_=0,offset_=0;
    uint64_t size_=0,hot_bytes_=0,disk_bytes_=0;
    std::shared_ptr<const std::vector<uint8_t>> current_;
public:
    explicit Reader(const std::string& path):root_(std::filesystem::absolute(path).parent_path()),lock_(root_,false) {
        auto b=read_file(path,64u<<20);size_t at=8;
        auto get=[&]() {if(at+8>b.size())fail("short manifest");uint64_t n;std::memcpy(&n,b.data()+at,8);at+=8;return n;};
        if(b.size()<56 || std::memcmp(b.data(),magic,8))fail("bad manifest");
        size_=get();auto nr=get(),ni=get(),nc=get();(void)get();
        if(nr>1048576 || ni>4194304 || nc>65536 || b.size()!=56+ni*4+nc*8+nr*24)fail("manifest bounds");
        uint64_t sum=0;at+=ni*4+nc*8;
        for(uint64_t i=0;i<nr;++i) {Ref r{get(),get(),get()};if(!r.bytes || r.bytes>page_bytes || sum>UINT64_MAX-r.bytes)fail("page bounds");sum+=r.bytes;refs_.push_back(r);}
        auto checksum=get();if(sum!=size_ || checksum!=session_hash64(b.data(),b.size()-8,0x4d414e4946455354ull))fail("manifest checksum/size");
    }
    uint64_t size() const {return size_;}
    long long read_some(uint8_t* dst,size_t n) {
        size_t done=0;
        while(done<n && index_<refs_.size()) {
            if(!current_) {bool hit=false;current_=load_page(root_,refs_[index_],hit);(hit?hot_bytes_:disk_bytes_)+=current_->size();}
            size_t c=std::min(n-done,current_->size()-offset_);std::memcpy(dst+done,current_->data()+offset_,c);done+=c;offset_+=c;
            if(offset_==current_->size()){current_.reset();offset_=0;++index_;}
        }
        return static_cast<long long>(done);
    }
    ~Reader(){std::fprintf(stderr,"strata paged cache: read logical=%llu hot=%llu disk=%llu\n",(unsigned long long)size_,(unsigned long long)hot_bytes_,(unsigned long long)disk_bytes_);}
};
inline bool is_manifest(const std::string& path) {
#ifndef _WIN32
    Fd fd(::open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC));if(fd.value<0)return false;
    struct stat st{};if(::fstat(fd.value,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1)return false;
    char h[8];return ::read(fd.value,h,8)==8 && std::memcmp(h,magic,8)==0;
#else
    return false;
#endif
}
} // namespace strata::core::session_pages
