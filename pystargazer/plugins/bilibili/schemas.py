import fastjsonschema

from .models import DynamicType

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
    DynamicType.FORWARD: fastjsonschema.compile({
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
    DynamicType.PHOTO: fastjsonschema.compile({
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
    DynamicType.PLAIN: fastjsonschema.compile({
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
    DynamicType.VIDEO: fastjsonschema.compile({
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
