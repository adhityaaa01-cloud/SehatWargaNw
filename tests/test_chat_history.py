from unittest.mock import patch

from tests import create_test_app
from app.extensions import db
from app.models.user import User
from app.models.chat_turn import ChatTurn


def test_history_survives_login_and_is_private_to_each_account():
    app = create_test_app()
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        accounts = [User(name=role, email=f"{role}@sehatwarga.test", role=role)
                    for role in ("citizen", "admin")]
        for account in accounts:
            account.set_password("Testing123!")
        db.session.add_all(accounts)
        db.session.commit()

    def login(role):
        client = app.test_client()
        assert client.post("/login", data={"email": f"{role}@sehatwarga.test",
                                           "password": "Testing123!"}).status_code == 302
        return client

    guest = app.test_client()
    with patch("app.routes.assistant.process_assistant_chat",
               return_value=({"success": True, "message": "Jawaban uji"}, 200)):
        assert "thread" not in guest.post("/assistant/chat", json={"message": "Tamu"}).json
        for owner, other in (("citizen", "admin"), ("admin", "citizen")):
            client = login(owner)
            question = f"Pertanyaan pribadi {owner}"
            thread = client.post("/assistant/chat", json={"message": question}).json["thread"]
            assert client.post("/assistant/chat", json={"thread": thread, "message": "Lanjutan"}).json["thread"] == thread
            page = login(owner).get(f"/assistant?thread={thread}")
            assert question in page.text and "Lanjutan" in page.text
            assert "no-store" in page.headers["Cache-Control"]
            for outsider in (guest, login(other)):
                assert question not in outsider.get("/assistant").text
                assert outsider.get(f"/assistant?thread={thread}").status_code == 404
                assert outsider.post("/assistant/chat", json={"thread": thread, "message": "Test"}).status_code == 404
    with app.app_context():
        assert db.session.query(ChatTurn).count() == 4
