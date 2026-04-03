from marshmallow import Schema, fields, post_dump


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str(load_only=True, required=False)  # For creating users via API
    password_hash = fields.Str(load_only=True)  # Only for loading, never dump
    role = fields.Str(load_default="user", dump_default="user")
    is_active = fields.Bool(load_default=True, dump_default=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_dump
    def extract_enum_value(self, data, **kwargs):
        """Convert UserRole enum to string value for serialization"""
        if "role" in data and isinstance(data["role"], str) and "UserRole" in data["role"]:
            # Extract just the value part: "UserRole.ADMIN" -> "admin"
            data["role"] = data["role"].split(".")[-1].lower()
        return data
