def test_server_start(client):
    response = client.get("/docs")
    assert response.status_code in [200, 307]


def test_password_reset_endpoint_exists(client):
    resp = client.post("/api/password/reset-request", json={"email": "test@x.com"})
    assert resp.status_code != 404


def test_register_login_smoke(client):
    # 尝试登录（可能已有该用户）
    login = client.post("/api/login", json={
        "username": "smoke_test",
        "password": "123456"
    })
    if login.status_code == 200:
        return  # 用户已存在，跳过注册

    # 注册
    reg = client.post("/api/register", json={
        "username": "smoke_test",
        "password": "123456",
        "role": "master",
        "email": "smoke@test.com"
    })
    assert reg.status_code < 500

    # 登录
    login2 = client.post("/api/login", json={
        "username": "smoke_test",
        "password": "123456"
    })
    assert login2.status_code == 200
    assert "access_token" in login2.json()