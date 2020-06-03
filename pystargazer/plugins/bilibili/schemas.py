import fastjsonschema

card_schema = fastjsonschema.compile({
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "desc": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "number"
                },
                "dynamic_id": {
                    "type": "number"
                }
            },
            "required": [
                "type",
                "dynamic_id"
            ]
        },
        "card": {
            "type": "string"
        }
    },
    "required": [
        "desc",
        "card"
    ]
})

dyn_schemas = {
    1: fastjsonschema.compile({  # forward
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "item": {
                "type": "object",
                "properties": {}
            },
            "origin": {
                "type": "string"
            }
        },
        "required": [
            "item",
            "origin"
        ]
    }),
    2: fastjsonschema.compile({  # pic
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "item": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string"
                    },
                    "pictures": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "img_src": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "img_src"
                            ]
                        }
                    }
                },
                "required": [
                    "description",
                    "pictures"
                ]
            }
        },
        "required": [
            "item"
        ]
    }),
    4: fastjsonschema.compile({  # plaintext
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "item": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string"
                    }
                },
                "required": [
                    "content"
                ]
            }
        },
        "required": [
            "item"
        ]
    }),
    8: fastjsonschema.compile({  # video
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "aid": {
                "type": "number"
            },
            "pic": {
                "type": "string"
            },
            "title": {
                "type": "string"
            }
        },
        "required": [
            "aid",
            "pic",
            "title"
        ]
    })
}
