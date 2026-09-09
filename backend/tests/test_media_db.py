import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path
import os
import uuid

from app.main import app
from app.persistence.repository import init_db, ProjectRepository, MediaRepository
from app.shared.models.project import ProjectState, WorkflowConfig


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


@pytest.mark.asyncio
async def test_media_repository_crud():
    project_id = f"test_proj_{uuid.uuid4().hex[:8]}"
    project = ProjectState(
        project_id=project_id,
        project_name="Test Project for Media DB",
        workflow_config=WorkflowConfig(),
    )
    await ProjectRepository.save(project)

    # 1. Save media
    test_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfakeimagecontent"
    media_id = f"{project_id}_shot_01"
    await MediaRepository.save_media(
        project_id=project_id,
        media_id=media_id,
        asset_type="storyboard",
        filename="01.png",
        content_type="image/png",
        data=test_image_bytes,
        metadata={"shot_id": "01", "prompt": "cyberpunk street"},
    )

    # 2. Get media by ID
    media = await MediaRepository.get_media(media_id)
    assert media is not None
    assert media["media_id"] == media_id
    assert media["project_id"] == project_id
    assert media["asset_type"] == "storyboard"
    assert media["filename"] == "01.png"
    assert media["content_type"] == "image/png"
    assert media["data"] == test_image_bytes
    assert media["metadata"]["shot_id"] == "01"

    # 3. Get by project and type (with shot_id)
    by_type = await MediaRepository.get_by_project_and_type(
        project_id=project_id,
        asset_type="storyboard",
        shot_id="01",
    )
    assert by_type is not None
    assert by_type["media_id"] == media_id
    assert by_type["data"] == test_image_bytes

    # 4. Save video thumbnail
    thumb_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfakethumbnailcontent"
    thumb_id = f"{project_id}_thumbnail_01"
    await MediaRepository.save_media(
        project_id=project_id,
        media_id=thumb_id,
        asset_type="video_thumbnail",
        filename="thumbnail_01.png",
        content_type="image/png",
        data=thumb_bytes,
        metadata={"shot_id": "01", "variant": "01"},
    )

    # Query with alias 'thumbnail'
    found_thumb = await MediaRepository.get_by_project_and_type(
        project_id=project_id,
        asset_type="thumbnail",
        shot_id="01",
    )
    assert found_thumb is not None
    assert found_thumb["media_id"] == thumb_id

    # 5. Save audio master
    audio_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00fakeaudio"
    audio_id = f"{project_id}_audio_master"
    await MediaRepository.save_media(
        project_id=project_id,
        media_id=audio_id,
        asset_type="audio_master",
        filename="master.wav",
        content_type="audio/wav",
        data=audio_bytes,
        metadata={"duration": 15.2},
    )

    found_audio = await MediaRepository.get_by_project_and_type(
        project_id=project_id,
        asset_type="audio_master",
    )
    assert found_audio is not None
    assert found_audio["media_id"] == audio_id
    assert found_audio["data"] == audio_bytes

    # 6. Save dub track
    dub_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00fakedubaudio"
    dub_id = f"{project_id}_dub_ja_Generic"
    await MediaRepository.save_media(
        project_id=project_id,
        media_id=dub_id,
        asset_type="dub_track",
        filename="dub_ja_Generic.wav",
        content_type="audio/wav",
        data=dub_bytes,
        metadata={"language": "ja-Generic"},
    )

    found_dub = await MediaRepository.get_by_project_and_type(
        project_id=project_id,
        asset_type="dub_track",
        language="ja-Generic",
    )
    assert found_dub is not None
    assert found_dub["media_id"] == dub_id

    # 7. List all media for project
    media_list = await MediaRepository.list_by_project(project_id)
    assert len(media_list) >= 4
    media_ids = [m["media_id"] for m in media_list]
    assert media_id in media_ids
    assert thumb_id in media_ids
    assert audio_id in media_ids
    assert dub_id in media_ids

    # 8. Delete individual media
    del_ok = await MediaRepository.delete_media(thumb_id)
    assert del_ok is True
    assert await MediaRepository.get_media(thumb_id) is None

    # 9. Cascade delete via ProjectRepository.delete_project
    await ProjectRepository.delete_project(project_id)
    remaining = await MediaRepository.list_by_project(project_id)
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_api_media_and_assets_routes():
    project_id = f"test_api_proj_{uuid.uuid4().hex[:8]}"
    project = ProjectState(
        project_id=project_id,
        project_name="API Test Project",
        workflow_config=WorkflowConfig(),
    )
    await ProjectRepository.save(project)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Test POST /projects/{project_id}/media
        upload_content = b"fake video bytes for creator upload mp4"
        files = {
            "file": ("creator_voice.mp4", upload_content, "video/mp4")
        }
        res = await ac.post(f"/projects/{project_id}/media", files=files)
        assert res.status_code == 200, res.text
        upload_json = res.json()
        media_id = upload_json["media_id"]
        assert upload_json["filename"] == "creator_voice.mp4"
        assert upload_json["file_size"] == len(upload_content)

        # 2. Test GET /projects/{project_id}/media/{media_id} (Metadata JSON for getMedia compatibility)
        get_meta = await ac.get(f"/projects/{project_id}/media/{media_id}")
        assert get_meta.status_code == 200
        meta_data = get_meta.json()
        assert meta_data["media_id"] == media_id
        assert meta_data["file_size"] == len(upload_content)
        assert "download_url" in meta_data

        # 3. Test GET /projects/{project_id}/media/{media_id}?download=true (Binary stream)
        get_binary = await ac.get(f"/projects/{project_id}/media/{media_id}?download=true")
        assert get_binary.status_code == 200
        assert get_binary.content == upload_content
        assert "video/mp4" in get_binary.headers["content-type"]

        # Also test GET /projects/{project_id}/media/{media_id}/download
        get_binary_endpoint = await ac.get(f"/projects/{project_id}/media/{media_id}/download")
        assert get_binary_endpoint.status_code == 200
        assert get_binary_endpoint.content == upload_content

        # 4. Save generated storyboard & audio directly to DB to simulate worker completion
        img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRgeneratedshot"
        await MediaRepository.save_media(
            project_id=project_id,
            media_id=f"{project_id}_shot_01",
            asset_type="storyboard",
            filename="01.png",
            content_type="image/png",
            data=img_bytes,
            metadata={"shot_id": "01"},
        )

        audio_bytes = b"RIFFgeneratedaudio"
        await MediaRepository.save_media(
            project_id=project_id,
            media_id=f"{project_id}_audio_master",
            asset_type="audio_master",
            filename="master.wav",
            content_type="audio/wav",
            data=audio_bytes,
            metadata={"duration": 10.0},
        )

        # 5. Test GET /projects/{project_id}/assets?type=storyboard&shot_id=01
        res_shot = await ac.get(f"/projects/{project_id}/assets?type=storyboard&shot_id=01")
        assert res_shot.status_code == 200
        assert res_shot.content == img_bytes
        assert "image/png" in res_shot.headers["content-type"]

        # 6. Test GET /projects/{project_id}/assets?type=audio_master
        res_audio = await ac.get(f"/projects/{project_id}/assets?type=audio_master")
        assert res_audio.status_code == 200
        assert res_audio.content == audio_bytes
        assert "audio/wav" in res_audio.headers["content-type"]

        # 7. Test GET /projects/{project_id}/media (listing)
        res_list = await ac.get(f"/projects/{project_id}/media")
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) >= 3

        # 8. Test GET /projects/{project_id}/media?type=storyboard&shot_id=01 (fetch by type in media router)
        res_media_type = await ac.get(f"/projects/{project_id}/media?type=storyboard&shot_id=01")
        assert res_media_type.status_code == 200
        assert res_media_type.content == img_bytes
        assert "image/png" in res_media_type.headers["content-type"]

        # 9. Test disk fallback and auto-caching into DB
        # Create a mock thumbnail on disk not in DB
        thumb_dir = Path("storage/storyboard/generated") / project_id / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        disk_thumb_file = thumb_dir / "thumbnail_02.png"
        disk_thumb_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdiskthumbnail"
        disk_thumb_file.write_bytes(disk_thumb_content)

        # Asset is NOT yet in MediaRepository
        in_db_before = await MediaRepository.get_by_project_and_type(project_id, "video_thumbnail", shot_id="02")
        assert in_db_before is None

        # Fetch via /assets route
        res_fallback = await ac.get(f"/projects/{project_id}/assets?type=video_thumbnail&shot_id=02")
        assert res_fallback.status_code == 200
        assert res_fallback.content == disk_thumb_content

        # Verify it has now been automatically cached into the database!
        in_db_after = await MediaRepository.get_by_project_and_type(project_id, "video_thumbnail", shot_id="02")
        assert in_db_after is not None
        assert in_db_after["data"] == disk_thumb_content

        # Clean up temporary disk file
        if disk_thumb_file.exists():
            disk_thumb_file.unlink()

        # 10. Test DELETE /projects/{project_id}/media/{media_id}
        res_del = await ac.delete(f"/projects/{project_id}/media/{media_id}")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "deleted"

        # Verify 404 after deletion
        res_gone = await ac.get(f"/projects/{project_id}/media/{media_id}")
        assert res_gone.status_code == 404

    # Cleanup
    await ProjectRepository.delete_project(project_id)
