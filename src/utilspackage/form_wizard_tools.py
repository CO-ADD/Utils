'''
Steps process driven by form submission requests. for imporing data with PDFs, Excels
-Select Files to upload : parsing, validating
-Upload: parsing, validating and saving to DB
-Finalize: return to first step (Select Files)

Process variables in sessionView storages: 
        valLog - validation result table store in "validation-result"; 
        confirm-to-upload - enable upload data store in "validation-result";
        dirname - files store path store in "dirname";
        filelist - uploaded files' namelist store in "filelist";
        validation_message - summarize progress store in "validation_message";
        step_1 - store step name.
'''
import os
from django import forms
from django.shortcuts import HttpResponse, render, redirect
from formtools.wizard.views import SessionWizardView
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ValidationError
from django.utils.datastructures import MultiValueDict
from .views_base import SuperUserRequiredMixin
from .files_upload import validate_file,file_location, OverwriteStorage

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result
# --------------------------------------------------------------------------------------------------
class SelectFile_StepForm(SuperUserRequiredMixin, forms.Form):
# --------------------------------------------------------------------------------------------------
    multi_files = MultipleFileField(label='Select one or multiple files', 
                                  validators=[validate_file], 
                                  required=False)

    def clean(self):
        cleaned_data = super().clean()
        uploadfiles=[]
        # List of file fields to validate
        file_fields = ['multi_files',]
        
        # check if filelist is MultiValueDict
        if not isinstance(self.files, MultiValueDict):
            return cleaned_data
        
        for field in file_fields:
            files = self.files.getlist(f'select_file-{field}')
            
            uploadfiles.extend(files)

            for file in files:
                for validator in self.fields[field].validators:
                    try:
                        validator(file)
                    except ValidationError as e:
                        self.add_error(field, f"{file.name}: {str(e)}")
                        
        if len(uploadfiles)<1: 
            self.add_error('multi_files', "Select at least one file")
            raise forms.ValidationError("No files selected")
        return cleaned_data
    

# --------------------------------------------------------------------------------------------------
class Upload_StepForm(forms.Form):
# --------------------------------------------------------------------------------------------------
    confirm = forms.BooleanField(required=True, help_text="Confirm to upload Data")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['confirm'].error_messages = {'required': 'File(s) contain Errors. Please correct the content of the files'}

# --------------------------------------------------------------------------------------------------   

# Add more class StepForm_2(forms.Form), if needed

# --------------------------------------------------------------------------------------------------
class Finalize_StepForm(forms.Form):
# --------------------------------------------------------------------------------------------------
    pass

# --------------------------------------------------------------------------------------------------
class ImportHandler_View(SuperUserRequiredMixin,SessionWizardView):
# --------------------------------------------------------------------------------------------------
    name_step1="Upload" # step label in template
    # define more steps name
    #... 
    # define each step's form
    form_list = [
        ('select_file', None),
        ('upload',None),
        # add more step -> StepForm
        ('finalize', None),
    ]
    # define template
    template_name = None
    # Define a file storage for handling file uploads
    file_storage = FileSystemStorage(location='/tmp/')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filelist=[]
        self.dirname=None
        self.valLog=None
        self.upload=False
        self.html_columns = ['Type','Note','Item','Filename','Help']
    
    def file_process_handler(self, request, *args, **kwargs):
        pass
        
         
    def process_step(self, form):
        current_step = self.steps.current
        request = self.request

        if current_step == 'select_file':
            context={}
            self.storage.extra_data['validation_result']="-"
            self.dirname = file_location(instance=request.user)  # define file store path during file process
            files = []
            if form.is_valid():
                if 'select_file-multi_files' in request.FILES:
                    files.extend(request.FILES.getlist('select_file-multi_files'))          
                # Get clean FileList
                for f in files:
                    fs = OverwriteStorage(location=self.dirname)
                    filename = fs.save(f.name, f)
                    self.filelist.append(filename)

                # Parse and Validation
                self.valLog=self.file_process_handler(request, self.dirname, self.filelist, form_data=form.cleaned_data, upload=self.upload, appuser=request.user) 
                if self.valLog.nLogs['Error'] >0 :
                    dfLog = self.valLog.get_ashtml(logTypes= ['Error'], columns=self.html_columns)#convert result in a table
                    self.storage.extra_data['confirm_to_upload'] = False
                elif self.valLog.nLogs['Error'] <=0:
                    print(f"error is : {self.valLog.nLogs}")
                    try:
                        dfLog = self.valLog.get_ashtml(columns=self.html_columns)
                    
                        self.storage.extra_data['confirm_to_upload'] = True
                    except Exception as err:
                        dfLog=f"{err}"
                        print(dfLog)
                        self.storage.extra_data['confirm_to_upload'] = False
                else:
                    dfLog = self.valLog.nLogs.get('Error') or 'No object exists, Is this a correct data file?'

                self.storage.extra_data['validation_result'] = dfLog
                self.storage.extra_data['validation_message']= f" {len(self.filelist)} file(s) checked for errors." 
                self.storage.extra_data['filelist'] = self.filelist
                self.storage.extra_data['dirname'] = self.dirname          
            else:
                self.storage.extra_data['validation_result']="No files selected"
                return render(request, self.template_name, context)

        elif current_step == 'upload': # recheck and save to DB
            form =self.form_list['upload'](request.POST)
            self.upload=True
            self.dirname=self.storage.extra_data['dirname'] #get file path
            self.filelist=self.storage.extra_data['filelist'] #get files' name  
            self.valLog=self.file_process_handler(request, self.dirname, self.filelist, form_data=request.POST, upload=self.upload, appuser=request.user)
            if self.valLog.nLogs['Error'] >0 :
                dfLog = self.valLog.get_ashtml(logTypes= ['Error'], columns=self.html_columns)#convert result in a table
            else:
                dfLog = self.valLog.get_ashtml(columns=self.html_columns)

            self.storage.extra_data['validation_result'] = dfLog  
            self.storage.extra_data['validation_message']= f" {len(self.filelist)} file(s) Uploaded." 
        return self.get_form_step_data(form)

    def done(self, form_list, **kwargs):
        import shutil
        # Redirect to the desired page after finishing
        dirname=self.storage.extra_data['dirname']
        if dirname:
            try:
                shutil.rmtree(dirname)
            except FileNotFoundError as err:
                print(err)
            except Exception as err:
                print(err)
        return redirect(self.request.META['HTTP_REFERER'])


    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        # save information to context,
        # then display in templates  
        context['step1']=self.name_step1
        current_step = self.steps.current
        context['validation_message'] = self.storage.extra_data.get('validation_message', None)
        if current_step == 'upload_file':
            context['validation_result']="Select VITEK PDF files"
        else:
            context['validation_result'] = self.storage.extra_data.get('validation_result', None)
            print(f"result: {context['validation_result']}")
            context['confirm_to_upload']=self.storage.extra_data.get('confirm_to_upload', None)
        return context
