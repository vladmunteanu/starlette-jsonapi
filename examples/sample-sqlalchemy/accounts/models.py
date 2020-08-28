import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Organization(Base):
    __tablename__ = 'organizations'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)
    contact_url = sa.Column(sa.String)
    contact_phone = sa.Column(sa.String)


class User(Base):
    __tablename__ = 'users'

    id = sa.Column(sa.Integer, primary_key=True)
    username = sa.Column(sa.String)
    organization_id = sa.Column(sa.Integer, sa.ForeignKey('organizations.id'))
    organization = orm.relationship('Organization')


class TeamsUsers(Base):
    __tablename__ = 'teams_users'

    id = sa.Column(sa.Integer, primary_key=True)
    team_id = sa.Column(sa.Integer, sa.ForeignKey('teams.id'))
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'))


class Team(Base):
    __tablename__ = 'teams'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)
    users = orm.relationship('User', secondary='teams_users')
