"""頁面文字的差異：刪掉的段落與改過的行（add-rules-video-mobile MR 4，design.md D11）。

純函式，不連資料庫。相似度門檻 0.6：剛好 0.6 算「改過」，低於算「刪掉」。
"""

from app.domains.rules_qa.video_pages import SIMILARITY_THRESHOLD, page_diff

PAGE_7 = """整理階段：

把所有有蓋子的木箱排成一列，不要讓客人看見箱子裡裝了什麼。
接著打開所有木箱，並依照下面3種情況處理。
"""

PAGE_8 = """# 收工與結算

當紅色燈號和藍色燈號同時亮起時活動立刻停止。

當每一位參加者都把籌碼收進收納盒，並做完手上的工作時，活動結束。

做完上面3個步驟，任一組達成目標(附圖甲、乙)就收工，若還沒有一組達成就重複第1~3步驟，直到有一組達成或時間用完。
"""


def test_threshold_is_0_6() -> None:
    assert SIMILARITY_THRESHOLD == 0.6


def test_same_text_has_no_difference() -> None:
    diff = page_diff(PAGE_7, PAGE_7)
    assert diff.removed == [] and diff.changed == []


def test_whitespace_and_blank_lines_are_ignored() -> None:
    edited = "\n\n  整理階段：  \n" + PAGE_7.split("\n", 2)[2] + "\n\n\n"
    diff = page_diff(PAGE_7, edited)
    assert diff.removed == [] and diff.changed == []


def test_typo_fix_is_changed_with_both_texts() -> None:
    edited = PAGE_7.replace("把所有有蓋子的木箱", "把所有蓋好的木箱")
    diff = page_diff(PAGE_7, edited)
    assert diff.removed == []
    assert len(diff.changed) == 1
    change = diff.changed[0]
    assert change.original.startswith("把所有有蓋子的木箱")
    assert change.edited.startswith("把所有蓋好的木箱")
    assert 0.9 < change.similarity < 1


def test_removed_paragraphs_keep_original_text() -> None:
    # 第 8 頁只留最後一段（店員刪掉不屬於本章的段落）
    last = PAGE_8.strip().split("\n\n")[-1]
    diff = page_diff(PAGE_8, last)
    assert diff.changed == []
    removed = [line for block in diff.removed for line in block.lines]
    assert removed == [
        "# 收工與結算",
        "當紅色燈號和藍色燈號同時亮起時活動立刻停止。",
        "當每一位參加者都把籌碼收進收納盒，並做完手上的工作時，活動結束。",
    ]


def test_consecutive_removed_lines_form_one_block() -> None:
    original = "甲\n乙\n丙\n丁\n戊"
    diff = page_diff(original, "甲\n戊")
    assert [block.lines for block in diff.removed] == [["乙", "丙", "丁"]]


def test_separate_removals_are_separate_blocks() -> None:
    original = "甲\n乙\n丙\n丁\n戊"
    diff = page_diff(original, "甲\n丙\n戊")
    assert [block.lines for block in diff.removed] == [["乙"], ["丁"]]


def test_exactly_threshold_counts_as_changed() -> None:
    # "abcde" 與 "abcxy"：相同 3 字、共 10 字 → 0.6
    diff = page_diff("開頭\nabcde\n結尾", "開頭\nabcxy\n結尾")
    assert diff.removed == []
    assert [(c.original, c.edited) for c in diff.changed] == [("abcde", "abcxy")]
    assert diff.changed[0].similarity == 0.6


def test_below_threshold_counts_as_removed() -> None:
    # "abcde" 與 "abxyz"：相同 2 字 → 0.4
    diff = page_diff("開頭\nabcde\n結尾", "開頭\nabxyz\n結尾")
    assert diff.changed == []
    assert [block.lines for block in diff.removed] == [["abcde"]]


def test_everything_removed() -> None:
    diff = page_diff(PAGE_7, "")
    assert diff.changed == []
    assert sum(len(block.lines) for block in diff.removed) == 3
