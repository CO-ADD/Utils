"""
Used and import for all application filter views
"""
from datetime import datetime
import pandas as pd
import django_filters
from django import forms
from django.views.generic import ListView
from django.db.models import Q, CharField, TextField, ForeignKey, IntegerField, Func, Value, ManyToManyField
from django.db.models import CharField, Value
from django.db.models.functions import Cast
from django.contrib.postgres.fields import ArrayField
from django.db.models.expressions import RawSQL
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest
from django.core.validators import MinLengthValidator


# -- create a function for search all fields--
def get_all_fields_q_object(model, search_value, exclude_fields=None, prefix=None, submodel=False):
    
    q_object = Q()
    exclude_fields = exclude_fields or []
    searchfields=[]
    if submodel:
        searchfields.append(model._meta.pk)
    else:
        searchfields=[field for field in model._meta.get_fields()]
    for field in searchfields:
        if field.name in exclude_fields:
            continue
        lookup_field_name = f"{prefix}__{field.name}" if prefix else field.name   
        if isinstance(field, (CharField, TextField)):
            q_object |= Q(**{f"{lookup_field_name}__icontains": search_value})        
        elif isinstance(field, ForeignKey):
            related_model = field.related_model
            related_q_object = get_all_fields_q_object(related_model, search_value, exclude_fields=exclude_fields, prefix=lookup_field_name, submodel=True)
            q_object |= related_q_object
        elif isinstance(field, IntegerField):
            try:
                int_value = int(search_value)
                q_object |= Q(**{lookup_field_name: int_value})
            except ValueError:
                pass       
        elif isinstance(field, ArrayField):
            q_object |= Q(**{f'{lookup_field_name}__icontains': search_value})       
        elif isinstance(field, ManyToManyField):
            related_model = field.related_model
            related_q_object = get_all_fields_q_object(related_model, search_value, exclude_fields=exclude_fields, prefix=lookup_field_name, submodel=True)
            q_object |= related_q_object
        # # Add more field types as needed...

    return q_object

def get_all_fields_q_object_deep(model, search_value, exclude_fields=None, prefix=None):

    q_object = Q()
    exclude_fields = exclude_fields or []

    for field in model._meta.get_fields():
        if field.name in exclude_fields:
            continue
        lookup_field_name = f"{prefix}__{field.name}" if prefix else field.name
        if isinstance(field, (CharField, TextField)):
            q_object |= Q(**{f"{lookup_field_name}__icontains": search_value})
        
        elif isinstance(field, ForeignKey):
            related_model = field.related_model
            related_q_object = get_all_fields_q_object_deep(related_model, search_value, exclude_fields=exclude_fields, prefix=lookup_field_name)
            q_object |= related_q_object
        elif isinstance(field, IntegerField):
            try:
                int_value = int(search_value)
                q_object |= Q(**{lookup_field_name: int_value})
            except ValueError:
                pass       
        elif isinstance(field, ArrayField):
            q_object |= Q(**{f'{lookup_field_name}__icontains': search_value})        
        elif isinstance(field, ManyToManyField):
            related_model = field.related_model
            related_q_object = get_all_fields_q_object_deep(related_model, search_value, exclude_fields=exclude_fields, prefix=lookup_field_name)
            q_object |= related_q_object
        # # Add more field types as needed...

    return q_object

# -- Filterset base Class--

from django.contrib import messages
class Filterbase_base(django_filters.FilterSet):
    Search_all_fields = django_filters.CharFilter(method='filter_all_fields', widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Search in All Fields', }), validators=[MinLengthValidator(10)])

   
    def multichoices_filter(self, queryset, name, value):
        lookup='__'.join([name, 'overlap'])
        return queryset.filter(**{lookup: value})
    
    def filter_all_fields(self, queryset, name, value):
        if value:
            
            exclude_fields = ['password',]
            q_object = get_all_fields_q_object(self._meta.model, value, exclude_fields=exclude_fields)
            return queryset.filter(q_object)
        return queryset
    
    def filter_all_fields_deep(self, queryset, name, value):
        if value:
            exclude_fields = ['password','astatus', 'acreated_at', 'aupdated_at', 'adeleted_at', 'acreated', 'aupdated', 'adeleted']
            q_object = get_all_fields_q_object_deep(self._meta.model, value, exclude_fields=exclude_fields)
            return queryset.filter(q_object)
        return queryset
    
    def __init__(self, *args, **kwargs):
        deep=kwargs.pop('deep') # switcher deep search or one-table search
        super().__init__(*args, **kwargs)
        if deep == True:
            self.filters['Search_all_fields'].method = 'filter_all_fields_deep'
        for field in self.filters:
            if 'CharFilter' == self.filters[field].__class__.__name__:
                self.filters[field].lookup_expr='icontains'
          
class Filterbase(Filterbase_base):

    @property
    def qs(self):
        parent = super().qs
        return parent.filter(astatus__gte=0)
    
 # utils for filteredListView method def ordered_by
def find_item_index(lst, item):

    for i, element in enumerate(lst):
        if isinstance(element, dict):
            if item in element.keys():
                return i
        elif element == item:
            return i
        
    return -1

# --Filter view base class--
class FilteredListView(ListView):
    filterset_class = None #each filterset class based on class Filterbase
    filterset_class_all = None #search in related tables thorough
    paginate_by = 50
    model_fields = None
    order_by = None
    filter_request = None
    filter_Count = None
    app_name = None
    model_name = None
  
    def get_queryset(self):

        # Get the queryset however you usually would.  For example:
        queryset = super().get_queryset()
        kwargs={'deep': False}      
        # Check if the reset request is submitted
        # Remove the stored queryset from the session
        if self.request.GET.get('reset')=='True':
            if 'cached_queryset' in self.request.session:
                del self.request.session[f'{self.model}_cached_queryset'] 
                
        # Instantiate the filterset with either the stored queryset from the session or the default queryset
        # ---- Switch off cache queryset
        # if self.request.session.get('cached_queryset'):
        #     stored_queryset_pks = self.request.session['cached_queryset']
        #     stored_queryset = queryset.filter(pk__in=stored_queryset_pks)
        # ----
        if 'applymulti' in self.request.GET:
            kwargs={'deep': True}
            self.filterset = self.filterset_class(self.request.GET,  queryset = queryset, **kwargs)
        else:
            self.filterset = self.filterset_class(self.request.GET, queryset = queryset, **kwargs)
        # Cache the filtered queryset in the session
        filtered_queryset_pks = self.filterset.qs.distinct().values_list('pk', flat = True)
        self.request.session[f'{self.model}_cached_queryset'] = list(filtered_queryset_pks) if filtered_queryset_pks else None  
        # Then use the query parameters and the queryset to
        # instantiate a filterset and save it as an attribute
        # on the view instance for later.
        # Return the filtered queryset
        order=self.get_order_by()
        self.filter_Count = self.filterset.qs.distinct().count()
        if order:           
            order = order.replace(".", "__")
            return self.filterset.qs.distinct().order_by(order)
        
        return self.filterset.qs.distinct()

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        self.context_list = context['object_list']
        filter_record_dict = {key: self.request.GET.getlist(key) for key in self.request.GET if self.request.GET.getlist(key)!=[""] and key not in ['paginate_by','page', 'csrfmiddlewaretoken', 'reset', "pivot", "applysingle", "applymulti"]}
        filter_record = "Selected: "+str(filter_record_dict).replace("{", "").replace("}", "") if str(filter_record_dict).replace("{", "").replace("}", "") else None
        # Pass the filterset to the template - it provides the form.
        context['filter'] = self.filterset
        context['paginate_by'] = self.get_paginate_by(self, **kwargs)
        context['fields'] = self.model.get_fields(fields = self.model_fields)
        context['filterset'] = filter_record
        context['Count'] = self.model.objects.count()
        context['querycount'] = self.filter_Count
        
        return context

    def get_paginate_by(self, queryset):
        qs=super().get_queryset()
        paginate_by= self.request.GET.get("paginate_by", self.paginate_by)

        return paginate_by
 
    def get_order_by(self):   

        order_by=self.request.GET.get("order_by", self.order_by) or None
        acs_decs=""
        if order_by:
            order_field=""
            if order_by[0]=="-":
                acs_decs=order_by[0]
                order_field=order_by[1:]
            else:
                order_field=order_by              
            index=find_item_index(list(self.model_fields.values()), order_field)
            order_by=acs_decs+ list(self.model_fields.keys())[index]
            return order_by
        
        return order_by
    
    # 
 