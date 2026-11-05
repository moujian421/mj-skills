# 飞书表格操作（lark-cli）

前提：已安装飞书官方 CLI（`@larksuite/cli`）并完成登录，`lark-cli auth status` 中 user 身份显示 ready。如果 `lark-cli` 不在 PATH 里，先执行 `export PATH="$HOME/.npm-global/bin:$PATH"`。

**文件路径限制**：`@文件` 只能读当前目录、/tmp 或 ~/files 下的文件。写入脚本开头先 `cd` 到放 CSV/样式的目录，再用相对路径 `@ad.csv`。

以下命令里，`U` 是飞书链接（wiki 链接也可以直接用），全部加 `--as user`。

## 读取
```bash
lark-cli sheets +workbook-info --url "$U" --as user                      # 列出所有子表：sheet_id、名称、行列数
lark-cli sheets +sheet-info   --url "$U" --sheet-id ID --as user          # 列宽、行高、合并单元格、冻结
lark-cli sheets +csv-get      --url "$U" --sheet-id ID --range A1:S20 --as user
lark-cli sheets +cells-get    --url "$U" --sheet-name 名称 --range A1:Z80 --include truncation --as user   # 检查文字是否被截断
```
读取整张表的 CSV：加 `--include-row-prefix=false`，结果在 `data.annotated_csv` 字段里。

## 写入
```bash
lark-cli sheets +sheet-create --url "$U" --title "类目广告词库" --index 2 --row-count 200 --col-count 30 --as user
lark-cli sheets +csv-put      --url "$U" --sheet-name 名称 --start-cell A1 --csv "@/path/ad.csv" --as user
```
- `--csv` 用 `@文件` 传入。数字会被识别成数字类型，`n.a.` 这类保持文本。
- 新增列时从下一列开始写（比如 `--start-cell X1`），超出原有范围时表格会自动扩展。

## 排版
```bash
lark-cli sheets +styles-put --url "$U" --styles "@/path/styles.json" --as user
lark-cli sheets +styles-put --print-schema --flag-name styles           # 查看可用的样式字段
```
- **每次 styles-put 最多 1000 条 cell_styles**。`build_sheets.py` 已拆成 `styles_NN.json`，逐个提交即可。
- 表头行用 `{"range":"1:1","type":"auto"}` 自动行高，列窄时表头换行不会被截断。
- styles JSON 的结构：`{"styles":[{"name":"子表名","cell_styles":[...],"cell_merges":[...],"col_sizes":[...],"row_sizes":[...],"freeze":{"rows":1,"cols":1}}]}`
- cell_styles 常用字段：`range`、`font_weight`、`font_color`、`background_color`、`horizontal_alignment`、`vertical_alignment`、`word_wrap: auto-wrap`、`number_format`（如 `#,##0`、`0.0%`、`$0.00`）、`border: {style, weight, color}`。
- 行高设成 `{"range":"2:80","type":"auto"}` 就会随内容自动调整。

## 筛选、合并、清空（重写表格时用）
```bash
lark-cli sheets +filter-create  --url "$U" --sheet-name 名称 --range A1:AB76 --as user
lark-cli sheets +filter-delete  --url "$U" --sheet-name 名称 --as user --yes
lark-cli sheets +cells-unmerge  --url "$U" --sheet-name 名称 --range A78:W78 --as user
lark-cli sheets +cells-clear    --url "$U" --sheet-name 名称 --range A1:Q80 --scope all --as user --yes
```
重写已有表格的顺序：删除筛选 → 取消合并 → 清空（`--scope all` 连格式一起清）→ 写入 → 排版 → 重新建筛选。
每张表只能有一个筛选，扩大筛选范围时要先删掉旧的再重建。

## 清空整本表格
用户要求清空时：先 `+workbook-export --output-path <目录>/backup.xlsx` 整本备份（`+csv-get` 导出的空格子不能当备份），再建好新子表，最后 `+sheet-delete --yes` 删旧子表（工作簿至少保留一个子表）。

## 注意
- 清空、删除等操作要加 `--yes`，属于不可逆操作。只对自己新建的表，或用户明确同意覆盖的区域执行。
- 写完回读：内容抽查前几行和改动过的关键行，再用 `--include truncation` 检查有没有截断。
