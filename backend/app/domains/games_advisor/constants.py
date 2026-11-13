"""games_advisor 的程式常數（spec §4.2）。

不開 .env 欄位：本機改這裡的值做實驗不用開 MR，要合併進 dev 時照常走 MR。
"""

# 心得片段的長度（spec §8.4）：中文算字元數（不含空白），英文算單字數
EXCERPT_MIN_CHINESE_CHARS = 40
EXCERPT_MAX_CHINESE_CHARS = 300
EXCERPT_MIN_ENGLISH_WORDS = 25
EXCERPT_MAX_ENGLISH_WORDS = 150
