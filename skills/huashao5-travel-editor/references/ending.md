# 正常收尾：一句花字，随后渐隐

直接作用于正片原有最后一个镜头，默认末尾约3秒显示“下次见”等一句收尾花字，然后让文字、画面和现有声音自然渐隐。收尾是原正片的一部分，增加时长为0。

不追加旅行回顾、合照、片尾蒙太奇、独立结束页、新音乐、贴纸或音效，不回放前面的镜头。若正片本来以某个场景结束，沿用该场景，不为片尾再选镜。

## 制作

init-project会生成ending-plan.json，只含文字、显示时长、位置与淡出配置。默认文字“下次见”，可用用户指定短句。不编造下期行程。台标、字体和音轨沿用正片。

```sh
python3 "$SKILL_DIR/scripts/ending.py" "$PROJECT/ending-plan.json" "$PROJECT/episode-with-closing.json" --episode "$PROJECT/edit-decision.json"
python3 "$SKILL_DIR/scripts/travel_edit.py" render "$PROJECT/episode-with-closing.json" "$PROJECT/exports/episode-v2.mp4"
```

seconds默认3，允许0.75–5秒，并限制在最后一个镜头内；镜头过短时先审阅剪点，不循环或补镜头。title/title_x/title_y/title_size控制花字。finish默认video_fade_out:1、audio_fade_out:1.2，可改为0关闭，不能超出收尾区间。

保留最后一句完整对白，淡出安排在话尾后的自然空隙。收尾花字不遮脸、不与对白字幕重叠。没有配乐时只淡出现有现场声，不为了结束而另起一首歌。

脚本保持镜头、源区间、成片时长、对白与音频时码不变；只替换收尾区间已有的ending类别文字并设置最终淡出。输出写新文件，不覆盖输入。重复应用会更新同一收尾效果，不叠加标题或延长片长。

旧版回顾式片尾不再使用--append-to。若清单里已经追加了旧回顾段，脚本会拒绝继续叠加，改用未追加回顾的原正片清单。

## 检查

确认镜头数和片长不变，文字可读，最后一帧全画面淡黑（含台标和花字），话尾完整且无声音突断。展示截取的尾段预览时注明是原正片末段，不把预览再接到正片后面。未完成实际听审要如实说明。
