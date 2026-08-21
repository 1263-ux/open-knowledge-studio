import json
import uuid
from datetime import datetime, timezone

# 读取元数据
with open('metadata.json', 'r', encoding='utf-8') as f:
    video_data = json.load(f)

# 生成唯一 ID
def generate_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"

# 创建 artifact
artifact_id = generate_id("art")
artifact = {
    "artifact_id": artifact_id,
    "source_url": video_data["webpage_url"],
    "title": video_data["title"],
    "retrieved_at": datetime.now(timezone.utc).isoformat()
}

# 创建 evidence list
evidence_list = []

# 1. metadata evidence
evidence_list.append({
    "evidence_id": generate_id("ev"),
    "artifact_id": artifact_id,
    "kind": "metadata",
    "method": "metadata_extraction",
    "locator": {"kind": "document"},
    "text": json.dumps({
        "title": video_data["title"],
        "uploader": video_data["uploader"],
        "duration": video_data["duration"],
        "view_count": video_data.get("view_count", 0),
        "like_count": video_data.get("like_count", 0),
        "comment_count": video_data.get("comment_count", 0),
        "upload_date": video_data.get("upload_date"),
        "tags": video_data.get("tags", [])
    }, ensure_ascii=False, indent=2)
})

# 2. description evidence
if video_data.get("description"):
    evidence_list.append({
        "evidence_id": generate_id("ev"),
        "artifact_id": artifact_id,
        "kind": "text_content",
        "method": "text-read",
        "locator": {"kind": "document"},
        "text": video_data["description"]
    })

# 3. chapters evidence
if video_data.get("chapters"):
    evidence_list.append({
        "evidence_id": generate_id("ev"),
        "artifact_id": artifact_id,
        "kind": "structure",
        "method": "document_structure_extraction",
        "locator": {"kind": "document"},
        "text": json.dumps({
            "chapters": video_data["chapters"]
        }, ensure_ascii=False, indent=2)
    })

# 创建 manifest
manifest = {
    "schema_version": "0.2.0",
    "manifest_id": generate_id("mf"),
    "created_at": datetime.now(timezone.utc).isoformat(),
    "source": {
        "url": video_data["webpage_url"],
        "type": "bilibili_video",
        "title": video_data["title"]
    },
    "artifacts": [artifact],
    "evidence_count": len(evidence_list)
}

# 写入文件
with open('manifest.json', 'w', encoding='utf-8') as f:
    f.write(json.dumps(manifest, ensure_ascii=False, indent=2))

with open('evidence.jsonl', 'w', encoding='utf-8') as f:
    for ev in evidence_list:
        f.write(json.dumps(ev, ensure_ascii=False) + '\n')

print(f"✓ Manifest created: {manifest['manifest_id']}")
print(f"✓ Artifacts: {len(manifest['artifacts'])}")
print(f"✓ Evidence: {len(evidence_list)}")
