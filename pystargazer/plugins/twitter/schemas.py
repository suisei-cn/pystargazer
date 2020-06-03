import fastjsonschema

raw_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {
                "type": "number"
            },
            "id_str": {
                "type": "string"
            },
            "text": {
                "type": "string"
            },
            "entities": {
                "type": "object",
                "properties": {
                    "media": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "number"
                                },
                                "id_str": {
                                    "type": "string"
                                },
                                "media_url": {
                                    "type": "string"
                                },
                                "media_url_https": {
                                    "type": "string"
                                },
                                "url": {
                                    "type": "string"
                                },
                                "type": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "id",
                                "id_str",
                                "media_url",
                                "media_url_https",
                                "url",
                                "type"
                            ]
                        }
                    }
                }
            },
            "retweeted_status": {
                "type": "object",
                "properties": {}
            }
        },
        "required": [
            "id",
            "id_str",
            "text",
            "entities"
        ]
    }
}

schema = fastjsonschema.compile(raw_schema)
