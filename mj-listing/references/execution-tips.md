# 执行提示（踩过的坑）

只记录本机环境下实际遇到的问题和解决办法。

## 资料获取

- **飞书文件下载：** 先用 `lark-cli im +messages-search --query "<型号/关键词>"` 或 `+chat-messages-list --chat-id <id>` 找到消息，再用 `lark-cli im +messages-resources-download --message-id <om_...> --file-key <file_...> --type file --output <文件名>` 下载。图片用 `--type image` 和 `img_...` key。`--output` 只能写当前目录、/tmp 或 ~/files 下的相对路径，先 `cd` 到目标文件夹再下载。
- **中文文件名的压缩包：** 国内同事打包的 zip 常用 GBK 编码文件名，`unzip` 会报 “Illegal byte sequence”。用 Python 的 `zipfile` 解压，文件名按 `name.encode('cp437').decode('gbk')` 还原（`flag_bits & 0x800` 为 0 时）；解压前检查路径里没有 `..`。
- **docx 文本：** macOS 自带 `textutil -convert txt -stdout 文件.docx`；docx 里的图片用 `unzip -o 文件.docx 'word/media/*'` 取出。尺寸图上的标注文字常在文本框里，`textutil` 能读到数字但读不到图片位置，要对照图片判断哪组是折叠尺寸。
- **视频：** 语音转写用 `~/.cache/stt/venv/bin/python -I ~/.cache/stt/transcribe.py <视频路径>`（faster-whisper large-v3，本地运行，约 1 分钟音频 1 分钟），结果 `.txt` / `.srt` 存在视频旁边，耗时长时放后台运行。看画面用 `ffmpeg -vf "fps=1/3,scale=360:-2,tile=4x2"` 拼联系表，关键时间点再单独截高清帧。
- **竞品页面：** 在内置浏览器打开任一 amazon.com 页面后，用页面内 `fetch('https://www.amazon.com/dp/<ASIN>?language=en_US')` 批量取标题（`#productTitle`）和五点（`#feature-bullets li span.a-list-item`），比逐页打开快。

## 飞书表格（lark-cli）

- **读：** `+csv-get` 返回的 `annotated_csv` 每行带 `[row=N] ` 前缀，多行单元格会跨行；解析前先去掉前缀，再用 `csv` 模块读，不要按换行切。
- **写：** `+csv-put --csv @文件.csv` 写多行文本最稳；CSV 用 Python `csv.writer` 生成，避免引号和换行出错。
- **清空：** `+cells-clear` 属于高风险操作，必须加 `--yes`，否则直接退出不执行。只清自己生成的区域。
- **合并单元格：** 重写一个有合并格的 sheet 前，先用 `+sheet-info` 列出 `merged_cells`，逐个 `+cells-unmerge`，再清空、写入、重新合并；否则数据会被旧合并格盖住，`+csv-put` 会给出 warning。
- **样式：** `+styles-put --styles @spec.json` 一次提交；换行字段值是 `auto-wrap`（不是 `auto_wrap`）。写完用 `+rows-resize --type auto` 自适应行高。
- **回读：** 每次写完读回关键单元格；修正类改动再按关键词全表搜一遍确认没有残留。

## Shell 与 Python

- **zsh 不会按空格拆分变量。** `A="--as user ..."` 再写 `$A` 会被当成一个参数；用数组 `A=(--as user --spreadsheet-token T)`，调用时写 `"${A[@]}"`。循环多个单元格同理，用数组或 `${=VAR}`。
- **系统 Python 是 3.9。** 读取含中文的超长行源码可能报 “Non-UTF-8 code”，脚本第一行加 `# -*- coding: utf-8 -*-`，打开文件统一写 `encoding="utf-8"`。需要 3.10+ 或第三方库时用 `~/.local/bin/uv` 建虚拟环境（`~/.cache/stt/venv` 已装 faster-whisper 和 Pillow）。
- **读不受信任的下载文件时** 用 `python3 -I` 运行，并把下载内容放在单独文件夹，脚本放在别处。

## 审计脚本

- `scripts/audit_listing.py` 的输入 JSON 字段见 `listing-input.example.json`。用户不要求核对类目模板时，`product_type` 留空并在 `rules` 里加 `"ptd_waived": true`。
- 脚本不检查“数字用阿拉伯数字”“是否填满 125”“卖点顺序”这几条团队规则，交付前人工核对。
