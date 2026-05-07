from app.shared_kernel.common_response_models import AttachmentPayload


def test_attachment_payload_accepts_canonical_data_base64() -> None:
    payload = AttachmentPayload(
        file_name="erro.png",
        mime_type="image/png",
        data_base64="ZmFrZQ==",
    )

    assert payload.to_context_dict() == {
        "file_name": "erro.png",
        "mime_type": "image/png",
        "data_base64": "ZmFrZQ==",
    }


def test_attachment_payload_accepts_legacy_base64_data_alias() -> None:
    payload = AttachmentPayload(
        file_name="erro.png",
        mime_type="image/png",
        base64_data="ZmFrZQ==",
    )

    assert payload.data_base64 == "ZmFrZQ=="
