"""games_advisor 的程式常數（spec §4.2）。

不開 .env 欄位：本機改這裡的值做實驗不用開 MR，要合併進 dev 時照常走 MR。
"""

# 心得片段的長度（spec §8.4）：中文算字元數（不含空白），英文算單字數
EXCERPT_MIN_CHINESE_CHARS = 40
EXCERPT_MAX_CHINESE_CHARS = 300
EXCERPT_MIN_ENGLISH_WORDS = 25
EXCERPT_MAX_ENGLISH_WORDS = 150

# 標籤詞彙表最多幾個標籤（spec §8.6）：同步時超過就整份拒絕
TAG_VOCABULARY_MAX_TAGS = 30

# 上標籤的自動檢查（spec §8.7）：信心分數到這個值以上，至少要引用 2 篇心得
TAG_HIGH_CONFIDENCE = 0.8
TAG_HIGH_CONFIDENCE_MIN_REVIEWS = 2

# 上標籤的提醒（spec §8.7）：有這個比例以上的桌遊都用到同一個標籤，就提醒「詞彙表可能有問題」
TAG_USAGE_WARNING_RATIO = 0.8

# 查桌遊（spec §11）：信心分數低於門檻的標籤當作這款沒有這個標籤
TAG_CONFIDENCE_THRESHOLD = 0.5
# 查桌遊回傳的桌遊數，也是一則訊息最多推薦幾款
MAX_RECOMMENDATIONS = 3
# 查桌遊時每款桌遊回傳幾段心得片段
EXCERPTS_PER_GAME = 2
# RRF 合併名次時的 k：合併分數 = Σ 1/(k + 名次)
RRF_K = 60
