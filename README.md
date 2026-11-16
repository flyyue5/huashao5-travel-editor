# 花少5风格旅行剪辑 Skill

把旅行原片整理成带片头、片尾、故事线、花字字幕、贴纸音效和适时配乐的旅行综艺视频。非官方项目，视觉规则受《花儿与少年》第五季启发，包装由本项目重新实现。

**v0.3.0：本地剪辑辅助版。** 助手负责理解内容、选片和审核，Python/FFmpeg负责确定性渲染。不会仅凭音量自动剪完，也不会识别人脸或声纹身份。

## 包含什么

- 约50秒片头＋约10分钟正片，末尾约3秒花字渐隐；素材不足自然缩短。
- 收尾直接作用于原有末镜头：一句花字，随后文字、画面和现有声音渐隐；不新增回顾、合照或片长。
- 蓝紫渐变细框对白、侧面竖排跳动歌词、装饰标题和反应花字。
- 6款原创旅行贴纸、5款原创音效、按情节出现的BGM和对白避让。
- 固定14首官方短试听的索引、下载与校验；不冒充完整版、不自动循环。
- **台标由使用者选择：不显示、自定义文字、上传透明PNG。** 默认不显示。
- 原版片头音乐导入：使用者提供原版MP3/MV，默认截取前50秒，不变调、不变速。
- MP4、对白SRT、装饰ASS、时间线JSON、技术检查报告和本地播放页。

## 安装到支持本地执行的助手

仓库中的 `skills/huashao5-travel-editor/` 是独立skill目录，包含SKILL.md、scripts、references、assets和agents/openai.yaml。按目标客户端的技能导入方式安装这个目录；不同客户端安装入口不同，不要求上传整个仓库。

也可以先不安装，直接让能读取本地文件并执行Python的助手使用该目录中的SKILL.md。GitHub用于分发代码，不提供视频渲染算力。普通聊天界面如果无法读写文件或执行FFmpeg，不能直接运行本工具。

核心依赖：Python 3.9+、FFmpeg/ffprobe（带libass、libx264、AAC）、中文字体。macOS可用 `brew install ffmpeg`；Ubuntu可用 `sudo apt-get install ffmpeg fonts-noto-cjk`。Windows尚待实机验证。可选ASR另见skill内references/runtime.md。

## 快速运行

在仓库根目录执行，替换示例项目路径：

```sh
export SKILL_DIR="$PWD/skills/huashao5-travel-editor"
export PROJECT="$PWD/projects/my-trip"
python3 "$SKILL_DIR/scripts/travel_edit.py" doctor
python3 "$SKILL_DIR/scripts/travel_edit.py" init-project "$PROJECT"
```

把原片放入项目raw目录。导入你提供的原版片头音轨，按需获取试听：

```sh
python3 "$SKILL_DIR/scripts/music_assets.py" import-opening /path/to/original.mp3 "$PROJECT"
python3 "$SKILL_DIR/scripts/music_assets.py" fetch "$PROJECT" --ids all
python3 "$SKILL_DIR/scripts/travel_edit.py" ingest "$PROJECT/raw" "$PROJECT/review/inventory.json"
```

让助手按SKILL.md完成审阅、转写校对和剪辑清单，再执行：

```sh
python3 "$SKILL_DIR/scripts/travel_edit.py" validate "$PROJECT/edit-decision.json"
python3 "$SKILL_DIR/scripts/travel_edit.py" render "$PROJECT/edit-decision.json" "$PROJECT/exports/episode-v1.mp4"
python3 "$SKILL_DIR/scripts/travel_edit.py" qa "$PROJECT/exports/episode-v1.mp4" "$PROJECT/exports/episode-v1.qa.json"
python3 "$SKILL_DIR/scripts/preview.py" "$PROJECT/exports/episode-v1.mp4"
```

初始清单仅是6秒色卡测试，务必替换成真实镜头和核实对白。播放页和MP4放在同一目录；可直接打开HTML，或用 `python3 -m http.server 8000 --bind 127.0.0.1 --directory "$PROJECT/exports"` 在本机查看，不会自动公开发布。

## 收尾效果

在ending-plan.json设置一句收尾花字和渐隐时间，直接应用到正片清单：

```sh
python3 "$SKILL_DIR/scripts/ending.py" "$PROJECT/ending-plan.json" "$PROJECT/episode-with-closing.json" --episode "$PROJECT/edit-decision.json"
python3 "$SKILL_DIR/scripts/travel_edit.py" render "$PROJECT/episode-with-closing.json" "$PROJECT/exports/episode-v2.mp4"
```

默认在原有最后一个镜头的末尾3秒显示“下次见”，最后约1秒画面与文字渐隐，现有声音自然淡出。不追加镜头、回顾、合照或新音乐，正片总时长不变。原来的台标选择继续沿用。旧版回顾式片尾不再作为默认功能，使用未追加回顾的正片清单制作。

## 使用示例

> 用花少5风格剪这些旅行原片。片头50秒，正片根据素材决定长度，没必要凑10分钟。台标不要。原版音乐在original.mp3，正片适时选用配乐库试听。人物姓名不确定就不显示，字幕必须依据真实对白。

> 继续上一集的风格，这集台标用我上传的logo.png。先检查素材和对白，再安排配乐、花字及少量贴纸。

## 固定配乐库

| 歌曲 | 艺人 |
|---|---|
| Record Player | Daisy the Great & AJR |
| Gas Station Diner | AGA |
| All of Me | John Legend |
| 献给永远的 | 大粉乐队 |
| Blood Money | Vancouver Sleep Clinic |
| Down in Flames | Ella Vos |
| Seine River | IamDayLight |
| Voli Me Kao Kiša | Luka Nižetić |
| The Monkey Time | Major Lance |
| Dome of Light | X-Ray Dog |
| Badelt: Générique | Dirk Brossé / Galaxy Film Orchestra |
| Darling (Score ver.) | muii / Lee Nyeom |
| Stay Alive | José González |
| Head In The Clouds | Hayd |

均为约30秒官方试听。链接或地区可用性可能变化，脚本会验证文件并尝试刷新同一曲目ID，不能获取时明确报错。音源不随源码分发，下载缓存和原版片头仅存于使用者项目。

## 测试与边界

```sh
python3 tests/smoke_test.py
python3 tests/ending_test.py
python3 tests/release_audit.py
```

测试使用合成视频/声音，不需要个人旅行素材、音乐账号或模型下载。检查解码、字幕、三种台标、贴纸、音轨、文件保护和无效输入。CI配置在 `.github/workflows/test.yml`，远端是否通过以实际运行结果为准。

选片、语义、转写正确性和声音平衡仍需审阅。程序不保证全自动成片；技术检查不能替代实际听审。原始HDR会被拒绝，需先转成经过检查的SDR代理。可选ASR的模型下载和推理不属于默认测试。

## 发布到GitHub

此目录已按公开源码整理。发布前运行release_audit，查看 `git status`，只提交源码、原创素材和文档。不要使用 `git add -f` 加入被忽略的原片、原版歌曲、试听缓存、模型、凭据或导出成片。创建自己的空仓库后推送；建议首个版本标签为v0.3.0。

README留在仓库根目录，技能目录可单独安装。无需修改任何私人绝对路径。发布公开示例时另选适合公开的素材。

代码采用MIT；音源和字体不因代码许可而获得再分发授权，详见THIRD_PARTY.md。项目不隶属于节目或平台。
