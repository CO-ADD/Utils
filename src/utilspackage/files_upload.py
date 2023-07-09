"""
File-upload...
"""
import os
import magic
import logging
logger = logging.getLogger(__name__)
#import clamd
from io import BytesIO
import mimetypes

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.template.defaultfilters import filesizeformat
from django.utils.deconstruct import deconstructible
from django.views import View
from django.shortcuts import render

from .views_base import SuperUserRequiredMixin
from .validation_log import Validation_Log
from .data import Timer


# --files upload--
## create user folder
def file_location(instance, filename=None):
    '''
    return a file path
    instance - request or request.user
    '''
    location=settings.MEDIA_ROOT+'/'+str(instance)
    return location

## Override filename in FileStorage
class OverwriteStorage(FileSystemStorage):
    
    def get_available_name(self, name, max_length=None):
        """
        Returns a filename that's free on the target storage system, and
        available for new content to be written to.
        """
        # If the filename already exists, remove it as if it was a true file system
    
        if self.exists(name):
            os.remove(os.path.join(self.location, name))
        return name

## validate files size, type, scan virus...
@deconstructible
class FileValidator(object):
    error_messages = {
     'max_size': ("Ensure this file size is not greater than %(max_size)s."
                  " Your file size is %(size)s."),
     'min_size': ("Ensure this file size is not less than %(min_size)s. "
                  "Your file size is %(size)s."),
     'content_type': "Files is not correct type.",
    }

    def __init__(self, max_size=None, min_size=None, content_types=()):
        self.max_size = max_size
        self.min_size = min_size
        self.content_types = content_types

    def __call__(self, data):
        
        # Scan File 
        # Connect to ClamAV daemon 
        # cd = clamd.ClamdUnixSocket(path="/run/clamd.scan/clamd.sock")
        # self.scan_file(data, cd)

        # Type validation
        if self.content_types:
            content_type =magic.from_buffer(data.read(), mime=True)
            data.seek(0)
            if content_type not in self.content_types:
                params = { 'content_type': content_type }
                raise ValidationError(self.error_messages['content_type'],
                                   'content_type', params)       

    def scan_file(self, file, cd):
        file_like_object = BytesIO(file.read())
        scan_result = cd.instream(file_like_object)
        file.seek(0)

        if scan_result and scan_result['stream'][0] == 'FOUND':
            raise ValidationError(f"Virus found in {file.name}")


    def __eq__(self, other):
        return (
            isinstance(other, FileValidator) and
            self.max_size == other.max_size and
            self.min_size == other.min_size and
            self.content_types == other.content_types
        )

# 

# set filefield Validator
validate_file = FileValidator(#max_size=1024 * 100, 
                             content_types=('text/csv', 'application/pdf','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'image/png'))

## set uploading/import data forms
class MultiFileUploadForm(SuperUserRequiredMixin, forms.Form):
    pass
    
    # file_field = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True, 'webkitdirectory':True}), validators=[validate_file])
    # def save(self):
    #     for each in self.files.getlist('files'):
    #         MyModel.objects.create(file=each)

##
class FileUploadForm(SuperUserRequiredMixin, forms.Form):
    
    file_field = forms.FileField(widget=forms.ClearableFileInput(),  validators=[validate_file])

## Import data base view, Legacy
class Importhandler(SuperUserRequiredMixin, View):  
    """
    upload, parse and import data from pdf
    """  
    form_class=MultiFileUploadForm
    file_url=[]
    data_model='default'
    validate_result={}
    file_report={}
    process_name=None
    # Use to delete uploaded files
    def delete_file(self, file_name):
        location=file_location(self.request)
        file_full_path=os.path.join(location, file_name)
        try:
            os.unlink(file_full_path)
        except Exception as err:
            raise Exception
        
    # use to validate records
    def validates (self, newentry_dict, app_model, vlog, report_result, report_filelog, save, **kwargs):
        if any(newentry_dict.values()):
            for key in newentry_dict:
                for e in newentry_dict[key]:
                    newentry=app_model.check_from_dict(e, vlog)
                    if newentry.VALID_STATUS:
                        if save:
                            try:
                                newentry.save(**kwargs)
                                e['VALID_STATUS']=True
                            except Exception as err:
                                self.validate_result[key].append(f"catch Exception Card {err}")
                        else:
                            e['VALID_STATUS']=False
                    if report_result.get(key, None):
                        report_result[key].append(str(app_model._meta.db_table)+'_'+str(newentry.VALID_STATUS))
                    else:
                        report_result[key]=[str(app_model._meta.db_table)+'_'+str(newentry.VALID_STATUS)]
                    if report_filelog.get(key, None):
                        report_filelog[key].append(str(vlog.log_to_UI()))
                    else:
                        report_filelog[key]=[str(vlog.log_to_UI())]
                    
    def get(self, request, process_name):
        self.process_name=process_name
        return render(request, self.template_name, { 'form': self.form_class, 'process_name':self.process_name})



# --------------------------------------------------------------------------------------------
def run_impProcess(lstDict,toDictFunc,procName,appuser=None,upload=False,OutputN=100):
    """
    Run an upload process - currently designed only for command line:

        lstDict         [List of {Dict}] for entries to upload

        toDictFunc      Function to convert a {Dict} to (djClass)

        procName        Name of the Data/Process for output only

        appuser=None    AppUser used for upload

        upload=False    If upload to database, or just dry/validation of data

        OutputN=100     Output frequency to logger
    """
# --------------------------------------------------------------------------------------------
    nProc = {}
    nProc['Saved'] = 0
    nProc['notValid'] = 0
    nProcessed = 0

    nTotal = len(lstDict)
    nTime  = Timer(nTotal)
    vLog = Validation_Log(procName)
    logger.info(f"[{procName}] Processing {nTotal} for import")

    for f in lstDict:
        nProcessed = nProcessed + 1
        vLog.reset()

        djInst = toDictFunc(f,vLog)

        if djInst.VALID_STATUS:
            if upload:
                if nProcessed%OutputN == 0:
                    eTime,sTime = nTime.remains(nProcessed)
                    logger.info(f"[{nProcessed:8d} / {nTotal:8d}] {eTime} -Save-> {djInst} ")
                djInst.save(user=appuser)
                nProc['Saved'] = nProc['Saved'] + 1
            else:
                if nProcessed%OutputN == 0:
                    eTime,sTime = nTime.remains(nProcessed)
                    logger.info(f"[{nProcessed:8d} / {nTotal:8d}] {eTime} >Check< {djInst} ")
        else:
            vLog.show(logTypes= ['Error'])
            nProc['notValid'] = nProc['notValid'] + 1

    eTime,sTime = nTime.remains(nProcessed)
    logger.info(f"[{procName}] {sTime} : {nTotal} {nProc} ({nTotal-(nProc['Saved']+nProc['notValid'])})")

    return(vLog)
