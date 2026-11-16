# 剪辑清单 schema_version 1

以assets/edit-decision.example.json为基础。路径相对EDL所在目录，支持绝对路径。内置素材用 `asset:sfx/soft-pop.wav` 等asset前缀，不改安装目录。

| 字段 | 含义 |
|---|---|
| width / height / fps | 偶数尺寸，最长边≤4096，fps≤60 |
| caption_theme | huashao_v2 |
| font / fonts_dir | 可选字体家族/本地字体目录 |
| clips | 成片顺序排列镜头 |
| events | 成片时间上的对白、歌词、标题、地点、花字 |
| speakers | 用户明确提供的姓名映射，未知时{} |
| music / sfx | 音频片段，不自动循环 |
| stickers | 图集索引、成片时间和位置 |
| branding | none / text / image |
| finish | 可选全片末尾画面/声音淡出秒数 |
| ending | ending.py写入的片尾起点与时长元数据 |

## 镜头与时码

```json
{"source":"raw/clip.mov","in":1.2,"out":5.6,"fit":"contain","grade":"none","gain_db":0,"mute":false}
```

fit为contain或cover，cover可用0–1的focal_x/focal_y保护主体。grade为none、natural_warm、cool_travel、night_neutral。片头需静音镜头明确mute:true。色卡用kind:card、in:0、out:时长、color:#RRGGBB，只用于标题或测试，不替代旅行镜头。

成片时间从0累加按帧量化后的镜头时长。不要直接套用原片ASR时码。

## 字幕

```json
{"kind":"dialogue","start":52.1,"end":54.5,"text":"已核对的原话","text_verified":true}
```

姓名还需speaker_id:p1、speaker_verified:true；speakers.p1包含display_name、color:#86B8D4、identity_source:user_provided。ASR speaker_0不是人物姓名。

歌词示例：
```json
{"kind":"lyric","start":3,"end":6,"text":"已核对歌词","text_verified":true,"animation":"bounce","pulse_times":[3.5,4,4.5,5]}
```

pulse_times是绝对成片秒数。动画不能冒称词级语音识别。其他kind为title/location/flower/ending；x/y为归一化中心位置，size为字号，theme为blue/pink/cream。花字≤20字符，避免溢出。

## 音频

```json
{"source":"private/music/previews/1518762768.m4a","source_in":2,"timeline_in":103.6,"duration":12.7,"gain_db":-24,"fade_in":1.3,"fade_out":2,"rights":"official_preview"}
```

时间只是字段示例，要按本集重算。原版片头用private/music/opening-original.m4a，rights:user_provided_reference；内置原创音效rights:licensed。其他标签user_owned/licensed/public_domain记录来源，不自动证明许可。源范围与成片范围均校验，试听单cue≤30.1秒。

music按现场音侧链避让；风噪或轻声时可能不准，仍需听审手调gain_db。不要静音全部原声掩盖混音问题。

## 贴纸

```json
{"cell":2,"start":63.2,"end":65.1,"width":0.12,"x":0.73,"y":0.62}
```

cell=0..5；width为画面宽度占比，x/y为左上位置。正方形贴纸须考虑竖屏比例、弹动位移与脸部。图集用透明度阈值清残留；用户logo保留原Alpha。

## 台标

```json
{"branding":{"mode":"none"}}
```
```json
{"branding":{"mode":"text","text":"我的旅行TV","style":"blue","x":0.03,"y":0.03}}
```
```json
{"branding":{"mode":"image","source":"private/branding/logo.png","width":0.14,"x":0.03,"y":0.03}}
```

文字style为blue或gold。图片推荐裁切边缘的透明PNG。新复杂logo用宿主图像生成工具制作再导入，本skill不内置生成服务。

## 全片末尾淡出

`"finish":{"video_fade_out":1.2,"audio_fade_out":2}`。默认没有finish就保持原输出；设置后只作用于整条时间线末尾，图像淡出包括台标、字幕和贴纸。数值应为0–5秒，且不超过全片时长。在现有末镜头上添加收尾花字见ending.md；不新增镜头或时长。
