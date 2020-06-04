import fastjsonschema

room_info_schema = fastjsonschema.compile({
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "code": {
            "type": "number"
        },
        "msg": {
            "type": "string"
        },
        "message": {
            "type": "string"
        },
        "data": {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "number"
                },
                "room_id": {
                    "type": "number"
                },
                "live_status": {
                    "type": "number"
                },
                "title": {
                    "type": "string"
                },
                "user_cover": {
                    "type": "string"
                }
            }
        }
    }
})
