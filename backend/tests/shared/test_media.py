from app.shared.tools.media.ffprobe import probe_media


def test_ffprobe_function_exists():
    assert callable(probe_media)