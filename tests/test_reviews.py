from trustora.reviews import amount_bucket, build_review_post, mask_room_code, user_public_hash


def test_mask_room_code():
    assert mask_room_code("TR-8F2K19").startswith("TR-")


def test_amount_bucket():
    assert amount_bucket(30) == "<50"
    assert amount_bucket(100) == "50-100"
    assert amount_bucket(120) == "100-250"


def test_review_post_format():
    post = build_review_post("TR-8F2K19", "TRC20", 120, "U#A3F9", 5, "Fast")
    assert "TR-****" in post
    assert "Chain: TRC20" in post
