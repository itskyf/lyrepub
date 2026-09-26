"""Fixed inspection cases for NLP screening, pinned to EPUB source locations.

Selected from the source scan (scripts/scan_sources.py) before any
segmentation or NER model ran, one case per materially distinct observed
phenomenon, so screening judgements cannot influence selection. Final
sample: 10 sentence-boundary-risk cases (6 in Thăng Long nổi giận, 4 in
Đêm hội Long Trì) and 6 entity-rich cases (3 per book); each case's
phenomenon is recorded in its note field.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from lyrepub.epub_text import Block

_SENTENCE_RISK: tuple[tuple[str, int, int, str, str], ...] = (
    (
        "9786045633946",
        12,
        68,
        "Thu thập tin tức xong, Đỗ Vỹ bèn cho người gửi một phong thư dán kín đ",
        "mixed straight and curly quotation marks within one block",
    ),
    (
        "9786045633946",
        17,
        24,
        "(Tể tướng nhà Tống là Vương An Thạch chủ trương đánh An Nam. Năm Ất mã",
        "nested parentheses with era and Western years plus quoted terms",
    ),
    (
        "9786045633946",
        17,
        135,
        'Tiếng "Sát Thát!\u201d thét vang trời. Dường như cả Thăng Long: Sát Thát! S',
        "mid-word ellipses and dots inside battle shouts",
    ),
    (
        "9786045633946",
        2,
        70,
        "(Văn Thù: là một trong 8 vị đại Bồ Tát, đệ tử của Phật Thích Ca: 1/ Vă",
        "slash-enumerated list inside a parenthetical note",
    ),
    (
        "9786045633946",
        5,
        9,
        "Phủ Chiêu Quốc không phải là phủ lớn nhất, nhưng là phủ đẹp nhất trong",
        "longest block of the corpus (upper-tail length)",
    ),
    (
        "9786045633946",
        11,
        82,
        "- Tâu hoàng thượng, tâu quan gia, Đại Việt ta từ thuở lập quốc vẫn một",
        "hyphen dialogue prefix on a long multi-sentence address",
    ),
    (
        "9786326186253",
        8,
        93,
        "- Kim đâu? Thành đâu? Nghiễm đâu? Hoành đâu? Hổ đâu? Giao đâu? Trực đâ",
        "rapid question burst followed by declaratives",
    ),
    (
        "9786326186253",
        4,
        103,
        "- Tiểu tướng được trọng dụng ngay. Được mươi hôm, giữa đêm mồng chín t",
        "footnote marker attached to a word, ellipsis, long dialogue",
    ),
    (
        "9786326186253",
        3,
        149,
        "- Bỏ chuyện ấy đấy, chưa phải lúc nói. Các chú cho tôi biết cái thằng ",
        "questions and ellipsis inside dialogue",
    ),
    (
        "9786326186253",
        7,
        303,
        "- Bỏ ra, bỏ ra, bỏ tôi ra! Trời ơi là trời!",
        "short exclamatory dialogue with immediate repetition",
    ),
)

_ENTITY_RICH: tuple[tuple[str, int, int, str, str], ...] = (
    (
        "9786045633946",
        2,
        26,
        "(Năm 1274 nhà Nguyên tập Kinh Hồ đẳng xứ hành trung thư tỉnh. Năm 1277",
        "dense historical place names and years in nested parentheses",
    ),
    (
        "9786045633946",
        10,
        42,
        "Quang Khải nắm tay Quốc Tuấn cùng đi vào lâu thuyền, và trong lòng ông",
        "person-dense court narrative",
    ),
    (
        "9786045633946",
        19,
        169,
        "Quốc Tuấn đã điều thêm quân từ các lộ Hải Đông, Vân Trà, Ba Điểm, chọn",
        "place-name enumeration",
    ),
    (
        "9786326186253",
        1,
        3,
        "Quê quán: Dục Tú, Đông Anh, Hà Nội",
        "compact biographical place list",
    ),
    (
        "9786326186253",
        2,
        5,
        "Tiểu thuyết Đêm hội Long Trì được đăng báo từ cuối năm 1942, xuất bản ",
        "persons, work titles, years, and a quotation",
    ),
    (
        "9786326186253",
        5,
        132,
        "Thị nữ dạ dạ. Một lúc đỉnh trầm ngào ngạt hương thơm đã đặt trên long ",
        "court narrative with titles, persons, and objects",
    ),
)


@dataclass(frozen=True, slots=True)
class InspectionCase:
    """One frozen screening case pinned to a block's EPUB source location.

    Args:
        expected_prefix: Start of the collapsed block text; detects
            extraction drift when the case is resolved.
        note: Observed phenomenon the case represents.
    """

    isbn: str
    spine_index: int
    block_index: int
    expected_prefix: str
    note: str


_Row = tuple[str, int, int, str, str]


def _make(rows: tuple[_Row, ...]) -> tuple[InspectionCase, ...]:
    return tuple(
        InspectionCase(isbn, spine_index, block_index, prefix, note)
        for isbn, spine_index, block_index, prefix, note in rows
    )


SENTENCE_RISK_CASES: tuple[InspectionCase, ...] = _make(_SENTENCE_RISK)
ENTITY_RICH_CASES: tuple[InspectionCase, ...] = _make(_ENTITY_RICH)


def resolve_case(case: InspectionCase, blocks: Sequence[Block]) -> Block:
    """Return the block at the case address, verifying the pinned prefix.

    Raises:
        ValueError: If no block matches the address or the block text no
            longer starts with the pinned prefix.
    """
    for block in blocks:
        if (
            block.spine_index == case.spine_index
            and block.block_index == case.block_index
            and block.text.startswith(case.expected_prefix)
        ):
            return block
    msg = (
        f"case {case.isbn} s{case.spine_index} #{case.block_index} "
        f"({case.note}) did not resolve; extraction drifted from pinned prefix"
    )
    raise ValueError(msg)
