---
name: huashao5-travel-editor
description: 把用户旅行原片剪成受《花儿与少年》第五季启发的旅行综艺风格，包含约50秒原创编排片头、适量正片、正片末尾约3秒花字渐隐、蓝紫细框对白花字、侧面竖排跳动歌词、原创贴纸音效、固定14首官方试听配乐和可选台标。在用户要求花少5风格剪辑、旅行综艺包装、整理旅行视频或按这套风格续剪时使用。需要本地Python与带libass的FFmpeg；不识别人脸或声纹身份，不制作翻唱。
---

# 花少5风格旅行剪辑

本文件所在目录为 `SKILL_DIR`；用户项目放在独立的 `PROJECT`。先检查已有项目再操作，保留原片，不覆盖旧成片。这是非官方原创风格实现，不声称拥有节目精确字体或官方LUT。

## 输入与默认行为

1. 找到旅行原片、本次要求、已有项目和原版片头音乐。不要寻找被用户否定的参考，不需要登录音乐平台。
2. 默认约50秒片头、约10分钟正片、最后约3秒花字渐隐（不增加总时长）。素材不足就缩短并报告实际时长；不重复镜头凑长度。片头从当次原片重新选镜，不能直接贴节目MV。
3. 台标按用户选择：`none`、`text`、`image`。未选择时，在制作过程中询问“不要台标 / 输入频道名 / 上传台标”；同时继续独立的素材检查，未答复默认none。不带入任何上一位用户的名字或台标。
4. 片头使用用户本地原版MP3/MV的前50秒，可明确指定其他区间。不翻唱、不变声、不变速、不静默替换歌曲。缺少原版文件时先整理其他素材，最终明确缺项。
5. 正片仅从 `assets/music-catalog.json` 的14首官方试听选择。适时进入、保留无BGM段，新增曲目由用户决定。

## 执行流程

### 1. 检查环境和建项目

```sh
python3 "$SKILL_DIR/scripts/travel_edit.py" doctor
python3 "$SKILL_DIR/scripts/travel_edit.py" init-project "$PROJECT"
```

已有项目直接续用。也可 `init-project ... --opening-source /path/to/original.mp3` 一并导入片头。依赖、字体和可选转写见 [runtime.md](references/runtime.md)。

### 2. 登记与审阅素材

```sh
python3 "$SKILL_DIR/scripts/travel_edit.py" ingest "$PROJECT/raw" "$PROJECT/review/inventory.json"
python3 "$SKILL_DIR/scripts/travel_edit.py" prepare "$PROJECT/review/inventory.json" "$PROJECT/review/media"
python3 "$SKILL_DIR/scripts/travel_edit.py" scan /path/to/clip.mp4 "$PROJECT/review/candidates.json"
```

检查重复、损坏、方向、HDR。抽帧只用于定位，结合连续观看和听声审阅。静音、黑场、静止只产生候选，不能直接据此删除。HDR需先制作并检查SDR代理，渲染器会拒绝未处理的HDR，不能悄悄当SDR处理。

### 3. 整理对白和故事

优先用户字幕；否则用宿主转写工具或 `scripts/transcribe.py`。ASR全是待校对草稿，听清并修正后才设 `text_verified: true`。无法核对的对白留待办，不编造、不宣称字幕完整。

只在用户明确提供“姓名—片段”对应关系时填 `speakers`，设 `identity_source: user_provided`，对应字幕设 `speaker_verified: true`。否则完全省略姓名签。禁止通过人脸、音色或声纹推断真实身份。

先按真实事件整理正片，再选择片头亮点。执行 [style.md](references/style.md) 的节奏、花字、调色和声音规则。

### 4. 准备音乐

```sh
python3 "$SKILL_DIR/scripts/music_assets.py" import-opening /path/to/original.mp3 "$PROJECT"
python3 "$SKILL_DIR/scripts/music_assets.py" fetch "$PROJECT" --ids all
```

片头记录在 `private/music/opening.json`，试听索引在 `private/music/previews/index.json`。依据实际时长安排入出点；不能把30秒试听宣称完整版、循环成长配乐或拼接寻找完整版。`--offline` 禁止联网。不可用曲目留空并说明，不偷换录音版本。

### 5. 写清单并渲染

编辑 `PROJECT/edit-decision.json`，字段见 [edl.md](references/edl.md)。镜头in/out为源时间，字幕/BGM为成片时间；剪后重新映射时间，不直接套原片转写时码。

```sh
python3 "$SKILL_DIR/scripts/travel_edit.py" validate "$PROJECT/edit-decision.json"
python3 "$SKILL_DIR/scripts/travel_edit.py" render "$PROJECT/edit-decision.json" "$PROJECT/exports/episode-v1.mp4"
python3 "$SKILL_DIR/scripts/travel_edit.py" qa "$PROJECT/exports/episode-v1.mp4" "$PROJECT/exports/episode-v1.qa.json"
python3 "$SKILL_DIR/scripts/preview.py" "$PROJECT/exports/episode-v1.mp4"
```

模板的6秒色卡仅为环境自测，不能作为用户旅行成片交付。正式片头要用用户原片按原版音乐重新编排，不声称未核对的词级卡点。

### 6. 制作片尾

按 [ending.md](references/ending.md)，直接在正片原有最后一个镜头的末尾约3秒显示一句收尾花字，再让文字、画面和现有声音自然渐隐。不追加旅行回顾、合照、片尾蒙太奇、新配乐或独立结束页，不增加成片时长。台标继承用户选择。使用ending.py的--episode模式修改清单，最后一句对白结束后再安排淡出。

### 7. 检查并交付

执行 [review.md](references/review.md)。技术通过不等于听审或故事审核通过。无法实际听声/连续观看时明确报告未完成项，不能伪造检查状态。

交付MP4、对白SRT、装饰ASS、可修改时间线JSON、技术检查JSON、同目录播放页。说明实际片长、曲目及入出点、缺失素材与待审项。只有用户要求时才发布到外部网站或GitHub。

## 边界

- 用户媒体与下载缓存只写独立项目，不写skill安装目录，不读取其他人的素材。
- 不需要ElevenLabs、付费API、账号密码或声纹档案。可选ASR首次可能下载模型；离线时明确使用已有模型。
- 保留真实反应、笑声与环境声。不用花字补写事实或杜撰心理活动。
- 不复制节目台标、水印、平台尾页、账号兔子贴纸；避开人脸和关键画面。
- 来源标签不等于再分发许可。公开源码只含音源索引和导入脚本，不携带商业歌曲音频。
