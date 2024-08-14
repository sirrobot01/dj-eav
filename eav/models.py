import typing
import uuid

from django.db import models, IntegrityError
from django.utils.text import slugify

from eav.eav import build_eav_class


# Create your models here.

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        abstract = True

class Entity(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    meta = models.JSONField(default=dict)
    
    class Meta:
        verbose_name_plural = 'Entities'
    
    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f'<Entity {self.slug}>'
        
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Entity, self).save(*args, **kwargs)
        
    def _get_fields(self) -> typing.List[dict]:
        fields = [{"name": "id", "data_type": "string", "required": True}]
        attributes = self.attributes.values_list('name', 'slug', 'data_type', 'required')
        for name, slug, data_type, required in attributes:
            fields.append({"name": slug, "data_type": data_type, "required": required})
        return fields
    
    def create_row_id(self) -> str:
        row_id = uuid.uuid4()
        while Value.objects.filter(entity=self, row_id=row_id).exists():
            row_id = uuid.uuid4()
        return str(row_id)
    
    def create_values(self, value_data: dict) -> (str, typing.List['Value']):
        values = []
        row_id = self.create_row_id()
        attributes = self.attributes.all()
        attrs = {attr.slug: attr for attr in attributes}
        for key, value in value_data.items():
            if key not in attrs:
                raise ValueError(f'Attribute {key} does not exist')
            v = Value(entity=self, attribute=attrs[key], row_id=row_id)
            v.value = value
            values.append(v)

        # Create an empty value for attributes that were not provided
        for slug, attr in attrs.items():
            if slug not in value_data:
                value = Value(entity=self, attribute=attr, row_id=row_id)
                values.append(value)
        try:
            Value.objects.bulk_create(values)
        except IntegrityError:
            raise ValueError('Duplicate values for unique fields. Have you created the row before?')
        return row_id, values
    
    def update_values(self, value_data: dict, row_id: str) -> (str, typing.List['Value']):
        attributes = self.attributes.all()
        attrs = {attr.slug: attr for attr in attributes}
        for key in value_data:
            if key not in attrs:
                raise ValueError(f'Attribute {key} does not exist')

        existing_values = Value.objects.filter(entity=self, attribute__in=attrs.values(), row_id=row_id)
        existing_values_dict = {value.attribute.slug: value for value in existing_values}
        values_to_update = []
        values_to_create = []
        updated_value_fields = []
        for key, value in value_data.items():
            if key in existing_values_dict:
                existing_value = existing_values_dict[key]
                existing_value.value = value
                values_to_update.append(existing_value)
                updated_value_fields.append(existing_value.attribute.data_type)
            else:
                v = Value(entity=self, attribute=attrs[key], row_id=row_id)
                v.value = value
                values_to_create.append(v)
        
        Value.objects.bulk_update(values_to_update, updated_value_fields)
        Value.objects.bulk_create(values_to_create)
        return row_id,  values_to_update + values_to_create
            

class Attribute(BaseModel):
    class DataTypes(models.TextChoices):
        STRING = 'string'
        INTEGER = 'integer'
        FLOAT = 'float'
        BOOLEAN = 'boolean'
        DATE = 'date'
        DATETIME = 'datetime'
        JSON = 'json'
        FILE = 'file'
        FOREIGN_KEY = 'foreign_key'
        MANY_TO_MANY = 'many_to_many'
        
    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name='attributes',
        related_query_name='attribute',
        null=True,
        blank=True,
        db_index=True
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    data_type = models.CharField(max_length=255, choices=DataTypes.choices, default=DataTypes.STRING)
    required = models.BooleanField(default=False)
    meta = models.JSONField(default=dict)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Attribute, self).save(*args, **kwargs)
        
class Value(BaseModel):
    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name='values',
        related_query_name='value',
        null=True,
        blank=True,
        db_index=True
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name='values',
        related_query_name='value',
        null=True,
        blank=True,
        db_index=True
    )
    
    row_id = models.UUIDField(default=uuid.uuid4)  # Act as a row id for the entity(Connects each value to a row)
    
    value_string = models.CharField(max_length=255, null=True, blank=True)
    value_integer = models.IntegerField(null=True, blank=True)
    value_float = models.FloatField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_datetime = models.DateTimeField(null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)
    value_file = models.FileField(null=True, blank=True)
    value_foreign_key = models.CharField(max_length=255, null=True, blank=True)
    value_many_to_many = models.JSONField(null=True, blank=True, default=list)
    
    def _get_value(self):
        value_type = f"value_{self.attribute.data_type}"
        try:
            return getattr(self, value_type)
        except AttributeError:
            raise ValueError(f'Invalid data type: {self.attribute.data_type}')

    def _set_value(self, value):
        value_type = f"value_{self.attribute.data_type}"
        setattr(self, value_type, value)

    value = property(_get_value, _set_value)
    
    def __str__(self):
        return f'{self.entity.name} - {self.attribute.name}'
    
    class Meta:
        unique_together = ('entity', 'attribute', 'row_id')


def EAV(entity_slug: str):
    """
    Get an entity class.
    """
    try:
        entity = Entity.objects.get(slug=entity_slug)
    except Entity.DoesNotExist:
        raise ValueError(f'Entity {entity_slug} does not exist')

    return build_eav_class(entity)
