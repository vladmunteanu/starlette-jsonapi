from tortoise import fields, models


class Organization(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=256)
    contact_url = fields.CharField(max_length=500, null=True)
    contact_phone = fields.CharField(max_length=200, null=True)

    def __str__(self) -> str:
        return f"Organization {self.id}: {self.name}"

    def __repr__(self) -> str:
        return f"Organization {self.id}: {self.name}"


class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=256)

    organization = fields.ForeignKeyField('models.Organization', related_name='users')

    def __str__(self) -> str:
        return f"User {self.id}: {self.username}"

    def __repr__(self) -> str:
        return f"User {self.id}: {self.username}"


class Team(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=256)

    users = fields.ManyToManyField('models.User', related_name='teams')

    def __str__(self) -> str:
        return f"Team {self.id}: {self.name}"

    def __repr__(self) -> str:
        return f"Team {self.id}: {self.name}"
