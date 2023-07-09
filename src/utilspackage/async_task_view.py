'''
View for uploading Vitek PDFs
'''
from asgiref.sync import async_to_sync, sync_to_async
import datetime
import pandas as pd
import shutil
from django import forms
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import HttpResponse, render, redirect
from django.views import View
from django.views.generic.edit import FormView

from apputil.utils.files_upload import file_location, OverwriteStorage
from apputil.utils.form_wizard_tools import ImportHandler_WizardView, UploadFileForm, StepForm_1, FinalizeForm
from apputil.utils.validation_log import * 
from dorganism.models import Organism_Batch
from ddrug.utils.vitek import upload_VitekPDF_List

#==  VITEK Import View =============================================================

# --upload file view--

# customized Form
class VitekValidation_StepForm(StepForm_1):
    orgbatch_id=forms.ModelChoiceField(label='Choose an Organism Batch',
                                       widget=forms.Select(attrs={'class': 'form-control'}), 
                                       required=False, 
                                       help_text='(**Optional)',
                                       queryset=Organism_Batch.objects.filter(astatus__gte=0), )
    field_order = ['orgbatch_id', 'confirm']
# 
# for progress bar
def get_session_key(request):
    return request.session.session_key
# 
async def get_upload_progress(request):
    SessionKey = await sync_to_async(get_session_key)(request)
    # print(f'get upload progress at {datetime.datetime.now()}') #-- Async Test
    progress = await cache.aget(SessionKey) or {'processed': 0, 'file_name':"",'total': 0, 'uploadpdf_version':0}
    return JsonResponse(progress)
# 

# 
class Import_VitekView(View):
    '''
    This is asycn View for process files uploading, parsing and storing in Vitek tables
    - Uploaded files stored in directory-on-server/uploads temporarily
    - process steps stored in Session and messages stored in Cache temporarily 
      Session key:  'current_step'
      Cache keys:   SessionKey - for progress status
                    f'{username}_vitek_filelist' - for uploaded filenames
                    f'{username}_vitek_DirName'  - for uploaded file-path
                    f'{username}_vitek_result' (dict) - 1)validatoin_result
                                                        2)confirm_to_save
                    f'{username}_vitek_processControl' - control operate buttons and start/stop  
                    f'{username}_vitek_showForm', - control show/hide(error in files) step forms 
    - Temporarily stored will be deleted on finalized step or cancel/stop step.
    '''
    step_names = ["select_file", "upload", "finalize"]
    form_classes = {
        "select_file": UploadFileForm,
        "upload": VitekValidation_StepForm,
        "finalize": FinalizeForm,
    }
    template_name = 'ddrug/importhandler_vitek.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filelist = []
        self.orgbatch_id = None
        self.process_control='Start'
        self.show_form=True

    async def get(self, request, *args, **kwargs):
        username = await sync_to_async(getattr, thread_sensitive=True)(request.user, 'username')
        current_step = await sync_to_async(request.session.get, thread_sensitive=True)('current_step', self.step_names[0])
        form_class = self.form_classes[current_step]
        form = form_class()
        validation_result= await cache.aget(f'{username}_vitek_result', 'Please upload files...') 
        self.process_control=await cache.aget(f'{username}_vitek_processControl', 'Start')
        show_form=await cache.aget(f'{username}_vitek_showForm', self.show_form)
        print(f'get: {show_form}')
        context = {
            'form': form,
            'current_step': current_step,
            'validation_result': validation_result,
            'process_control': self.process_control,
            'show_form': show_form,
        }
        return await sync_to_async(render)(request, self.template_name, context)

    async def post(self, request, *args, **kwargs):
        context={}
        SessionKey = request.session.session_key
        username = await sync_to_async(getattr, thread_sensitive=True)(request.user, 'username')
        get_step = await sync_to_async(request.session.get, thread_sensitive=True)('current_step', self.step_names[0])
        # submit type Button control block##
        if 'Next' in request.POST:
            current_step=get_step
        elif 'Prev' in request.POST:
            await cache.adelete(f'{username}_vitek_showForm')
            if self.step_names.index(get_step) > 0:
                current_step = self.step_names[self.step_names.index(get_step)-1]
                await sync_to_async(request.session.__setitem__, thread_sensitive=True)('current_step', current_step)
            else:
                return redirect(request.META.get('HTTP_REFERER', '/'))

        elif 'Start' in request.POST:
            await cache.aset(f'{username}_vitek_processControl', 'Stop')
            current_step=self.step_names[0]
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        elif 'Stop' in request.POST:
            current_step=self.step_names[len(self.step_names)-1]
        ##
        ## process step handler:
        form_class = self.form_classes[current_step]
        form = form_class(request.POST, request.FILES)
        print(f'current step is : {current_step}')
        if form.is_valid():
            if current_step == 'select_file':
                await self.handle_select_file(request, SessionKey, username, form)
            elif current_step == 'upload':
                await self.handle_upload(request, SessionKey,username, form)
            elif current_step == 'finalize':
                await self.handle_finalize(request, SessionKey, username, form)

            # Move to next step
            try:
                next_step_index = self.step_names.index(current_step) + 1
                await sync_to_async(request.session.__setitem__, thread_sensitive=True)('current_step', self.step_names[next_step_index])
            except IndexError:
                print('End step')
                # message
                await sync_to_async(request.session.__setitem__, thread_sensitive=True)('current_step', self.step_names[0])
            except Exception as err:
                print(err)
                # message
            
            return redirect(request.META.get('HTTP_REFERER', '/'))  # Assuming that the next step is handled by the same view 
        
        else:
            print(f"form error: s{form.errors}")
            await self.handle_finalize(request, SessionKey, username, form)

        validation_result= await cache.aget(f'{username}_vitek_result')  # get file path
        show_form=await cache.aget(f'{username}_vitek_showForm', self.show_form) 
        context = {
            'form': form,
            'current_step': current_step,
            'validation_result': validation_result,
            'process_control': self.process_control,
            'show_form': show_form,
        }
        return await sync_to_async(render)(request, self.template_name, context)

    async def handle_select_file(self, request, SessionKey, username, form):
        DirName = await sync_to_async(file_location)(request.user)  # define file store path during file process
        files = []
        if form.is_valid():
            print("form valid")
            if 'multi_files' in request.FILES:
                files.extend(request.FILES.getlist('multi_files'))          
            # Get clean FileList
            for f in files:
                fs = OverwriteStorage(location=DirName)
                filename = await sync_to_async(fs.save)(f.name, f)
                self.filelist.append(filename)

        valLog=await sync_to_async(upload_VitekPDF_List)(request, SessionKey, DirName, self.filelist, OrgBatchID=self.orgbatch_id, upload=False, appuser=request.user)
        cache_key = f'valLog_{username}'
        if valLog.nLogs['Error'] >0 :
            dfLog = pd.DataFrame(valLog.get_aslist(logTypes= ['Error']))#convert result in a table
            await cache.aset(f'{username}_vitek_showForm', False)
            confirm_to_save = False
        else:
            dfLog = pd.DataFrame(valLog.get_aslist())
            await cache.aset(f'{username}_vitek_showForm', True)
            confirm_to_save = True
        valLog=dfLog.to_html(classes=[ "table", "table-bordered", "fixTableHead", "bg-light", "overflow-auto"], index=False)        
        # print(f'store vlog at {datetime.datetime.now()}') #--Async Test
        await cache.aset(f'{username}_vitek_filelist', self.filelist)
        await cache.aset(f'{username}_vitek_DirName', DirName)
        await cache.aset(f'{username}_vitek_result', {'confirm_to_save':confirm_to_save, 'validation_result': valLog})
        return None

    async def handle_upload(self, request, SessionKey, username, form):
        print("step validation again")            
        upload = False
        if form.is_valid():
            confirm = form.cleaned_data.get('confirm')
            if confirm:
                upload = confirm
                print(f"confirm : {confirm}")
            self.organism_batch = request.POST.get("orgbatch_id")  # get organism_batch
            DirName = await cache.aget(f'{request.user.username}_vitek_DirName')  # get file path
            self.filelist = await cache.aget(f'{request.user.username}_vitek_filelist')  # get files' name   
            valLog=await sync_to_async(upload_VitekPDF_List)(request, SessionKey, DirName, self.filelist , OrgBatchID=self.orgbatch_id, upload=False, appuser=request.user)
            if valLog.nLogs['Error'] >0 :
                dfLog = pd.DataFrame(valLog.get_aslist(logTypes= ['Error']))#convert result in a table
            else:
                dfLog = pd.DataFrame(valLog.get_aslist())
            valLog=dfLog.to_html(classes=[ "table", "table-bordered", "fixTableHead", "bg-light", "overflow-auto"], index=False)
            await cache.aset(f'{username}_vitek_result', {'confirm_to_save':confirm, 'validation_result': valLog})
            return None

    async def handle_finalize(self, request, SessionKey, username, form):
        print("Finalize")
        dirname = await cache.aget(f'{username}_vitek_DirName')
        show_Form= await cache.aget(f'{username}_vitek_showForm')
        await self.delete_directory(dirname)
        await sync_to_async(cache.delete_many)([f'valLog_{username}', SessionKey, f'{username}_vitek_filelist', 
                                                f'{username}_vitek_DirName', f'{username}_vitek_result', f'{username}_vitek_processControl',
                                                f'{username}_vitek_showForm', ])
        
        del request.session['current_step']
        return redirect(request.META.get('HTTP_REFERER', '/'))

    async def delete_directory(self, dirname):
        if dirname:
            await sync_to_async(shutil.rmtree)(dirname)
        else:
            print("no dir")
        print('deleted')