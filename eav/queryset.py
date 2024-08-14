import typing
import uuid
from collections import defaultdict

from django.core.exceptions import FieldError

from eav.models import Value, Attribute

class Query:
    def __init__(self, meta):
        self.meta = meta
        self.query = {}
        self.negated_query = {}
        self.fields = self.meta.get_entity_fields()
        self.fields_map = {f['name']: f['data_type'] for f in self.fields}
        self.entity = self.meta.entity
        self.order_by = []
        self.select_related = []
        self.query_id = None
        self.negated_query_id = None
        
    @staticmethod
    def get_id(queries: dict) -> (str, typing.Optional[str]):
        if queries.get('id'):
            return "id", queries.get('id')
        elif queries.get('pk'):
            return "pk", queries.get('pk')
        return NotImplementedError, None
        
    def update(self, **kwargs):
        negate = kwargs.pop('negate', False)
        key, query_id = self.get_id(kwargs)
        
        if negate:
            if query_id:
                self.negated_query_id = query_id
                kwargs.pop(key)
            self.negated_query.update(kwargs)
        else:
            if query_id:
                self.negated_query_id = query_id
                kwargs.pop(key)
            self.query.update(kwargs)
        self.__validate_query()
        return self
    
    def __validate_query(self):
        for key, value in self.query.items():
            if key not in self.fields_map:
                self.query = {}
                raise FieldError(f'Cannot resolve keyword {key} into field. Choices are: {", ".join(self.fields_map)}')
        
        for key, value in self.negated_query.items():
            if key not in self.fields_map:
                self.negated_query = {}
                raise FieldError(f'Cannot resolve keyword {key} into field. Choices are: {", ".join(self.fields_map)}')
    
    def items(self):
        return self.query.items()
    
    def nitems(self):
        return self.negated_query.items()
    
    def __bool__(self):
        return bool(self.query) or bool(self.negated_query)

    def __prepare_query(self) -> typing.Tuple[dict, dict]:
        fields_map = self.fields_map
        q = {}
        for key, value in self.items():
            q["attribute__slug"] = key
            q[f'value_{fields_map[key]}'] = value

        n_q = {}
        for key, value in self.nitems():
            n_q["attribute__slug"] = key
            n_q[f'value_{fields_map[key]}'] = value

        return q, n_q
    
    def prepare(self) -> (dict, dict):
        filters, exclude = self.__prepare_query()
        if self.negated_query_id:
            exclude['row_id'] = self.negated_query_id
        if self.query_id:
            filters['row_id'] = self.query_id
        
        return filters, exclude
    

class ObjectQuerySet:
    prefetch = []
    query = None
    meta = None
    fields = None
    result_cache: typing.Optional[typing.List] = None
    rows = []

    def __init__(self, meta):
        self.meta = meta
        self.query = Query(meta)
        self.entity = self.meta.entity
        self.model = self.meta._class
    
    # Magic Methods
    
    def __repr__(self):
        return f'<ObjectQuerySet {self.meta.entity.slug.title()}>'
    
    def __str__(self):
        return self.meta.entity.slug
    
    def __iter__(self):
        self.fetch()
        try:
            return iter(self.result_cache)
        except TypeError:
            return iter([])
    
    def __len__(self):
        self.fetch()
        try:
            return len(self.result_cache)
        except TypeError:
            return 0
    
    def __bool__(self):
        self.fetch()
        return bool(self.result_cache)
    
    def __getitem__(self, index):
        self.fetch()
        try:
            return self.result_cache[index]
        except IndexError:
            raise IndexError(f'{self.meta.entity.slug} object index out of range')
        except TypeError:
            return None
        
    def fetch(self):
        if self.result_cache is None:
            filters, excludes = self.query.prepare()
            rows_id = (
                self.entity.values
                .filter(**filters)
                .exclude(**excludes)
                .values_list('row_id', flat=True)
                .distinct()
            )
            rows_id = list(map(str, rows_id))
            values_types = [f"value_{v}" for v in Attribute.DataTypes.values]
            results = defaultdict(dict)
            for row_id in rows_id:
                row = {}
                res = self.entity.values.filter(row_id=row_id).values('attribute__slug', 'attribute__data_type',
                                                                      *values_types)
                for r in res:
                    row[r['attribute__slug']] = r[f'value_{r["attribute__data_type"]}']
                results[row_id] = row
            if results:
                self.result_cache = []
                for row_id, result in results.items():
                    result['id'] = row_id
                    obj = self.meta._class(**result)
                    self.result_cache.append(obj)
            else:
                self.result_cache = None
                
        return self
        
    def _clone(self, **kwargs):
        self.query.update(**kwargs)
        return self
        
    def all(self):
        return self._clone()
    
    def get(self, **kwargs):
        return self._clone(**kwargs).fetch()[0]
    
    def count(self):
        return len(self)
    
    def filter(self, **kwargs):
        return self._clone(**kwargs)
    
    def exclude(self, **kwargs):
        return self._clone(negate=True, **kwargs)
    
    def __create(self, **kwargs) -> (uuid.UUID, typing.List['Value']):
        entity = self.entity
        if kwargs.get("id"):
            return self.__update(**kwargs)
        self.query = Query(self.meta)
        self._clone(**kwargs)
        return entity.create_values(kwargs)
    
    def __update(self, **kwargs) -> (uuid.UUID, typing.List['Value']):
        entity = self.entity
        row_id = kwargs.pop("id")
        self._clone(**kwargs)
        return entity.update_values(kwargs, row_id)
    
    def __prepare_values(self, row_id: uuid.UUID, values: typing.List['Value']):
        result = {}
        for value in values:
            result[value.attribute.slug] = value.value
        result['id'] = row_id
        obj = self.meta._class(**result)
        return obj
    
    def create(self, **kwargs):
        row_id, values = self.__create(**kwargs)
        return self.__prepare_values(row_id, values)
    
    def update(self, **kwargs):
        row_id, values = self.__update(**kwargs)
        return self.__prepare_values(row_id, values)
    
    def order_by(self, *args):
        self.query.order_by = args
        return self
