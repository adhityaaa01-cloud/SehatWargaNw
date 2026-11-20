from app.extensions import db


class ChatTurn(db.Model):
    __tablename__ = "chat_turns"
    __table_args__ = (db.Index("ix_chat_turn_owner_thread", "user_id", "thread", "id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    thread = db.Column(db.String(32), nullable=False)
    first_turn = db.Column(db.Boolean, nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
