### Django EAV (Entity-Attribute-Value)

IN PROGRESS

Django EAV (Entity-Attribute-Value) is a technique for storing data with a large number of attributes that might be sparsely populated.

Read more about EAV at [Wikipedia](http://en.wikipedia.org/wiki/Entity-attribute-value_model).


This is a true EAV implementation, not just a dynamic schema. It is designed to be a complete replacement for the standard ORM.

### Implemented API
- Django Admin List View
- Model.objects
    - .filter
    - .exclude
    - .get
    - .all
    - .create
    - .update

### TODO
- Full Django Admin support
- Model.objects
    - .delete
    - .update_or_create
    - .bulk_create
    - .values
    etc
- Cleaner Readme
- Tests


### Installation

#### In Progress

### Usage

```python
from eav.models import Entity, Attribute

# Create an entity
entity = Entity.objects.create(name="City", slug="city")

# Create an attribute
Attribute.objects.create(entity=entity, name="population", datatype=Attribute.DataTypes.INTEGER)
Attribute.objects.create(entity=entity, name="name", datatype=Attribute.DataTypes.STRING)
Attribute.objects.create(entity=entity, name="founded", datatype=Attribute.DataTypes.DATE)

# Create a Model that uses the EAV system

from eav.models import EAV

City = EAV("city")

new_york = City.objects.create(name="New York", founded="1624-01-01", population=8000000)
sf = City.objects.create(name="San Francisco", founded="1776-06-29", population=800000)

# Query the model

cities = City.objects.filter(name="New York")
for city in cities:
    print(city.name, city.founded, city.population)


cities = City.objects.filter(population=8000000).exclude(name="New York")
for city in cities:
    print(city.name, city.founded, city.population)

```
