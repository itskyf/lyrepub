#include "engine/community_models/vieneu_v3_turbo/orchestration.h"

#include <iostream>
#include <iterator>
#include <string>

int main() {
    const std::string phonemes(std::istreambuf_iterator<char>(std::cin), {});
    using namespace engine::models::vieneu_v3_turbo;
    for (const auto & chunk : split_phoneme_chunks(phonemes, 200, 20)) {
        const char * gap = chunk.gap_before == Gap::Para ? "paragraph"
            : chunk.gap_before == Gap::Sentence ? "sentence" : "minor";
        std::cout << gap << '\t' << chunk.phonemes << '\n';
    }
}
