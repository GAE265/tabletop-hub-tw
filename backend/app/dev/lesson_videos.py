"""開發用 seed 登記的規則教學影片：組內自製、上傳到 YouTube 的 Demo 遊戲教學影片。

遊戲用 bgg_id 尋找（games 唯一不重複的欄位，見 docs/adr/0003-shared-games-table.md），
不寫死 games.id。正式環境不跑 seed，要由管理員用 PUT /api/v1/rules-lessons/{game_id}/video 登記。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LessonVideo:
    bgg_id: int
    game_name: str  # 只用在提示訊息
    youtube_id: str
    title: str

    @property
    def video_url(self) -> str:
        return f"https://youtu.be/{self.youtube_id}"


LESSON_VIDEOS = (
    LessonVideo(400566, "血與刃的白薔薇", "XE-Sw_FtFFs", "血與刃的白薔薇 規則影片"),
    LessonVideo(144734, "阿不思學院", "5nIdNY056Gw", "阿不思學院 規則影片"),
    LessonVideo(171623, "馬可波羅", "F5abxTqoEH8", "馬可波羅 規則影片"),
)
