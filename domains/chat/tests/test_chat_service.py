from domains.chat.services.chat import ChatService


def test_build_messages_returns_system_and_user_payload():
    service = ChatService()

    messages = service._build_messages("두 번째 질문")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"][0]["type"] == "input_text"
    assert messages[1]["content"][0]["text"] == "두 번째 질문"
