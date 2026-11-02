import base64
import hashlib
import hmac

from apps.core.imgproxy import imgproxy_url


def test_imgproxy_url_is_signed_for_the_s3_source(settings):
    settings.IMGPROXY_URL = "http://img.test/"
    settings.IMGPROXY_KEY = "aa" * 16
    settings.IMGPROXY_SALT = "bb" * 16

    url = imgproxy_url("listings/ABC/photo.jpg", 640, 480)

    assert url.startswith("http://img.test/")
    signature, path = url.removeprefix("http://img.test/").split("/", 1)
    path = "/" + path
    assert path.startswith("/rs:fill:640:480:0/") and path.endswith(".webp")
    encoded = path.split("/")[2].removesuffix(".webp")
    source = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    assert (
        source
        == f"s3://{settings.STORAGES['default']['OPTIONS']['bucket_name']}/listings/ABC/photo.jpg"
    )
    expected = hmac.new(
        bytes.fromhex("aa" * 16), bytes.fromhex("bb" * 16) + path.encode(), hashlib.sha256
    ).digest()
    assert signature == base64.urlsafe_b64encode(expected).rstrip(b"=").decode()
