// Opt-in cold-to-hot promotion: keep already-read host KV rather than copying it back from the GPU.
#pragma once
#include "strata/core/conversation_cache.hpp"
#include <functional>
#include <limits>
#include <new>

namespace strata::core {
inline bool session_restore_hot(SavedConversation& image, ConversationCache& cache,
                                std::vector<int32_t>& live, std::vector<ConversationImageKey>& images,
                                std::vector<ConversationCheckpoint>& checkpoints,
                                const std::function<bool(uint64_t)>& admit) {
    if (!cache.enabled() || !cache.wants(static_cast<int64_t>(image.live.ids.size()))) return false;
    uint64_t need = uint64_t(1) << 20; // small containers and cache bookkeeping
    const auto add = [&](uint64_t n) {
        need = n > UINT64_MAX - need ? UINT64_MAX : need + n;
    };
    add(image.live.ids.size() * sizeof(int32_t));
    add(image.live.imgs.size() * sizeof(ConversationImageKey));
    for (const auto& c : image.checkpoints) add(c.bytes());
    if (admit && !admit(need)) return false;
    // Make the live metadata independently mutable; the large K/V buffers are MOVED, not copied.
    std::vector<int32_t> ids;
    std::vector<ConversationImageKey> imgs;
    std::vector<ConversationCheckpoint> checks;
    try {
        ids = image.live.ids;
        imgs = image.live.imgs;
        checks = image.checkpoints;
    } catch (const std::bad_alloc&) { return false; }
    // A budget refusal does not consume image. Allocation exceptions from the cache itself
    // propagate: its containers must not be treated as intact after an allocation failure.
    if (!cache.put(std::move(image))) return false;
    live = std::move(ids);
    images = std::move(imgs);
    checkpoints = std::move(checks);
    return true;
}
} // namespace strata::core
