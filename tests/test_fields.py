from marshmallow_jsonapi import fields
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.schema import JSONAPISchema


def test_jsonapi_relationship_id_attribute():

    class OtherSchema(JSONAPISchema):
        class Meta:
            type_ = 'bar'
        id = fields.Str()

    class TestSchema(JSONAPISchema):
        class Meta:
            type_ = 'foo'
        id = fields.Str()
        rel = JSONAPIRelationship(
            id_attribute='rel_id',
            schema=OtherSchema,
            include_resource_linkage=True,
            type_='bar'
        )

    d = TestSchema().dump(dict(rel=dict(id='bar'), rel_id='bar_id', id='foo'))
    assert d['data']['relationships'] == {
        'rel': {
            'data': {
                'type': 'bar',
                'id': 'bar_id',
            }
        }
    }


def test_jsonapi_relationship_not_rendered():

    class OtherSchema(JSONAPISchema):
        class Meta:
            type_ = 'bar'
        id = fields.Str()

    class TestSchema(JSONAPISchema):
        class Meta:
            type_ = 'foo'
        id = fields.Str()
        rel = JSONAPIRelationship(
            schema=OtherSchema,
            type_='bar'
        )

    d = TestSchema().dump(dict(rel=dict(id='bar'), rel_id='bar_id', id='foo'))
    assert 'relationships' not in d['data']
