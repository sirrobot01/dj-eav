from django.contrib import admin

from eav.eav import build_eav_class
from eav.models import Entity, Attribute


# Register your models here.

class DynamicModelAdmin(admin.ModelAdmin):
    list_display = None
    
    def get_queryset(self, request):
        qs = self.model.objects.all()
        return qs
    
    def get_list_display(self, request):
        if self.list_display:
            return self.list_display
        fields = [f.name for f in self.model._meta.fields]
        return fields

def register_eav_models():
    entities = Entity.objects.all()
    for entity in entities:
        cls = build_eav_class(entity)
        admin.site.register([cls], DynamicModelAdmin)

class AttributeInline(admin.TabularInline):
    model = Attribute
    exclude = ['meta']
    prepopulated_fields = {'slug': ('name',)}
    extra = 0

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    model = Entity
    list_display = ['name', 'slug', 'active']
    search_fields = ['slug', 'name',]
    fields = ['name', 'slug', 'active', ]
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['slug']
    inlines = [AttributeInline]
    

register_eav_models()
    

