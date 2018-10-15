# always make explicit includes
from peewee import Model, PrimaryKeyField, CharField, DateTimeField
from database.db import BaseModel


class User(BaseModel):
    id = PrimaryKeyField()
    email = CharField()
    nickname = CharField()
    password = CharField()
    created_at = DateTimeField()
    updated_at = DateTimeField()