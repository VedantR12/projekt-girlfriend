def save_live_memories(db, user_id, persona_id, memories):

    for m in memories:
        db.insert("live_memories", {
            "user_id": user_id,
            "persona_id": persona_id,
            "text": m["text"],
            "type": m["type"],
            "importance": m["importance"]
        })