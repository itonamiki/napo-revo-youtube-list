import json
import os
import re
import sys
from googleapiclient.discovery import build

def parse_duration(duration):
    """
    ISO8601 形式の再生時間文字列（例: "PT1H2M3S"）を秒数に変換する関数
    """
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration)
    if not match:
        return 0
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds

def get_channel_data(api_key, channel_id):
    """
    指定したチャンネルIDのチャンネル情報と動画一覧を取得し、動画の詳細情報（再生時間、再生回数、ライブ状態、動画種類）もマージする関数
    """
    youtube = build("youtube", "v3", developerKey=api_key)

    # 1. チャンネル情報の取得
    channels_response = youtube.channels().list(
        part="snippet,contentDetails",
        id=channel_id
    ).execute()

    if not channels_response.get("items"):
        print("指定したチャンネルが見つかりません。Channel ID を確認してください。")
        return None

    channel_item = channels_response["items"][0]
    snippet = channel_item.get("snippet", {})
    content_details = channel_item.get("contentDetails", {})
    uploads_playlist_id = content_details.get("relatedPlaylists", {}).get("uploads")

    channel_info = {
        "チャンネルID": channel_id,
        "チャンネル名": snippet.get("title"),
        "説明": snippet.get("description"),
        "公開日": snippet.get("publishedAt"),
        "サムネイル": snippet.get("thumbnails", {}).get("high", {}).get("url", "")
    }

    # 2. アップロード済み動画の一覧を取得（playlistItems を利用）
    videos = []
    video_ids = []
    next_page_token = None
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in playlist_response.get("items", []):
            vid_snippet = item.get("snippet", {})
            video_id = vid_snippet.get("resourceId", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
                videos.append({
                    "タイトル": vid_snippet.get("title"),
                    "動画ID": video_id,
                    "公開日": vid_snippet.get("publishedAt"),
                    "説明": vid_snippet.get("description"),
                    "サムネイルURL": vid_snippet.get("thumbnails", {}).get("high", {}).get("url") or
                                    vid_snippet.get("thumbnails", {}).get("default", {}).get("url")
                })

        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    # 3. 各動画の詳細情報を videos.list で取得（再生時間、再生回数、ライブ状態など）
    video_details = {}
    for i in range(0, len(video_ids), 50):
        id_chunk = video_ids[i:i+50]
        videos_response = youtube.videos().list(
            part="contentDetails,statistics,snippet",
            id=",".join(id_chunk)
        ).execute()

        for item in videos_response.get("items", []):
            vid = item.get("id")
            cont_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})
            vid_snippet = item.get("snippet", {})

            duration_iso = cont_details.get("duration", "")
            duration_seconds = parse_duration(duration_iso)
            live_status = vid_snippet.get("liveBroadcastContent", "none")
            
            # 動画種類の判定
            if live_status == "live":
                video_type = "ライブ中"
            elif live_status == "upcoming":
                video_type = "ライブ予定"
            elif duration_seconds < 60:
                video_type = "ショート"
            else:
                video_type = "通常動画"

            video_details[vid] = {
                "再生時間": duration_iso,         # ISO8601 表記（必要なら秒数に変換も可能）
                "再生回数": statistics.get("viewCount", "0"),
                "ライブ状態": live_status,
                "動画種類": video_type
            }

    # 4. 取得した詳細情報を、動画情報にマージ
    for video in videos:
        vid = video["動画ID"]
        details = video_details.get(vid, {})
        video.update(details)

    return {"channel_info": channel_info, "videos": videos}

def main():
    api_key = os.environ.get("YT_API_KEY")
    channel_id = os.environ.get("YT_CHANNEL_ID")

    if not api_key:
        print("Error: YouTube API Key が見つかりません。環境変数 YT_API_KEY を設定してください。")
        return
    if not channel_id:
        print("Error: Channel ID が見つかりません。環境変数 YT_CHANNEL_ID を設定してください。")
        return
    

    print("情報を取得中...")
    channel_data = get_channel_data(api_key, channel_id)
    if channel_data is None:
        print("情報の取得に失敗しました。")
        sys.exit(1)
    
    # 取得したデータを JSON 形式に変換してファイルに保存
    json_data = json.dumps(channel_data, ensure_ascii=False, indent=2)
    output_filename = "channel_data.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(json_data)
    
    print(f"データを {output_filename} に保存しました。")

if __name__ == '__main__':
    main()
