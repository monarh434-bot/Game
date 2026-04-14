from ai import WorldAI

def test_ai_becomes_friendly_on_hello():
    ai = WorldAI()
    ai.observe("chat", {"message": "hello spirit"})
    decision = ai.decide_event()
    assert ai.mood == "friendly"
    assert decision["type"] == "ai_message"

def test_ai_becomes_protective_on_remove():
    ai = WorldAI()
    ai.observe("block_remove", {"x": 0, "y": 1, "z": 0})
    decision = ai.decide_event()
    assert ai.mood == "protective"
    assert decision["type"] == "world_event"
