# -*- coding: utf-8 -*-
"""
mj_dj_edit.py — 歌单 → 无缝 DJ 串烧（静音裁切 / BPM 过渡 / 低频置换 / CUE / U 盘 ZIP），可选发布到 GitHub Release。

推荐运行方式（uv 会自动准备 Python 3.11 和依赖，imageio-ffmpeg 自带 ffmpeg）：

    uv run --python 3.11 \
      --with requests --with mutagen --with yt-dlp --with imageio-ffmpeg \
      --with pedalboard --with numpy \
      ~/.claude/skills/mj-dj-edit/scripts/mj_dj_edit.py "<歌单链接 或 歌名清单.txt>" --name 自驾歌单

音频的检索/下载/混音复用用户自己的 FlowScope 仓库（moujian421/FlowScope），
首次运行会 clone 到 ~/.cache/mj-dj-edit/FlowScope，之后 git pull 更新。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import zipfile

DEFAULT_REPO = "moujian421/FlowScope"
DEFAULT_FLOWSCOPE_DIR = os.path.expanduser("~/.cache/mj-dj-edit/FlowScope")
MIN_VALID_AUDIO_BYTES = 300_000


def log(msg=""):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# FlowScope 准备
# ---------------------------------------------------------------------------
def ensure_flowscope(path, repo, update=True):
    if os.path.isdir(os.path.join(path, ".git")):
        if update:
            r = subprocess.run(["git", "-C", path, "pull", "--ff-only", "-q"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                log(f"⚠️ FlowScope 更新失败，继续用本地版本: {r.stderr.strip()[:200]}")
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    log(f"📥 首次运行，clone {repo} → {path}")
    # 优先尝试 SSH 协议，失败再回退 HTTPS
    r = subprocess.run(["git", "clone", "-q", f"git@github.com:{repo}.git", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        r = subprocess.run(["git", "clone", "-q", f"https://github.com/{repo}.git", path],
                           capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"❌ clone FlowScope 失败（检查网络和 SSH/GitHub 权限）: {r.stderr.strip()[:300]}")
    return path


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def clean_title(text):
    text = re.sub(r"[\(（\[【].*?[\)）\]】]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def first_artist(artist):
    return re.split(r"[/,，、&]", artist or "")[0].strip()


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ascii_slug(text, fallback):
    """GitHub Release 会把非 ASCII 文件名替换成 '_'（上次就变成了 '_.cue'），上传名一律用 ASCII。"""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return s or fallback


def fmt_dur(sec):
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# 下载：每首歌一个独立子目录，杜绝「按歌名模糊命中缓存」导致的串歌/重复
# ---------------------------------------------------------------------------
def download_all(tracks, songs_dir, downloader_core):
    files, skipped, seen_hash = [], [], {}
    total = len(tracks)
    for t in tracks:
        idx, name, artist = t["index"], t["name"], t["artist"]
        track_dir = os.path.join(songs_dir, f"{idx:02d}")
        os.makedirs(track_dir, exist_ok=True)
        log(f"\n[{idx:02d}/{total}] 《{name}》 - {artist}")

        cached = [os.path.join(track_dir, f) for f in os.listdir(track_dir) if f.endswith(".mp3")]
        cached = [p for p in cached if os.path.getsize(p) >= MIN_VALID_AUDIO_BYTES]
        dest, msg = (cached[0], "缓存") if cached else (None, "")

        attempts = [(name, artist)]
        alt = (clean_title(name), first_artist(artist))
        if alt != (name, artist):
            attempts.append(alt)
        for q_name, q_artist in ([] if dest else attempts):
            try:
                ok, d, msg = downloader_core.download_single_song(
                    q_name, q_artist, save_dir=track_dir, filter_live=True)
            except Exception as exc:  # 单首失败不影响整批
                ok, d, msg = False, None, f"{type(exc).__name__}: {exc}"
            if ok and d and os.path.exists(d) and os.path.getsize(d) >= MIN_VALID_AUDIO_BYTES:
                dest = d
                break
            log(f"   ↻ 未命中（{(msg or '无有效音源')[:80]}）")

        if not dest:
            skipped.append({"index": idx, "name": name, "artist": artist,
                            "reason": msg or "各音源均无完整音轨（可能 VIP/仅试听）"})
            log("   ⚠️ 跳过")
            continue

        digest = sha1(dest)
        if digest in seen_hash:
            skipped.append({"index": idx, "name": name, "artist": artist,
                            "reason": f"与第 {seen_hash[digest]} 首下载到的是同一个文件，已去重"})
            log(f"   ⚠️ 与第 {seen_hash[digest]} 首音频完全相同，去重跳过")
            continue
        seen_hash[digest] = idx
        files.append((idx, dest, name, artist))
        log(f"   ✅ {os.path.basename(dest)} ({os.path.getsize(dest) // 1024} KB)")
    return files, skipped


# ---------------------------------------------------------------------------
# GitHub 发布（可选）
# ---------------------------------------------------------------------------
def github_token():
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    if shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True)
    m = re.search(r"^password=(.+)$", r.stdout, re.M)
    return m.group(1).strip() if m else None


def gh_api(method, url, token, payload=None, timeout=60):
    cmd = ["curl", "-sS", "-m", str(timeout), "-X", method,
           "-H", f"Authorization: token {token}",
           "-H", "Accept: application/vnd.github+json", url]
    if payload is not None:
        cmd[1:1] = ["-H", "Content-Type: application/json", "--data-binary", "@-"]
    r = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"message": (r.stdout or r.stderr)[:300]}


def gh_upload(upload_base, token, path, name, ctype, retries=3):
    url = f"{upload_base}?name={urllib.parse.quote(name)}"
    for attempt in range(1, retries + 1):
        r = subprocess.run(
            ["curl", "-sS", "--connect-timeout", "30", "-m", "1800", "-X", "POST",
             "-H", f"Authorization: token {token}", "-H", f"Content-Type: {ctype}",
             "--data-binary", f"@{path}", url],
            capture_output=True, text=True)
        try:
            res = json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            res = {}
        if res.get("browser_download_url"):
            return res["browser_download_url"]
        log(f"   ↻ 上传 {name} 第 {attempt} 次失败: {(res.get('message') or r.stderr or r.stdout)[:150]}")
        time.sleep(5 * attempt)
    return None


def publish(repo, album, timeline, assets, total_dur, size_mb):
    token = github_token()
    if not token:
        log("❌ 没拿到 GitHub 凭据（GITHUB_TOKEN / gh auth / git credential 都没有），跳过发布")
        return None
    rows = "\n".join(
        f"| {t['index']:02d} | `{t['start_time']}` | {t['title']} | {t['singer']} | {t.get('bpm') or '—'} |"
        for t in timeline)
    body = (f"## 🎵 《{album}》无缝串烧\n\n"
            f"总时长 {fmt_dur(total_dur)} · {size_mb} MB · {len(timeline)} 首\n\n"
            "| # | 起始 | 曲名 | 歌手 | BPM |\n|:-:|:-:|:--|:--|:-:|\n" + rows +
            "\n\n由 mj-dj-edit / FlowScope 生成。")
    rel = gh_api("POST", f"https://api.github.com/repos/{repo}/releases", token, {
        "tag_name": f"mixtape-{time.strftime('%Y%m%d-%H%M%S')}",
        "name": f"🎵 《{album}》无缝串烧", "body": body, "draft": False, "prerelease": False})
    if not rel.get("upload_url"):
        log(f"❌ 创建 Release 失败: {rel.get('message')}")
        return None
    upload_base = rel["upload_url"].split("{")[0]
    urls = {}
    for path, name, ctype in assets:  # ZIP 放第一位：它已包含 MP3+CUE，后面的大文件失败也不影响交付
        log(f"📤 上传 {name} ({os.path.getsize(path) / 1048576:.1f} MB)")
        urls[name] = gh_upload(upload_base, token, path, name, ctype)
    return {"release_url": rel.get("html_url"), "assets": urls}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="歌单 → 无缝 DJ 串烧")
    ap.add_argument("input", help="QQ/网易云歌单链接，或每行一首歌名的 .txt 文件，或直接用换行分隔的歌名文本")
    ap.add_argument("--name", help="串烧名称（默认用歌单标题）")
    ap.add_argument("--out", help="输出目录（默认 ~/Downloads/<名称>_串烧）")
    ap.add_argument("--crossfade", type=float, default=2.5, help="淡化时长秒：1.5/2.5/3.5/5（尾渐弱，首渐强取 0.8 倍）")
    ap.add_argument("--bitrate", default="320k", choices=["128k", "192k", "256k", "320k"])
    ap.add_argument("--bars", type=int, default=2, help="过渡长度小节数：1/2/4（每小节 4 拍）")
    ap.add_argument("--max-silence", type=float, default=4.0, help="整轨允许的最长静音秒数（校验用）")
    ap.add_argument("--no-bpm", action="store_true", help="关闭 BPM 对拍，改为普通交叉淡化")
    ap.add_argument("--no-bass-swap", action="store_true", help="关闭低频置换")
    ap.add_argument("--publish", action="store_true", help="完成后发布到 GitHub Release")
    ap.add_argument("--repo", default=DEFAULT_REPO, help="发布用仓库 owner/name")
    ap.add_argument("--upload-mp3", action="store_true", help="发布时额外单独上传 MP3（ZIP 里已有，默认不传）")
    ap.add_argument("--flowscope-dir", default=DEFAULT_FLOWSCOPE_DIR)
    ap.add_argument("--no-update", action="store_true", help="不 git pull FlowScope")
    ap.add_argument("--keep-work", action="store_true", help="保留单曲与中间文件")
    ap.add_argument("--clean-local", action="store_true", help="发布全部成功后删除本地输出目录")
    args = ap.parse_args()

    fs_dir = ensure_flowscope(args.flowscope_dir, args.repo, update=not args.no_update)
    sys.path.insert(0, fs_dir)
    try:
        import playlist_parser
        import downloader_core
        from merger.core.processor import process_and_merge_tracks, find_ffmpeg
        from merger.core.cue_generator import generate_cue_and_timeline
    except ImportError as exc:
        raise SystemExit(f"❌ 依赖缺失: {exc}\n请用 SKILL.md 里的 uv run 命令启动（会自动装 requests/mutagen/yt-dlp/imageio-ffmpeg/pedalboard）")

    try:
        import pedalboard  # noqa: F401  # FlowScope 的 BPM 估算依赖它
        bpm_ok = True
    except ImportError:
        bpm_ok = False
        if not args.no_bpm:
            log("⚠️ 没装 pedalboard：BPM 无法检测，所有曲目会按 120 BPM 计算过渡长度（结果里会标注）")

    text = args.input
    if os.path.isfile(text):
        with open(text, encoding="utf-8") as f:
            text = f.read()

    # 1. 解析
    log("【1/5】解析歌单 / 歌名")
    parsed = playlist_parser.parse_playlist_or_batch(text)
    if parsed.get("status") == "error" or not parsed.get("songs"):
        raise SystemExit(f"❌ 解析失败: {parsed.get('message', '没有解析到曲目')}")
    tracks = [{"index": s.get("index", i), "name": s.get("name", ""),
               "artist": s.get("artist", "") or s.get("singer", "")}
              for i, s in enumerate(parsed["songs"], 1)]
    album = (args.name or parsed.get("title") or "无缝串烧").strip()
    out_dir = os.path.expanduser(args.out or f"~/Downloads/{album}_串烧")
    work_dir = os.path.join(out_dir, "_work")
    os.makedirs(work_dir, exist_ok=True)
    log(f"   《{album}》共 {len(tracks)} 首 → {out_dir}")

    # 2. 下载
    log("\n【2/5】检索下载音轨")
    files, skipped = download_all(tracks, os.path.join(work_dir, "songs"), downloader_core)
    log(f"\n   成功 {len(files)} 首，跳过 {len(skipped)} 首")
    if len(files) < 2:
        raise SystemExit("❌ 有效音轨不足 2 首，无法串烧")

    # 3. 混音
    log("\n【3/5】静音裁切 + 过渡混音（FFmpeg: %s）" % find_ffmpeg())
    mp3_path = os.path.join(out_dir, f"{album}_无缝串烧.mp3")
    processed, total_dur, size_bytes = process_and_merge_tracks(
        downloaded_files=files, output_merged_mp3=mp3_path,
        temp_dir=os.path.join(work_dir, "temp"),
        fade_in_sec=round(args.crossfade * 0.8, 2), fade_out_sec=args.crossfade,
        max_silence_sec=args.max_silence, bitrate=args.bitrate,
        dj_mode=not args.no_bpm, bass_swap=not args.no_bass_swap,
        transition_bars=args.bars, min_tracks=2,
        log_callback=lambda m: log(f"   {m}"))
    size_mb = round(size_bytes / 1048576, 1)

    # 4. CUE + ZIP
    log("\n【4/5】生成 CUE 与 U 盘包")
    cue_path, timeline_path, timeline = generate_cue_and_timeline(processed, album, mp3_path)
    zip_path = os.path.join(out_dir, f"{album}_U盘包.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(mp3_path, os.path.basename(mp3_path))
        zf.write(cue_path, os.path.basename(cue_path))

    report = {
        "album": album, "output_dir": out_dir, "mp3": mp3_path, "cue": cue_path, "zip": zip_path,
        "duration": fmt_dur(total_dur), "size_mb": size_mb,
        "tracks_in_mix": len(processed), "tracks_requested": len(tracks),
        "bpm_detected": bpm_ok and not args.no_bpm,
        "settings": {"crossfade": args.crossfade, "bitrate": args.bitrate, "bars": args.bars,
                     "bpm_transition": not args.no_bpm, "bass_swap": not args.no_bass_swap,
                     "silence_threshold_db": -40, "max_silence": args.max_silence},
        "timeline": timeline, "skipped": skipped,
    }

    # 5. 发布
    if args.publish:
        log("\n【5/5】发布到 GitHub Release 与同步 CUE 到仓库")
        # 优先通过 Git SSH 把 CUE 文件提交并推送到 FlowScope 仓库
        try:
            mixtapes_dir = os.path.join(fs_dir, "mixtapes")
            os.makedirs(mixtapes_dir, exist_ok=True)
            shutil.copy2(cue_path, os.path.join(mixtapes_dir, os.path.basename(cue_path)))
            subprocess.run(["git", "-C", fs_dir, "add", "mixtapes/"], capture_output=True)
            r_cmt = subprocess.run(["git", "-C", fs_dir, "commit", "-m", f"feat(mixtape): add {album} CUE index"], capture_output=True, text=True)
            if r_cmt.returncode == 0:
                r_push = subprocess.run(["git", "-C", fs_dir, "push", "origin", "main"], capture_output=True, text=True)
                if r_push.returncode == 0:
                    log("   ✅ CUE 索引已通过 SSH 成功推送到 GitHub 仓库 main 分支！")
                else:
                    log(f"   ⚠️ Git push 提示: {r_push.stderr.strip()[:150]}")
        except Exception as e:
            log(f"   ⚠️ 同步 CUE 到仓库提示: {e}")

        slug = ascii_slug(album, "mixtape")
        assets = [(zip_path, f"{slug}_usb.zip", "application/zip"),
                  (cue_path, f"{slug}.cue", "application/octet-stream")]
        if args.upload_mp3:
            assets.append((mp3_path, f"{slug}_{args.bitrate}.mp3", "audio/mpeg"))
        report["github"] = publish(args.repo, album, timeline, assets, total_dur, size_mb)
    else:
        log("\n【5/5】未加 --publish，跳过发布")

    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if not args.keep_work:
        shutil.rmtree(work_dir, ignore_errors=True)
        if os.path.exists(timeline_path):
            os.remove(timeline_path)  # 时间轴已写进 report.json

    gh = report.get("github") or {}
    all_uploaded = bool(gh.get("assets")) and all(gh["assets"].values())
    if args.clean_local:
        if all_uploaded:
            shutil.rmtree(out_dir, ignore_errors=True)
            log("🧹 发布已确认成功，本地输出目录已删除")
        else:
            log("⚠️ 发布未全部成功，保留本地文件（--clean-local 未执行）")

    log("\n" + "=" * 60)
    log(f"🎉 完成：{len(processed)}/{len(tracks)} 首 · {fmt_dur(total_dur)} · {size_mb} MB")
    if gh.get("release_url"):
        log(f"GitHub: {gh['release_url']}")
    log("REPORT_JSON=" + json.dumps({k: report[k] for k in ("output_dir", "duration", "size_mb",
                                     "tracks_in_mix", "bpm_detected")} | {"skipped": skipped,
                                     "github": gh}, ensure_ascii=False))


if __name__ == "__main__":
    main()
