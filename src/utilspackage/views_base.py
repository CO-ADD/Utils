"""
General base view class or function used by all applications
"""
import os
import pandas as pd
import json
from datetime import datetime

from django.apps import apps
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError
from django.shortcuts import HttpResponse, render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.generic.edit import FormView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from apputil.models import ApplicationLog

# --utilized in Decoration has_permissions, an Alert on Permissions--
def permission_not_granted(req):
    return HttpResponse("Permission Not Granted")

# --Super UserRequire Mixin--
class SuperUserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = '/'

    def test_func(self):
        return self.request.user.has_permission('Admin')

# --create view class--
class SimplecreateView(LoginRequiredMixin, View):
    form_class = None
    template_name = None
    transaction_use = 'default'

    def get(self, request, *args, **kwargs):
        form=self.form_class()
        return render(request, self.template_name, {'form':form})
    def post(self, request, *args, **kwargs):
        
        form =self.form_class(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic(using=self.transaction_use):
                instance=form.save(commit=False)
                kwargs={'user': request.user}
                instance.save(**kwargs)
                ## python logging levels: 10-'DEBUG', 40-'ERROR', 50-'CRITICAL', 30-'WARNING', 20-'INFO', 0-'Notset'
                 #LogCode, LogProc,LogType,LogUser,LogObject,LogDesc,LogStatus
                ApplicationLog.add('Create',str(instance.pk),'Info',request.user,instance.__str__(),'Create a new entry','Completed')
            return redirect(request.META['HTTP_REFERER'])
        else:
            messages.error(request, form.errors)
            return redirect(request.META['HTTP_REFERER'])

## create view with searching input:



# --update view class--
class SimpleupdateView(LoginRequiredMixin, View):
    form_class = None
    template_name = None
    model = None
    transaction_use = 'default'

    def get_object_byurlname(self, slug):
        return get_object_or_404(self.model, urlname=slug)
    
    def get_object(self, pk):
        return get_object_or_404(self.model, pk=pk)

    def get(self, request, *args, **kwargs):
        if 'slug' in kwargs:
            slug=kwargs.get("slug")
            object_=self.get_object_byurlname(slug)
        else: 
            pk=kwargs.get("pk")
            object_=self.get_object(pk)
        form=self.form_class(instance=object_)
        return render(request, self.template_name, {'form':form})

    def post(self, request, *args, **kwargs):
        if 'slug' in kwargs:
            slug=kwargs.get("slug")
            object_=self.get_object_byurlname(slug)
        else: 
            pk=kwargs.get("pk")
            object_=self.get_object(pk)
        form =self.form_class(request.POST, instance=object_)
        if form.is_valid():
            with transaction.atomic(using=self.transaction_use):
                object_new=form.save(commit=False)
                kwargs={'user': request.user}
                object_new.save(**kwargs)
                ApplicationLog.add('Update',str(object_new.pk),'Info',request.user,object_new.__str__(),'Update an entry','Completed')
            return redirect(request.META['HTTP_REFERER'])
        else:
            messages.error(request, form.errors)
            return redirect(request.META['HTTP_REFERER'])

class SimpledeleteView(SuperUserRequiredMixin, SimpleupdateView):
    model=None
    transaction_use = 'default'
    

    def post(self, request, *args, **kwargs):
        if 'slug' in kwargs:
            slug=kwargs.get("slug")
            object_=self.get_object_byurlname(slug)
        else: 
            pk=kwargs.get("pk")
            object_=self.get_object(pk)
        with transaction.atomic(using=self.transaction_use):
            kwargs={'user': request.user}
            print("try deletess")
            try:
                object_.delete(**kwargs)
                ApplicationLog.add('Delete','log_proc','Warning',request.user, object_.pk, 'switch entry_astatus -9','Completed')            
            except Exception as err:
                messages.error(request, err)

        return redirect(request.META['HTTP_REFERER'])
    


# --update view class with htmx put request--
from django.http import QueryDict
class HtmxupdateView(LoginRequiredMixin, View):
    form_class = None
    template_name = None
    template_partial = None
    model = None
    transaction_use = 'default'
    
    def get_object(self, pk):
        return get_object_or_404(self.model, pk=pk)

    def get(self, request, *args, **kwargs):
        pk=kwargs.get("pk")
        object_=self.get_object(pk)
        form=self.form_class(instance=object_)
        context={
        "form":form,
        "object":object_,
    }
        return render(request, self.template_name, context)

    def put(self, request, *args, **kwargs):
        pk=kwargs.get("pk")
        object_=self.get_object(pk)
        qd=QueryDict(request.body).dict()
        form =self.form_class(data=qd, instance=object_)
        context={
        "form":form,
        "object":object_,
    }
        if request.GET.get('_value') == 'cancel':
            return render(request, self.template_partial, context)
        elif form.is_valid():
            with transaction.atomic(using=self.transaction_use):
                object_new=form.save(commit=False)
                kwargs={'user': request.user}
                object_new.save(**kwargs)
                ApplicationLog.add('Update',"model",'Info', request.user, 'object','Update an entry','Completed')              
            return render(request, self.template_partial, context)
        else:
            messages.error(request, form.errors)
            return render(request, self.template_partial, context)

# --View for simple update files and images to database--
class CreateFileView(LoginRequiredMixin,FormView):
    form_class = None
    model = None
    file_field = None
    related_name = None
    transaction_use = 'default'
    transaction_use_manytomany = 'default'

    def dispatch(self, request, *args, **kwargs):
        self.object_ = get_object_or_404(self.model, organism_id=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Handle AJAX file upload
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            print("ajax called")
            file_data = request.FILES.get(self.file_field)
            print(file_data)
            if file_data:
                file_path = default_storage.save(file_data.name, file_data)
                file_name = os.path.basename(file_path)
                file_type = file_data.content_type
                response = {
                    'name': file_name,
                    'type': file_type,
                    'path': file_path,
                }
                return JsonResponse(response)
        # Handle form submission
        else:
            return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        instance = form.save(commit=False)
        if getattr(instance, self.file_field):
            with transaction.atomic(using=self.transaction_use):
                kwargs={'user': self.request.user}
                instance.save(**kwargs)
            with transaction.atomic(using=self.transaction_use_manytomany):
                getattr(self.object_, self.related_name).add(instance)
                self.object_.save(**kwargs)
        else:
            messages.warning(self.request, 'No file provided.')
        return redirect(self.request.META['HTTP_REFERER'])

    def form_invalid(self, form):
        messages.warning(self.request, f'Update failed due to {form.errors} error')
        return redirect(self.request.META['HTTP_REFERER'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.object_
        return context
    
# --export view--
import ddrug.utils.tables as drugtbl

class DataExportBaseView(LoginRequiredMixin, View):
    '''
    Export Data in EXCEL or CSV Format
    '''
    selected_pks_string = None
    organism = None 

    def post(self, request):
        items=None
        app_name = request.POST.get('app_name')
        model_name = request.POST.get('model_name')
        
        if not app_name or not model_name:
            messages.error(request, "No application or model name were provided for export.")
            return redirect(request.path)
        try:
            Model = apps.get_model(app_name, model_name)
        except LookupError:
            # Handle the case where the model does not exist.
            return HttpResponse("Model not found.")
        self.selected_pks_string = request.POST.get('selected_pks')
        self.organism = request.POST.get('organism_pk')

        if self.selected_pks_string == 'SelectAll':
            items = Model.objects.filter(pk__in=request.session.get("cached_queryset") or Model.objects.all())
            # table = Model.get_pivottable(querydata=items, columns_str=columns_str, index_str=index_str, aggfunc=aggfunc_name, values=values)
        elif self.selected_pks_string:
            selected_pks = json.loads(self.selected_pks_string)
            items = Model.objects.filter(pk__in=selected_pks)
        else:
            if self.organism and model_name == 'MIC_COADD':
                displaycols = ['Drug Class', 'Drug Name', 'MIC', 'BP Profile', 'BatchID', 'Source', 'BP Source']
                df = drugtbl.get_Antibiogram_byOrgID(self.organism)
                df.reset_index(inplace=True)
                df = df[displaycols]
            else:
                messages.error(request, "No items were selected for export.")
                return redirect(request.META['HTTP_REFERER'])
        if items:
            df = pd.DataFrame.from_records(items.values())

        if 'acreated_at' in df.columns:
            df['acreated_at'] = pd.to_datetime(df['acreated_at']).dt.tz_localize(None).apply(lambda a: a.date())
        if 'aupdated_at' in df.columns:
            df['aupdated_at'] = pd.to_datetime(df['aupdated_at']).dt.tz_localize(None).apply(lambda a: a.date())
        if 'adeleted_at' in df.columns:
            df['adeleted_at'] = pd.to_datetime(df['adeleted_at']).dt.tz_localize(None).apply(lambda a: a.date())

        current_date = datetime.now().strftime('%Y-%m-%d')
        filename = f'{model_name}_{current_date}'
        response = HttpResponse("No valid export option was selected.")
        if "csvdownload" in request.POST:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            df.to_csv(path_or_buf=response, index=False)

        elif "xlsxdownload" in request.POST:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
            df.to_excel(excel_writer=response, index=False)

        return response
 

