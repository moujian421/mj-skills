---
name: mj-dj-edit
description: 把歌单做成无缝 DJ 串烧（Auto Mixtape）：解析 QQ 音乐 / 网易云歌单链接或多行歌名，逐首检索下载，-40 dB 首尾静音裁切，按 BPM 对拍过渡（1/2/4 小节）+ 低频置换（Bass Swap），导出 320/192 kbps MP3、.CUE 曲目索引和车载 U 盘 ZIP，可选发布到 GitHub Release。用户说“把这个歌单串烧一下”“做个串烧/混音/mixtape/车载歌单连播”“歌单无缝连起来”“导出带 CUE 的串烧”“串烧传到 GitHub”，或给出歌单链接 + 串烧参数截图（淡化时长、导出码率、BPM 过渡、低频置换、过渡长度）时使用。
---

# 歌单无缝串烧（mj-dj-edit）

一条命令跑完：解析 → 下载 → 静音裁切 + 过渡混音 → CUE + ZIP →（可选）GitHub Release。
检索、下载、混音引擎复用用户自己的 FlowScope 仓库 `moujian421/FlowScope`，脚本首次运行会 clone 到 `~/.cache/mj-dj-edit/FlowScope`。

## 1. 参数对照（FlowScope「串烧工坊」界面 → 脚本参数）

| 界面项 | 默认 | 脚本参数 |
|---|---|---|
| 歌单链接或歌名（每行一首） | — | 位置参数：链接 / `.txt` 文件 / 换行分隔的文本 |
| 串烧名称 | 歌单标题 | `--name` |
| 淡化时长 1.5 / 2.5 / 3.5 / 5 秒 | 2.5 | `--crossfade`（尾渐弱=该值，首渐强=0.8 倍） |
| 导出码率 320 / 192 kbps | 320k | `--bitrate` |
| BPM 过渡 ☑ | 开 | 关闭用 `--no-bpm` |
| 低频置换 ☑ | 开 | 关闭用 `--no-bass-swap` |
| 过渡长度 2 小节·8 拍 / 4 小节·16 拍 / 1 小节·4 拍 | 2 | `--bars 2/4/1` |
| -40 dB 静音裁切 | 固定 | 引擎内置；`--max-silence 4` 为整轨静音校验上限 |

用户只给截图没给数字时，按截图上的选项填；截图是默认值就直接用默认。

## 2. 运行

```bash
uv run --python 3.11 \
  --with requests --with mutagen --with yt-dlp --with imageio-ffmpeg \
  --with pedalboard --with numpy \
  ~/.claude/skills/mj-dj-edit/scripts/mj_dj_edit.py \
  "<歌单链接>" --name "幼儿园入园歌曲" --crossfade 2.5 --bitrate 320k --bars 2
```

- 必须用 `uv run`（`~/.local/bin/uv` 已装）：系统 Python 3.9 没有这些库，也没有 ffmpeg；`imageio-ffmpeg` 自带 ffmpeg，`pedalboard` 负责 BPM 检测。
- 需要上传：加 `--publish`（默认仓库 `moujian421/FlowScope`，换仓库用 `--repo owner/name`）。默认只传 ZIP（已含 MP3+CUE）和 CUE；要单独 MP3 再加 `--upload-mp3`。
- 用户要求“传完删本地”：加 `--clean-local`，脚本**只在所有附件都确认上传成功后**才删输出目录。
- 21 首左右：下载 2–5 分钟，最后一步多轨混音 FFmpeg 单线程渲染 5–15 分钟（48 分钟成品约 110 MB），用后台任务跑，别反复轮询。
- 输出默认 `~/Downloads/<名称>_串烧/`：`*_无缝串烧.mp3`、`.cue`、`*_U盘包.zip`、`report.json`。

## 3. 交付给用户时必须如实说明

从 `report.json`（或终端最后一行 `REPORT_JSON=`）取数：

1. **实际进串烧的曲目数 / 歌单曲目数**，以及 `skipped` 里每首被跳过的原因（VIP、仅试听、无音源、与其他曲目重复）。不要把“歌单 21 首”说成“21 首都做了”。
2. **`bpm_detected` 为 false 时**要明说：BPM 没测出来，过渡按 120 BPM 的 8 拍（4 秒）统一处理，不是真正按每首歌的节拍对齐。
3. 时间轴表（序号 / 起始时间 / 曲名 / 歌手 / BPM）。
4. 发布结果：Release 链接和每个附件是否成功；有失败的附件就说失败了。

## 4. 已踩过的坑（脚本已处理，改脚本时别改回去）

| 问题 | 现象 | 处理 |
|---|---|---|
| 按歌名模糊匹配本地缓存 | 同名不同版本（两首《爱上幼儿园》《萤火虫对星星说》）被替换成同一个文件，串烧里重复播放 | 每首歌下载到独立子目录 `songs/NN/`；再按 SHA1 去重并记入 skipped |
| 没装 pedalboard | 日志刷 `BPM 估算失败`，全部按 120 BPM | `uv run --with pedalboard`；装不上时 report 标注 `bpm_detected:false` |
| `process_and_merge_tracks` 返回值 | 返回 `(processed_tracks, 时长, 字节数)` 三元组，当列表用会崩 | 已按三元组解包 |
| `generate_cue_and_timeline` 返回值 | 返回 `(cue路径, json路径, timeline)` | 已按三元组解包 |
| GitHub 附件中文名 | 上传后变成 `_.cue` | 上传名统一转 ASCII（`ascii_slug`） |
| 大文件上传 | urllib 一次性上传 100MB+ 报 Broken pipe / `Upload body timed out` | 用 curl 流式上传 + 重试；ZIP 先传 |
| FlowScope 云端（onrender）跑串烧 | 免费实例中途重启，任务 404 丢失 | 本地跑，不依赖云端 API |
| 凭据 | 曾把 token 硬编码进脚本 | 只从 `GITHUB_TOKEN`/`GH_TOKEN`、`gh auth token`、`git credential` 读取，不打印、不写文件 |

## 5. 失败排查

- `GitHub 权限与连接`：本机已配置并验证 GitHub SSH 密钥（`ssh -T git@github.com` 返回 `Hi moujian421!`）。克隆 FlowScope 仓库以及将 CUE 提交推送到仓库分支时优先使用 SSH（`git@github.com:moujian421/FlowScope.git`），无需依赖 HTTP Token。
- `GitHub Releases 发布（--publish）`：Release 附件上传依赖 GitHub REST API，需通过环境变量 `GITHUB_TOKEN` 提供有效 Token（若未提供或 Token 过期，脚本会自动跳过 Release 创建，并通过 SSH 仅同步 CUE 索引至 Git 仓库）。
- 大量曲目“仅试听/VIP”：音源限制，如实列出；可让用户换歌名写法（去掉括号备注、只留第一个歌手）后用多行歌名模式重跑。
- B 站兜底报 `HTTP 412`：B 站风控，稍后重试或跳过。
- 有效音轨 < 2 首：直接报错，不出成品。
