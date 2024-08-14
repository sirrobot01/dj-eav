import types
import typing

from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models.base import subclass_exception

from eav.queryset import ObjectQuerySet
from eav.utils import DATA_TYPES_MAP

T = typing.TypeVar('T')


class Meta(typing.Generic[T]):
    def __repr__(self):
        return f'<Meta {self.entity.slug}>'

    def __str__(self):
        return self.entity.slug

    def __init__(self, entity, _cls):
        self.entity = entity
        self._class = _cls
        self.fields_dict = _cls.__fields__
        self.fields = self.fields_dict.values()
        self.abstract = False
        self.swapped = False
        self.app_label = "eav"
        self.model_name = self.entity.slug
        self.verbose_name_plural = self.entity.name.title()
        self.verbose_name = self.entity.name
        self.object_name = self.entity.slug.title()
        self.app_config = None
        self.ordering = []
        self.unique_together = []
        self.total_unique_constraints = []
        self.indexes = []
        self.private_fields = []
        self.concrete_fields = []
        self.many_to_many = []
        self.pk = self.get_field('id')

    def get_fields(self):
        if self.fields is None:
            self.fields = self._class.__fields__
        return self.fields

    def get_field(self, field_name):
        field = self.fields_dict.get(field_name)
        if field is None:
            raise FieldDoesNotExist(f'Field {field_name} does not exist')
        return field

    def get_entity_fields(self):
        return self.entity._get_fields()


class DynamicClassMeta(type):
    def __new__(cls, name, bases, dct):
        module = dct.pop("__module__", None)
        fields = dct.get('__fields__', {})
        entity = dct.pop('__entity__', None)
        if dct.get("__annotations__") is None:
            dct["__annotations__"] = {}

        for field_name, field in fields.items():
            dct["__annotations__"][field_name] = field.field_type
            dct[field_name] = field
        _cls = super().__new__(cls, name, bases, dct)
        if entity is not None:
            meta = Meta(entity, _cls)
            _cls.contribute_to_class("_meta", meta)
            _cls.contribute_to_class("objects", ObjectQuerySet(meta))
            _cls.contribute_to_class(
                "DoesNotExist",
                subclass_exception(
                    "DoesNotExist",
                    (ObjectDoesNotExist,),
                    module,
                    attached_to=_cls,
                )
            )
            _cls.contribute_to_class(
                "MultipleObjectsReturned",
                subclass_exception(
                    "MultipleObjectsReturned",
                    (MultipleObjectsReturned,),
                    module,
                    attached_to=_cls,
                )
            )
            update_fields_post_create(_cls)
        return _cls

    def __repr__(cls):
        return f'<class {cls.__name__}>'

    def contribute_to_class(cls, name, value):
        setattr(cls, name, value)


class DynamicClass(typing.Generic[T], metaclass=DynamicClassMeta):
    __fields__: typing.Dict[str, 'Field']
    __annotations__: typing.Dict[str, typing.Any]

    def __init__(self, **kwargs):
        self.__set_values(**kwargs)

    def __repr__(self):
        pk = getattr(self, 'id', None)
        return f'<{self.__class__.__name__} {pk}>'

    def save(self) -> None:
        pass

    def __str__(self):
        return self.__repr__()

    def __set_values(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def contribute_to_class(cls, name, value):
        setattr(cls, name, value)
        
    def serializable_value(self, field_name: str) -> typing.Any:
        meta = getattr(self, '_meta')
        try:
            field = meta.get_field(field_name)
        except FieldDoesNotExist:
            return getattr(self, field_name)
        return getattr(self, field.attname)
    
    @property
    def pk(self):
        return getattr(self, 'id', None)


def update_fields_post_create(cls):
    """
    Update the fields of the class after it has been created.
    """
    for field_name, field in cls.__fields__.items():
        setattr(field, 'related_model', cls)
    

def init_field(field: dict) -> 'Field':
    """
    Add fields to the class.
    """
    field_name = field["name"]
    field_type = DATA_TYPES_MAP.get(field["data_type"], str)
    required = field.get("required", False)
    return Field(field_name, field_type, required=required)


def build_eav_class(entity) -> type:
    """
    Build a class that represents an entity with its attributes.
    """
    fields = {
        field["name"]: init_field(field) for field in entity._get_fields()
    }
    pk = Field("id", str, required=True)
    fields["id"] = pk
    
    attrs: dict = {
        "__fields__": fields,
        "__entity__": entity,
        "__annotations__": {},
    }

    return types.new_class(entity.slug.title(), (DynamicClass[T],), {}, lambda ns: ns.update(attrs))


class Field:
    def __init__(
        self, name, field_type, default=None, required=False, unique=False, null=False, remote_field=None, attname=None,
        is_relation=None, related_model=None, auto_created=False
    ):
        self.field_type = field_type
        self.default = default
        self.required: bool = required
        self.name: str = name
        self.unique: bool = unique
        self.null: bool = null
        self.remote_field = remote_field
        self.attname: str = attname or name
        self.is_relation: bool = is_relation
        self.related_model = related_model
        self.auto_created: bool = auto_created
        self.verbose_name = name.replace('_', ' ').title()

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name, self.default)

    def __set__(self, instance, value):
        if value is None and self.required:
            raise ValueError(f"The field '{self.name}' is required and cannot be None.")
        if value is not None and not isinstance(value, self.field_type):
            raise TypeError(
                f"Expected value of type {self.field_type.__name__} for field '{self.name}', got {type(value).__name__}")
        instance.__dict__[self.name] = value
        
    def to_python(self, value):
        return value
